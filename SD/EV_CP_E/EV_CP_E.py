import socket
import time
import random
import sys
import os
# Kafka imports
from kafka import KafkaProducer
import json

# Añadir el directorio padre al path para importar network_config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network_config import ENGINE_CONFIG

# Configuración de Kafka
KAFKA_BROKER = 'localhost:9092'  # Cambia si tu broker está en otra IP
KAFKA_TOPIC_PRODUCE = 'engine-events'

class EV_CP_E:
    def __init__(self, central_ip='localhost', central_port=5000, engine_id="Engine_001"):
        self.central_ip = central_ip
        self.central_port = central_port
        self.engine_id = engine_id
        self.connected = False
        self.charging_status = "IDLE"
        self.power_output = 0

    def connect_to_central(self):
        """
        Conecta al EV_Central para recibir órdenes de carga.
        Además, publica eventos en Kafka (engine-events) cada vez que realiza una acción.
        """
        try:
            print(f"[ENGINE] {self.engine_id} connecting to Central at {self.central_ip}:{self.central_port}")

            # Inicializar productor Kafka
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKER,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.central_ip, self.central_port))
                self.connected = True

                # Identificarse como Engine
                initial_message = f"EV_CP_E {self.engine_id} ready for charging operations"
                s.sendall(initial_message.encode())

                # Publicar evento de conexión en Kafka
                event = {
                    'engine_id': self.engine_id,
                    'action': 'connect',
                    'timestamp': time.time()
                }
                producer.send(KAFKA_TOPIC_PRODUCE, event)
                producer.flush()

                # Recibir respuesta del central
                response = s.recv(1024)
                print(f'[ENGINE] Response from Central: {response.decode()}')

                # Simular operaciones de carga
                self.simulate_charging_operations(s, producer)

        except ConnectionRefusedError:
            print(f"[ENGINE] Error: Could not connect to Central at {self.central_ip}:{self.central_port}")
        except Exception as e:
            print(f"[ENGINE] Error: {e}")
        finally:
            self.connected = False

    def simulate_charging_operations(self, socket_conn, producer):
        """
        Simula operaciones de carga del engine y publica cada acción en Kafka.
        """
        try:
            for i in range(4):
                time.sleep(2)

                # Simular diferentes estados de carga
                if i == 0:
                    self.charging_status = "PREPARING"
                    self.power_output = 0
                elif i == 1:
                    self.charging_status = "CHARGING"
                    self.power_output = random.randint(5, 50)  # kW
                elif i == 2:
                    self.charging_status = "CHARGING"
                    self.power_output = random.randint(10, 50)
                else:
                    self.charging_status = "COMPLETED"
                    self.power_output = 0

                status_msg = f"EV_CP_E {self.engine_id}: Status {self.charging_status}, Power: {self.power_output}kW"
                socket_conn.sendall(status_msg.encode())

                # Publicar evento de estado en Kafka
                event = {
                    'engine_id': self.engine_id,
                    'action': 'charging_status',
                    'status': self.charging_status,
                    'power': self.power_output,
                    'timestamp': time.time()
                }
                producer.send(KAFKA_TOPIC_PRODUCE, event)
                producer.flush()

                response = socket_conn.recv(1024)
                print(f'[ENGINE] Central response: {response.decode()}')

            # Mensaje de desconexión
            socket_conn.sendall(f"EV_CP_E {self.engine_id}: Operations complete, going idle".encode())

            # Publicar evento de fin de operaciones en Kafka
            event = {
                'engine_id': self.engine_id,
                'action': 'operations_complete',
                'timestamp': time.time()
            }
            producer.send(KAFKA_TOPIC_PRODUCE, event)
            producer.flush()

        except Exception as e:
            print(f"[ENGINE] Error in charging simulation: {e}")

    def read_sensors(self):
        """Simula lectura de sensores del charging point"""
        voltage = random.uniform(220, 240)
        current = random.uniform(0, 32)
        temperature = random.uniform(20, 45)
        
        return {
            'voltage': voltage,
            'current': current, 
            'temperature': temperature,
            'power': voltage * current / 1000  # kW
        }

    def start_charging(self, power_level=22):
        """Inicia proceso de carga"""
        self.charging_status = "CHARGING"
        self.power_output = power_level
        print(f"[ENGINE] Charging started at {power_level}kW")

    def stop_charging(self):
        """Detiene proceso de carga"""
        self.charging_status = "IDLE"
        self.power_output = 0
        print(f"[ENGINE] Charging stopped")

    def test_connection(self):
        """Método simple para probar la conexión"""
        print(f"[ENGINE] Testing connection to Central...")
        self.connect_to_central()

if __name__ == "__main__":
    engine = EV_CP_E(
        central_ip=ENGINE_CONFIG['central_ip'], 
        central_port=ENGINE_CONFIG['central_port'],
        engine_id="Engine_Test_001"
    )
    print(f"[ENGINE] Connecting to Central at {ENGINE_CONFIG['central_ip']}:{ENGINE_CONFIG['central_port']}")
    engine.test_connection()