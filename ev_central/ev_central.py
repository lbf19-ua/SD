import os
import time
import json
import sys
import sqlite3
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import NoBrokersAvailable

#Controlamos que se reciban los parametros que necesita central, si se reciben de manera correcta lanzamos error
if len(sys.argv) < 3:
    print("Error: Faltan parámetros")
    print("Uso: python ev_central.py <puerto_escucha> <broker_ip:puerto> [bbdd_ip:puerto]")
    print("Ejemplo: python ev_central.py 8080 localhost:9092")
    exit(1)
    
#Parametros de entrada
puerto_escucha = int(sys.argv[1])
direccion_broker = sys.argv[2]
direccion_bbdd = sys.argv[3] if len(sys.argv) > 3 else None
print(f"[EV_Central] Puerto de escucha configurado: {puerto_escucha}")
print(f"[EV_Central] Broker Kafka: {direccion_broker}")
if direccion_bbdd:
    print(f"[EV_Central] Base de datos: {direccion_bbdd}")

#Nos conectamos a la base de datos
def get_db_connection():
    if direccion_bbdd:
        # Si se proporciona dirección de BBDD, usar esa ruta
        db_path = direccion_bbdd.replace(":", "_").replace("/", "_") + ".db"
    else:
        # Si no, usar archivo local
        db_path = "ev_central.db"
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Para acceder por nombre de columna
    return conn

def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    #Tabla conductores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conductores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE,
            licencia TEXT UNIQUE,
            fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    #Tabla charging_points
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS charging_points (
            cp_id TEXT PRIMARY KEY,
            ubicacion TEXT,
            estado TEXT DEFAULT 'AVAILABLE',
            potencia_maxima REAL,
            fecha_instalacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    #Tabla solicitudes_carga
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS solicitudes_carga (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cp_id TEXT,
            conductor_id INTEGER,
            timestamp_solicitud DATETIME DEFAULT CURRENT_TIMESTAMP,
            potencia_solicitada REAL,
            duracion_estimada INTEGER,
            estado_solicitud TEXT DEFAULT 'PENDING',
            FOREIGN KEY (cp_id) REFERENCES charging_points (cp_id),
            FOREIGN KEY (conductor_id) REFERENCES conductores (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("[EV_Central] Base de datos inicializada correctamente")

def insert_solicitud(cp_id, potencia_solicitada=0, duracion_estimada=0):
    """Insertar una nueva solicitud de carga"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO solicitudes_carga (cp_id, potencia_solicitada, duracion_estimada)
        VALUES (?, ?, ?)
    ''', (cp_id, potencia_solicitada, duracion_estimada))
    
    solicitud_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return solicitud_id

def update_charging_point_status(cp_id, nuevo_estado):
    """Actualizar el estado de un charging point"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Insertar CP si no existe
    cursor.execute('''
        INSERT OR IGNORE INTO charging_points (cp_id, estado)
        VALUES (?, ?)
    ''', (cp_id, nuevo_estado))
    
    # Actualizar estado
    cursor.execute('''
        UPDATE charging_points 
        SET estado = ?
        WHERE cp_id = ?
    ''', (nuevo_estado, cp_id))
    
    conn.commit()
    conn.close()

#Configuracion necesaria de kafka
BOOTSTRAP = direccion_broker  # Usar la dirección del broker proporcionada como argumento
TOPIC_STATE = os.getenv("TOPIC_STATE", "ev.cp.state")
TOPIC_REQUEST = os.getenv("TOPIC_REQUEST", "ev.supply.request")
GROUP = os.getenv("GROUP", "ev-group-central")

#Nos conectamos al productor de Kafka
def connect_producer():
    for i in range(30):
        try:
            return KafkaProducer(
                bootstrap_servers=BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode("utf-8")
            )
        except NoBrokersAvailable:
            print("[EV_Central] Kafka no disponible, reintentando...", i+1, "/30")
            time.sleep(1)
    print("[EV_Central] No fue posible conectar con Kafka")
    exit(1)

#Nos conectamos al consumidor de Kafka
def connect_consumer():
    for i in range(30):
        try:
            return KafkaConsumer(
                TOPIC_REQUEST,
                bootstrap_servers=BOOTSTRAP,
                group_id=GROUP,
                auto_offset_reset="earliest",
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            )
        except NoBrokersAvailable:
            print("[EV_Central] Kafka no disponible, reintentando...", i+1, "/30")
            time.sleep(1)
    print("[EV_Central] No fue posible conectar con Kafka")
    exit(1)

#Manejamos las solicitudes de suministro
def handle_requests(consumer):
    for message in consumer:
        print(f"[EV_Central] Solicitud recibida: {message.value}")
        
        try:
            # Extraer datos del mensaje
            cp_id = message.value.get("cpId")
            potencia_solicitada = message.value.get("requestedPower", 0)
            duracion_estimada = message.value.get("estimatedDuration", 0)
            
            if not cp_id:
                print("[EV_Central] ERROR: No se encontró cpId en el mensaje")
                continue
            
            # 1. Guardar la solicitud en BBDD
            solicitud_id = insert_solicitud(cp_id, potencia_solicitada, duracion_estimada)
            print(f"[EV_Central] Solicitud guardada en BBDD con ID: {solicitud_id}")
            
            # 2. Lógica de autorización (por ahora siempre autoriza)
            autorizado = True  # Aquí puedes agregar lógica más compleja
            
            if autorizado:
                status = "AUTHORIZED"
                # Actualizar estado del charging point a OCCUPIED
                update_charging_point_status(cp_id, "OCCUPIED")
            else:
                status = "REJECTED"
                    
            # 3. Preparar respuesta
            response = {"status": status, "cpId": cp_id}

            # 4. Enviar respuesta por Kafka
            producer = connect_producer()
            producer.send(TOPIC_STATE, response)
            producer.flush()
            print(f"[EV_Central] Enviado estado de CP: {response}")
            
        except Exception as e:
            print(f"[EV_Central] ERROR procesando solicitud: {e}")
            

# Ejecutar la aplicación
if __name__ == "__main__":
    print("[EV_Central] Iniciando...")
    init_database()
    consumer = connect_consumer()
    handle_requests(consumer)
