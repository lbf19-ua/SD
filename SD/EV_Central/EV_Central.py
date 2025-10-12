import socket
import threading
import time
import sys
import os
# Kafka imports
from kafka import KafkaConsumer, KafkaProducer
import json

# Añadir el directorio padre al path para importar network_config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network_config import CENTRAL_CONFIG

# Configuración de Kafka
KAFKA_BROKER = 'localhost:9092'  # Cambia si tu broker está en otra IP
KAFKA_TOPICS_CONSUME = ['driver-events', 'monitor-events', 'engine-events']
KAFKA_TOPIC_PRODUCE = 'central-events'

class EV_Central:
    def __init__(self, listen_ip='0.0.0.0', listen_port=5000):
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.connected_clients = {}
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
                event = {
                    'source': str(addr),
                    'message': message,
                    'timestamp': time.time()
                }
                producer.send(KAFKA_TOPIC_PRODUCE, event)
                producer.flush()

                # Identificar tipo de cliente y responder
                if "EV_Driver" in message:
                    response = "Central: Driver connection acknowledged"
                    self.connected_clients[addr] = "Driver"
                elif "EV_CP_M" in message:
                    response = "Central: Monitor connection acknowledged"
                    self.connected_clients[addr] = "Monitor"
                elif "EV_CP_E" in message:
                    response = "Central: Engine connection acknowledged"
                    self.connected_clients[addr] = "Engine"
                else:
                    response = "Central: Unknown client type"

                conn.sendall(response.encode())

        except Exception as e:
            print(f"[CENTRAL] Error handling client {addr}: {e}")
        finally:
            if addr in self.connected_clients:
                print(f"[CENTRAL] Client {self.connected_clients[addr]} ({addr}) disconnected")
                del self.connected_clients[addr]
            conn.close()
    
    def start_server(self):
        """
        Inicia el servidor central (TCP) y el consumidor Kafka en hilos separados.
        """
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
        Hilo que consume eventos de Kafka de los topics driver-events, monitor-events, engine-events.
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
            print(f"[CENTRAL][KAFKA] Received event from topic '{message.topic}': {message.value}")

if __name__ == "__main__":
    print("""
    =============================================
    EV_Central - Servidor principal + Kafka
    - Escucha conexiones TCP de Driver, Monitor, Engine
    - Publica eventos en Kafka (central-events)
    - Consume eventos de Kafka (driver-events, monitor-events, engine-events)
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