import socket
import time
import threading
import sys
import os
# Kafka imports
from kafka import KafkaProducer
import json

# Añadir el directorio padre al path para importar network_config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network_config import MONITOR_CONFIG

# Configuración de Kafka
KAFKA_BROKER = 'localhost:9092'  # Cambia si tu broker está en otra IP
KAFKA_TOPIC_PRODUCE = 'monitor-events'

class EV_CP_M:
    def __init__(self, central_ip='localhost', central_port=5000, monitor_id="Monitor_001"):
        self.central_ip = central_ip
        self.central_port = central_port
        self.monitor_id = monitor_id
        self.connected = False
        self.health_status = "OK"

    def connect_to_central(self):
        """
        Conecta al EV_Central para reportar estado y autenticarse.
        Además, publica eventos en Kafka (monitor-events) cada vez que realiza una acción.
        """
        try:
            print(f"[MONITOR] {self.monitor_id} connecting to Central at {self.central_ip}:{self.central_port}")

            # Inicializar productor Kafka
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKER,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.central_ip, self.central_port))
                self.connected = True

                # Identificarse como Monitor
                initial_message = f"EV_CP_M {self.monitor_id} registration request"
                s.sendall(initial_message.encode())

                # Publicar evento de registro en Kafka
                event = {
                    'monitor_id': self.monitor_id,
                    'action': 'register',
                    'timestamp': time.time()
                }
                producer.send(KAFKA_TOPIC_PRODUCE, event)
                producer.flush()

                # Recibir respuesta del central
                response = s.recv(1024)
                print(f'[MONITOR] Response from Central: {response.decode()}')

                # Simular monitorización y reporte
                self.simulate_monitoring(s, producer)

        except ConnectionRefusedError:
            print(f"[MONITOR] Error: Could not connect to Central at {self.central_ip}:{self.central_port}")
        except Exception as e:
            print(f"[MONITOR] Error: {e}")
        finally:
            self.connected = False

    def simulate_monitoring(self, socket_conn, producer):
        """
        Simula monitorización del charging point y publica cada acción en Kafka.
        """
        try:
            for i in range(4):
                time.sleep(3)

                # Simular diferentes estados
                if i == 2:
                    self.health_status = "WARNING"
                    status_msg = f"EV_CP_M {self.monitor_id}: Health status WARNING - Temperature high"
                else:
                    self.health_status = "OK"
                    status_msg = f"EV_CP_M {self.monitor_id}: Health status OK - All systems normal"

                socket_conn.sendall(status_msg.encode())

                # Publicar evento de estado en Kafka
                event = {
                    'monitor_id': self.monitor_id,
                    'action': 'health_status',
                    'status': self.health_status,
                    'timestamp': time.time()
                }
                producer.send(KAFKA_TOPIC_PRODUCE, event)
                producer.flush()

                response = socket_conn.recv(1024)
                print(f'[MONITOR] Central response: {response.decode()}')

            # Mensaje de desconexión
            socket_conn.sendall(f"EV_CP_M {self.monitor_id}: Monitoring session complete".encode())

            # Publicar evento de fin de sesión en Kafka
            event = {
                'monitor_id': self.monitor_id,
                'action': 'session_complete',
                'timestamp': time.time()
            }
            producer.send(KAFKA_TOPIC_PRODUCE, event)
            producer.flush()

        except Exception as e:
            print(f"[MONITOR] Error in monitoring simulation: {e}")

    def check_engine_health(self):
        """Método para verificar salud del Engine asociado"""
        print(f"[MONITOR] Checking Engine health...")
        # Aquí iría la lógica para comunicarse con EV_CP_E
        return self.health_status

    def test_connection(self):
        """Método simple para probar la conexión"""
        print(f"[MONITOR] Testing connection to Central...")
        self.connect_to_central()

if __name__ == "__main__":
    monitor = EV_CP_M(
        central_ip=MONITOR_CONFIG['central_ip'], 
        central_port=MONITOR_CONFIG['central_port'],
        monitor_id="Monitor_Test_001"
    )
    print(f"[MONITOR] Connecting to Central at {MONITOR_CONFIG['central_ip']}:{MONITOR_CONFIG['central_port']}")
    monitor.test_connection()