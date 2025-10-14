import socket
import time
import sys
import os
# Kafka imports
from kafka import KafkaProducer
import json

# Añadir el directorio padre al path para importar network_config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network_config import DRIVER_CONFIG

# Configuración de Kafka
KAFKA_BROKER = 'localhost:9092'  # Cambia si tu broker está en otra IP
KAFKA_TOPIC_PRODUCE = 'driver-events'

class EV_Driver:
    def __init__(self, central_ip='localhost', central_port=5000, driver_id="Driver_001", kafka_broker='localhost:9092'):
        self.central_ip = central_ip
        self.central_port = central_port
        self.driver_id = driver_id
        self.connected = False
        self.kafka_broker = kafka_broker

    def connect_to_central(self):
        """
        Conecta al EV_Central y mantiene la conexión.
        Además, publica eventos en Kafka (driver-events) cada vez que realiza una acción.
        """
        try:
            print(f"[DRIVER] {self.driver_id} connecting to Central at {self.central_ip}:{self.central_port}")

            # Inicializar productor Kafka
            producer = KafkaProducer(
                bootstrap_servers=self.kafka_broker,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.central_ip, self.central_port))
                self.connected = True

                # Identificarse como Driver
                initial_message = f"EV_Driver {self.driver_id} connection request"
                s.sendall(initial_message.encode())

                # Publicar evento de conexión en Kafka
                event = {
                    'driver_id': self.driver_id,
                    'action': 'connect',
                    'timestamp': time.time()
                }
                producer.send(KAFKA_TOPIC_PRODUCE, event)
                producer.flush()

                # Recibir respuesta del central
                response = s.recv(1024)
                print(f'[DRIVER] Response from Central: {response.decode()}')

                # Simular actividad del driver
                self.simulate_driver_activity(s, producer)

        except ConnectionRefusedError:
            print(f"[DRIVER] Error: Could not connect to Central at {self.central_ip}:{self.central_port}")
        except Exception as e:
            print(f"[DRIVER] Error: {e}")
        finally:
            self.connected = False

    def simulate_driver_activity(self, socket_conn, producer):
        """
        Simula actividad del driver (solicitar carga, etc.) y publica cada acción en Kafka.
        """
        try:
            for i in range(3):
                time.sleep(2)
                message = f"EV_Driver {self.driver_id}: Request charging session #{i+1}"
                socket_conn.sendall(message.encode())

                # Publicar evento de solicitud de carga en Kafka
                event = {
                    'driver_id': self.driver_id,
                    'action': 'request_charging',
                    'session': i+1,
                    'timestamp': time.time()
                }
                producer.send(KAFKA_TOPIC_PRODUCE, event)
                producer.flush()

                response = socket_conn.recv(1024)
                print(f'[DRIVER] Central response: {response.decode()}')

            # Mensaje de desconexión
            socket_conn.sendall(f"EV_Driver {self.driver_id}: Disconnecting".encode())

            # Publicar evento de desconexión en Kafka
            event = {
                'driver_id': self.driver_id,
                'action': 'disconnect',
                'timestamp': time.time()
            }
            producer.send(KAFKA_TOPIC_PRODUCE, event)
            producer.flush()

        except Exception as e:
            print(f"[DRIVER] Error in activity simulation: {e}")

    def test_connection(self):
        """Método simple para probar la conexión"""
        print(f"[DRIVER] Testing connection to Central...")
        self.connect_to_central()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='EV_Driver - Solicitud de suministro')
    parser.add_argument('--broker-ip', default='localhost', help='IP del broker/Bootstrap-server')
    parser.add_argument('--broker-port', type=int, default=9092, help='Puerto del broker/Bootstrap-server')
    parser.add_argument('--central-ip', default=DRIVER_CONFIG['central_ip'], help='IP de EV_Central')
    parser.add_argument('--central-port', type=int, default=DRIVER_CONFIG['central_port'], help='Puerto de EV_Central')
    parser.add_argument('--driver-id', required=True, help='ID único del cliente')
    parser.add_argument('--services-file', help='Ruta al archivo .txt con servicios a solicitar')
    parser.add_argument('--test', action='store_true', help='Solo prueba de conexión')
    args = parser.parse_args()

    # Configuración de broker para Kafka
    KAFKA_BROKER = f"{args.broker_ip}:{args.broker_port}"

    driver = EV_Driver(
        central_ip=args.central_ip,
        central_port=args.central_port,
        driver_id=args.driver_id,
        kafka_broker=f"{args.broker_ip}:{args.broker_port}"
    )

    if args.test:
        print(f"[DRIVER] Running connection test...")
        driver.test_connection()
    elif args.services_file:
        print(f"[DRIVER] Processing services from file: {args.services_file}")
        # Leer servicios del archivo txt
        try:
            with open(args.services_file, 'r', encoding='utf-8') as f:
                services = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"[DRIVER] Error reading services file: {e}")
            sys.exit(1)

        # Procesar cada servicio secuencialmente
        for idx, service in enumerate(services):
            print(f"[DRIVER] Requesting service #{idx+1}: {service}")
            try:
                # Conectar y solicitar el servicio
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((args.central_ip, args.central_port))
                    # Identificarse como Driver
                    initial_message = f"EV_Driver {args.driver_id} connection request"
                    s.sendall(initial_message.encode())
                    response = s.recv(1024)
                    print(f'[DRIVER] Response from Central: {response.decode()}')

                    # Solicitar el servicio
                    s.sendall(f"EV_Driver {args.driver_id}: Request {service}".encode())
                    response = s.recv(1024)
                    print(f'[DRIVER] Central response: {response.decode()}')

            except Exception as e:
                print(f"[DRIVER] Error requesting service: {e}")

            # Esperar 4 segundos antes de la siguiente solicitud
            if idx < len(services) - 1:
                print(f"[DRIVER] Waiting 4 seconds before next service...")
                time.sleep(4)
        print(f"[DRIVER] All services processed.")
    else:
        print(f"[DRIVER] Connecting to Central at {args.central_ip}:{args.central_port}")
        driver.test_connection()