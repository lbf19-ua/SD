import socket
import threading
import time
import sys
import os
# Kafka imports
from kafka import KafkaConsumer, KafkaProducer
import json
import sqlite3 
from pathlib import Path
# Añadir el directorio padre al path para importar network_config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network_config import CENTRAL_CONFIG
from event_utils import generate_message_id, current_timestamp
import database as db

# Configuración de Kafka
KAFKA_BROKER = 'localhost:9092'  # Cambia si tu broker está en otra IP
KAFKA_TOPICS_CONSUME = ['driver-events', 'cp-events']
KAFKA_TOPIC_PRODUCE = 'central-events'

class EV_Central:
    def __init__(self, listen_ip='0.0.0.0', listen_port=5000):
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.connected_clients = {}
        self.authenticated_users = {}  # {addr: user_dict}
        self.running = True
        
    def handle_client(self, conn, addr):
        """
        Maneja la conexión de un cliente específico por socket TCP.
        Además, puede publicar eventos en Kafka cuando recibe mensajes.
        """
        try:
            # Inicializar productor Kafka para este hilo
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKER,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            while self.running:
                data = conn.recv(1024)
                if not data:
                    break
                message = data.decode()
                print(f"[CENTRAL] Received from {addr}: {message}")

                # Publicar el evento recibido en Kafka (topic central-events)
                # Extraer correlation_id del mensaje si viene anotado como [cid=XXXX]
                corr = None
                try:
                    if '[cid=' in message:
                        start = message.index('[cid=') + 5
                        end = message.index(']', start)
                        corr = message[start:end]
                except Exception:
                    corr = None

                event = {
                    'message_id': generate_message_id(),
                    'source': str(addr),
                    'message': message,
                    'timestamp': current_timestamp(),
                    'correlation_id': corr
                }
                producer.send(KAFKA_TOPIC_PRODUCE, event)
                producer.flush()

                # Identificar tipo de cliente y responder
                if "EV_Driver" in message and "AUTH" in message:
                    # Autenticación de Driver: formato "EV_Driver driver_id AUTH username:password [cid=...]"
                    response = self.handle_driver_auth(message, addr)
                    self.connected_clients[addr] = "Driver"
                elif "EV_Driver" in message:
                    # Mensajes de Driver ya autenticado
                    if addr in self.authenticated_users:
                        response = self.handle_authenticated_driver_request(message, addr)
                    else:
                        response = "Central: Authentication required. Send AUTH username:password"
                elif "EV_CP_M" in message:
                    response = "Central: Monitor connection acknowledged"
                    self.connected_clients[addr] = "Monitor"
                elif "EV_CP_E" in message:
                    response = "Central: Engine connection acknowledged"
                    self.connected_clients[addr] = "Engine"
                else:
                    response = "Central: Unknown client type"

                # Eco del correlation_id si está presente para trazabilidad simétrica
                if corr:
                    response = f"{response} [cid={corr}]"

                conn.sendall(response.encode())

        except Exception as e:
            print(f"[CENTRAL] Error handling client {addr}: {e}")
        finally:
            if addr in self.connected_clients:
                print(f"[CENTRAL] Client {self.connected_clients[addr]} ({addr}) disconnected")
                del self.connected_clients[addr]
            if addr in self.authenticated_users:
                del self.authenticated_users[addr]
            conn.close()
    
    def handle_driver_auth(self, message: str, addr) -> str:
        """
        Maneja autenticación de Driver.
        Formato esperado: "EV_Driver driver_id AUTH username:password [cid=...]"
        """
        try:
            # Extraer username y password
            if "AUTH" in message:
                auth_part = message.split("AUTH")[1].strip()
                # Quitar [cid=...] si está presente
                if "[cid=" in auth_part:
                    auth_part = auth_part.split("[cid=")[0].strip()
                
                if ":" in auth_part:
                    username, password = auth_part.split(":", 1)
                    user = db.authenticate_user(username.strip(), password.strip())
                    
                    if user:
                        self.authenticated_users[addr] = user
                        print(f"[CENTRAL] User '{username}' authenticated successfully (balance: €{user['balance']:.2f})")
                        return f"Central: AUTH_OK user={username} balance={user['balance']:.2f}"
                    else:
                        print(f"[CENTRAL] Authentication failed for user '{username}'")
                        return "Central: AUTH_FAILED Invalid credentials"
        except Exception as e:
            print(f"[CENTRAL] Error in authentication: {e}")
            return "Central: AUTH_ERROR Malformed auth request"
        
        return "Central: AUTH_ERROR Use format: AUTH username:password"
    
    def handle_authenticated_driver_request(self, message: str, addr) -> str:
        """
        Maneja solicitudes de Driver ya autenticado.
        """
        user = self.authenticated_users.get(addr)
        if not user:
            return "Central: AUTH_REQUIRED Please authenticate first"
        
        # Solicitud de carga
        if "Request charging" in message or "Request" in message:
            # Verificar si ya tiene sesión activa
            active_session = db.get_active_session_for_user(user['id'])
            if active_session:
                return f"Central: ALREADY_CHARGING session_id={active_session['id']} cp={active_session['cp_id']}"
            
            # Verificar balance suficiente (mínimo €5 para empezar)
            if user['balance'] < 5.0:
                return f"Central: INSUFFICIENT_BALANCE balance={user['balance']:.2f} required=5.00"
            
            # Buscar punto de carga disponible
            available_cps = db.get_available_charging_points()
            if not available_cps:
                return "Central: NO_CP_AVAILABLE All charging points are busy"
            
            # Asignar primer CP disponible
            cp = available_cps[0]
            
            # Extraer correlation_id si está presente
            corr_id = None
            if '[cid=' in message:
                try:
                    start = message.index('[cid=') + 5
                    end = message.index(']', start)
                    corr_id = message[start:end]
                except Exception:
                    pass
            
            # Crear sesión
            session_id = db.create_charging_session(user['id'], cp['cp_id'], corr_id)
            print(f"[CENTRAL] Created charging session {session_id} for user '{user['username']}' at {cp['cp_id']}")
            
            return f"Central: CHARGING_AUTHORIZED session={session_id} cp={cp['cp_id']} tariff={cp['tariff_per_kwh']}"
        
        # Finalizar carga
        elif "completed" in message.lower() or "disconnect" in message.lower():
            active_session = db.get_active_session_for_user(user['id'])
            if active_session:
                # Simular energía consumida (en realidad vendría del Engine)
                import random
                energy_kwh = random.uniform(10, 50)
                result = db.end_charging_session(active_session['id'], energy_kwh)
                
                if result:
                    # Actualizar balance en memoria
                    self.authenticated_users[addr]['balance'] = result['updated_balance']
                    print(f"[CENTRAL] Session {result['session_id']} completed: {result['energy_kwh']:.2f}kWh, €{result['cost']:.2f}")
                    return f"Central: SESSION_COMPLETE energy={result['energy_kwh']:.2f}kWh cost={result['cost']:.2f} balance={result['updated_balance']:.2f}"
            
            return "Central: Disconnection acknowledged"
        
        else:
            return f"Central: Request received from {user['username']}"
    
    def start_server(self):
        """
        Inicia el servidor central (TCP) y el consumidor Kafka en hilos separados.
        """
        # Inicializar base de datos
        print("[CENTRAL] Inicializando base de datos...")
        db.init_database()
        print("[CENTRAL] Base de datos lista")
        # Mostrar puntos de recarga registrados y su ubicación/estado
        print("\n[CENTRAL] === PUNTOS DE RECARGA REGISTRADOS ===")
        charging_points = db.get_all_charging_points() if hasattr(db, 'get_all_charging_points') else None
        if charging_points is None:
            # Fallback si no existe la función: usar SELECT directo
            DB_PATH = Path(__file__).parent.parent / "ev_charging.db"
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT cp_id, location, status FROM charging_points")
                charging_points = [dict(row) for row in cursor.fetchall()]
                conn.close()
            except Exception as e:
                print(f"[CENTRAL] Error leyendo puntos de recarga: {e}")
                charging_points = []
        if charging_points:
            for cp in charging_points:
                estado = cp.get('status', 'DESCONECTADO')
                if estado not in ("available", "charging", "maintenance"):
                    estado = "DESCONECTADO"
                print(f"  {cp['cp_id']} - {cp['location']} - Estado: {estado}")
        else:
            print("  (No hay puntos de recarga registrados)")
        print("[CENTRAL] =====================================\n")
        print(f"[CENTRAL] Starting server on {self.listen_ip}:{self.listen_port}")

        # Iniciar hilo para consumir eventos de Kafka
        kafka_thread = threading.Thread(target=self.kafka_consumer_loop)
        kafka_thread.daemon = True
        kafka_thread.start()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.listen_ip, self.listen_port))
            server_socket.listen(5)

            print("[CENTRAL] Server listening for connections...")
            print(f"[CENTRAL] Connected clients: {len(self.connected_clients)}")

            try:
                while self.running:
                    conn, addr = server_socket.accept()
                    print(f"[CENTRAL] New connection from {addr}")

                    # Crear un hilo para cada cliente
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(conn, addr)
                    )
                    client_thread.daemon = True
                    client_thread.start()

            except KeyboardInterrupt:
                print("\n[CENTRAL] Shutting down server...")
                self.running = False

    def kafka_consumer_loop(self):
        """
        Hilo que consume eventos de Kafka de los topics driver-events y cp-events (unificado para Monitor/Engine).
        """
        print(f"[CENTRAL] Starting Kafka consumer for topics: {KAFKA_TOPICS_CONSUME}")
        consumer = KafkaConsumer(
            *KAFKA_TOPICS_CONSUME,
            bootstrap_servers=KAFKA_BROKER,
            auto_offset_reset='earliest',
            group_id='central-group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        for message in consumer:
            key = message.key.decode('utf-8') if message.key else None
            print(f"[CENTRAL][KAFKA] Received event from topic '{message.topic}' key={key}: {message.value}")

if __name__ == "__main__":
    print("""
    =============================================
    EV_Central - Servidor principal + Kafka
    - Escucha conexiones TCP de Driver, Monitor, Engine
    - Publica eventos en Kafka (central-events)
    - Consume eventos de Kafka (driver-events, cp-events)
    =============================================
    """)
    central = EV_Central(
        listen_ip=CENTRAL_CONFIG['ip'],
        listen_port=CENTRAL_CONFIG['port']
    )
    print(f"[CENTRAL] Server will listen on {CENTRAL_CONFIG['ip']}:{CENTRAL_CONFIG['port']}")
    print("[CENTRAL] Kafka broker: localhost:9092")
    print("[CENTRAL] Make sure this IP is accessible from other PCs in the network")
    central.start_server()