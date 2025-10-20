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
from event_utils import generate_message_id, current_timestamp

# Configuración de Kafka
KAFKA_BROKER = 'localhost:9092'  # Cambia si tu broker está en otra IP
KAFKA_TOPIC_PRODUCE = 'driver-events'

class EV_Driver:
    def __init__(self, central_ip='localhost', central_port=5000, driver_id="Driver_001", 
                 kafka_broker='localhost:9092', username=None, password=None):
        self.central_ip = central_ip
        self.central_port = central_port
        self.driver_id = driver_id
        self.connected = False
        self.authenticated = False
        self.kafka_broker = kafka_broker
        self.username = username
        self.password = password
        self.user_balance = 0.0

    def connect_to_central(self):
        """
        Conecta al EV_Central y mantiene la conexión.
        Además, publica eventos en Kafka (driver-events) cada vez que realiza una acción.
        """
        try:
            print(f"[DRIVER] {self.driver_id} connecting to Central at {self.central_ip}:{self.central_port}")

            # Generar un correlation_id por sesión de conexión del Driver
            self.correlation_id = generate_message_id()

            # Inicializar productor Kafka
            producer = KafkaProducer(
                bootstrap_servers=self.kafka_broker,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.central_ip, self.central_port))
                self.connected = True

                # Autenticarse si se proporcionaron credenciales
                if self.username and self.password:
                    auth_message = f"EV_Driver {self.driver_id} AUTH {self.username}:{self.password} [cid={self.correlation_id}]"
                    s.sendall(auth_message.encode())
                    
                    # Publicar evento de auth en Kafka
                    event = {
                        'message_id': generate_message_id(),
                        'driver_id': self.driver_id,
                        'action': 'authenticate',
                        'username': self.username,
                        'timestamp': current_timestamp(),
                        'correlation_id': self.correlation_id
                    }
                    producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.driver_id.encode())
                    producer.flush()
                    
                    # Recibir respuesta de autenticación
                    auth_response = s.recv(1024).decode()
                    print(f'[DRIVER] Auth response: {auth_response}')
                    
                    if "AUTH_OK" in auth_response:
                        self.authenticated = True
                        # Extraer balance si está presente
                        if "balance=" in auth_response:
                            try:
                                balance_str = auth_response.split("balance=")[1].split()[0]
                                self.user_balance = float(balance_str)
                                print(f'[DRIVER] ✅ Authenticated successfully. Balance: €{self.user_balance:.2f}')
                            except Exception:
                                pass
                    else:
                        print(f'[DRIVER] ❌ Authentication failed')
                        return
                else:
                    # Conexión sin autenticación (modo legacy)
                    initial_message = f"EV_Driver {self.driver_id} connection request [cid={self.correlation_id}]"
                    s.sendall(initial_message.encode())
                    
                    event = {
                        'message_id': generate_message_id(),
                        'driver_id': self.driver_id,
                        'action': 'connect',
                        'timestamp': current_timestamp(),
                        'correlation_id': self.correlation_id
                    }
                    producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.driver_id.encode())
                    producer.flush()
                    
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
                message = f"EV_Driver {self.driver_id}: Request charging session #{i+1} [cid={self.correlation_id}]"
                socket_conn.sendall(message.encode())

                # Publicar evento de solicitud de carga en Kafka
                event = {
                    'message_id': generate_message_id(),
                    'driver_id': self.driver_id,
                    'action': 'request_charging',
                    'session': i+1,
                    'timestamp': current_timestamp(),
                    'correlation_id': self.correlation_id
                }
                producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.driver_id.encode())
                producer.flush()

                response = socket_conn.recv(1024)
                print(f'[DRIVER] Central response: {response.decode()}')

            # Mensaje de desconexión
            socket_conn.sendall(f"EV_Driver {self.driver_id}: Disconnecting [cid={self.correlation_id}]".encode())

            # Publicar evento de desconexión en Kafka
            event = {
                'message_id': generate_message_id(),
                'driver_id': self.driver_id,
                'action': 'disconnect',
                'timestamp': current_timestamp(),
                'correlation_id': self.correlation_id
            }
            producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.driver_id.encode())
            producer.flush()

        except Exception as e:
            print(f"[DRIVER] Error in activity simulation: {e}")

    def process_services_from_list(self, services):
        """
        Procesa una lista de servicios con conexión persistente y publicación en Kafka
        """
        try:
            print(f"[DRIVER] {self.driver_id} connecting to Central at {self.central_ip}:{self.central_port}")

            # Generar un correlation_id por sesión de conexión del Driver
            self.correlation_id = generate_message_id()

            # Inicializar productor Kafka
            producer = KafkaProducer(
                bootstrap_servers=self.kafka_broker,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.central_ip, self.central_port))
                self.connected = True

                # Autenticarse si se proporcionaron credenciales
                if self.username and self.password:
                    auth_message = f"EV_Driver {self.driver_id} AUTH {self.username}:{self.password} [cid={self.correlation_id}]"
                    s.sendall(auth_message.encode())
                    
                    event = {
                        'message_id': generate_message_id(),
                        'driver_id': self.driver_id,
                        'action': 'authenticate',
                        'username': self.username,
                        'timestamp': current_timestamp(),
                        'correlation_id': self.correlation_id
                    }
                    producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.driver_id.encode())
                    producer.flush()
                    
                    auth_response = s.recv(1024).decode()
                    print(f'[DRIVER] Auth response: {auth_response}')
                    
                    if "AUTH_OK" in auth_response:
                        self.authenticated = True
                        if "balance=" in auth_response:
                            try:
                                balance_str = auth_response.split("balance=")[1].split()[0]
                                self.user_balance = float(balance_str)
                                print(f'[DRIVER] ✅ Authenticated. Balance: €{self.user_balance:.2f}')
                            except Exception:
                                pass
                    else:
                        print(f'[DRIVER] ❌ Authentication failed')
                        return
                else:
                    # Sin autenticación
                    initial_message = f"EV_Driver {self.driver_id} connection request [cid={self.correlation_id}]"
                    s.sendall(initial_message.encode())
                    
                    event = {
                        'message_id': generate_message_id(),
                        'driver_id': self.driver_id,
                        'action': 'connect',
                        'timestamp': current_timestamp(),
                        'correlation_id': self.correlation_id
                    }
                    producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.driver_id.encode())
                    producer.flush()
                    
                    response = s.recv(1024)
                    print(f'[DRIVER] Response from Central: {response.decode()}')

                # Procesar cada servicio manteniendo la conexión
                for idx, service in enumerate(services):
                    print(f"[DRIVER] Requesting service #{idx+1}: {service}")
                    
                    # Solicitar el servicio
                    service_message = f"EV_Driver {self.driver_id}: Request {service} [cid={self.correlation_id}]"
                    s.sendall(service_message.encode())

                    # Publicar evento de solicitud de servicio en Kafka
                    event = {
                        'message_id': generate_message_id(),
                        'driver_id': self.driver_id,
                        'action': 'request_service',
                        'service': service,
                        'service_number': idx+1,
                        'timestamp': current_timestamp(),
                        'correlation_id': self.correlation_id
                    }
                    producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.driver_id.encode())
                    producer.flush()

                    # Recibir respuesta
                    response = s.recv(1024)
                    print(f'[DRIVER] Central response: {response.decode()}')

                    # Esperar 4 segundos antes de la siguiente solicitud (excepto la última)
                    if idx < len(services) - 1:
                        print(f"[DRIVER] Waiting 4 seconds before next service...")
                        time.sleep(4)

                # Mensaje de desconexión
                s.sendall(f"EV_Driver {self.driver_id}: All services completed, disconnecting [cid={self.correlation_id}]".encode())

                # Publicar evento de desconexión en Kafka
                event = {
                    'message_id': generate_message_id(),
                    'driver_id': self.driver_id,
                    'action': 'disconnect',
                    'total_services': len(services),
                    'timestamp': current_timestamp(),
                    'correlation_id': self.correlation_id
                }
                producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.driver_id.encode())
                producer.flush()

                print(f"[DRIVER] All {len(services)} services processed successfully.")

        except ConnectionRefusedError:
            print(f"[DRIVER] Error: Could not connect to Central at {self.central_ip}:{self.central_port}")
        except Exception as e:
            print(f"[DRIVER] Error: {e}")
        finally:
            self.connected = False

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
    parser.add_argument('--username', help='Username para autenticación')
    parser.add_argument('--password', help='Password para autenticación')
    parser.add_argument('--services-file', help='Ruta al archivo .txt con servicios a solicitar')
    parser.add_argument('--test', action='store_true', help='Solo prueba de conexión')
    args = parser.parse_args()

    # Configuración de broker para Kafka
    KAFKA_BROKER = f"{args.broker_ip}:{args.broker_port}"

    driver = EV_Driver(
        central_ip=args.central_ip,
        central_port=args.central_port,
        driver_id=args.driver_id,
        kafka_broker=f"{args.broker_ip}:{args.broker_port}",
        username=args.username,
        password=args.password
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

        # Procesar servicios con conexión persistente
        driver.process_services_from_list(services)
    else:
        print(f"[DRIVER] Connecting to Central at {args.central_ip}:{args.central_port}")
        driver.test_connection()