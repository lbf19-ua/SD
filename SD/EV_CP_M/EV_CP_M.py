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
from event_utils import generate_message_id, current_timestamp

# Configuración de Kafka
KAFKA_BROKER = 'localhost:9092'  # Cambia si tu broker está en otra IP
KAFKA_TOPIC_PRODUCE = 'cp-events'

class EV_CP_M:
    def __init__(self, central_ip='localhost', central_port=5000, engine_ip='localhost', engine_port=5001, cp_id="CP_001"):
        self.central_ip = central_ip
        self.central_port = central_port
        self.engine_ip = engine_ip
        self.engine_port = engine_port
        self.cp_id = cp_id
        self.monitor_id = f"EV_CP_M"
        self.connected_to_central = False
        self.connected_to_engine = False
        self.monitoring = False
        self.health_status = "OK"
        self.producer = None
        self.correlation_id = None  # Correlación por sesión de monitorización

    def initialize_kafka_producer(self):
        """Inicializa el productor de Kafka"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKER,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            print(f"[MONITOR] Kafka producer initialized successfully")
        except Exception as e:
            print(f"[MONITOR] Warning: Kafka producer not available: {e}")
            print(f"[MONITOR] Continuing without Kafka logging...")
            self.producer = None

    def connect_to_central(self):
        """
        Conecta al EV_Central para autenticarse y validar que el vehículo está operativo.
        Según la especificación, debe recibir los siguientes parámetros:
        - IP y puerto del EV_CP_E
        - IP y puerto del EV_Central  
        - ID del CP
        """
        try:
            print(f"[MONITOR] {self.monitor_id} connecting to Central at {self.central_ip}:{self.central_port}")

            # Generar correlation_id para la sesión de monitorización
            if not self.correlation_id:
                self.correlation_id = generate_message_id()

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(10)  # Timeout de 10 segundos
                s.connect((self.central_ip, self.central_port))
                self.connected_to_central = True

                # Mensaje de registro como indica la especificación
                registration_message = f"{self.monitor_id} {self.cp_id} registration request [cid={self.correlation_id}]"
                s.sendall(registration_message.encode())

                # Publicar evento de registro en Kafka
                if self.producer:
                    event = {
                        'message_id': generate_message_id(),
                        'component': 'monitor',
                        'cp_id': self.cp_id,
                        'monitor_id': self.monitor_id,
                        'action': 'register_to_central',
                        'timestamp': current_timestamp(),
                        'correlation_id': self.correlation_id,
                        'status': 'connecting'
                    }
                    self.producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.cp_id.encode())
                    self.producer.flush()

                # Recibir respuesta del central
                response = s.recv(1024)
                response_text = response.decode()
                print(f'[MONITOR] Response from Central: {response_text}')

                if "OK" in response_text or "authenticated" in response_text.lower() or "successful" in response_text.lower():
                    print(f"[MONITOR] Successfully authenticated with Central")
                    
                    # Publicar evento de autenticación exitosa
                    if self.producer:
                        event = {
                            'message_id': generate_message_id(),
                            'component': 'monitor',
                            'cp_id': self.cp_id,
                            'monitor_id': self.monitor_id,
                            'action': 'authenticated_with_central',
                            'timestamp': current_timestamp(),
                            'correlation_id': self.correlation_id,
                            'status': 'success'
                        }
                        self.producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.cp_id.encode())
                        self.producer.flush()
                    
                    return True
                else:
                    print(f"[MONITOR] Authentication failed with Central: {response_text}")
                    return False

        except ConnectionRefusedError:
            print(f"[MONITOR] Error: Could not connect to Central at {self.central_ip}:{self.central_port}")
            return False
        except socket.timeout:
            print(f"[MONITOR] Timeout connecting to Central")
            return False
        except Exception as e:
            print(f"[MONITOR] Error connecting to Central: {e}")
            return False
        finally:
            self.connected_to_central = False

    def connect_to_engine(self):
        """
        Conecta al Engine del CP al que pertenece para empezar a monitorizarlo.
        """
        try:
            print(f"[MONITOR] Connecting to Engine at {self.engine_ip}:{self.engine_port}")
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(10)
                s.connect((self.engine_ip, self.engine_port))
                self.connected_to_engine = True

                # Identificarse ante el Engine
                # Incluir correlation_id en el mensaje de conexión al Engine
                connection_message = f"{self.monitor_id} {self.cp_id} monitor connection [cid={self.correlation_id}]"
                s.sendall(connection_message.encode())

                # Recibir respuesta del engine
                response = s.recv(1024)
                response_text = response.decode()
                print(f'[MONITOR] Response from Engine: {response_text}')

                if self.producer:
                    event = {
                        'message_id': generate_message_id(),
                        'component': 'monitor',
                        'cp_id': self.cp_id,
                        'monitor_id': self.monitor_id,
                        'action': 'connected_to_engine',
                        'timestamp': current_timestamp(),
                        'correlation_id': self.correlation_id,
                        'engine_response': response_text
                    }
                    self.producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.cp_id.encode())
                    self.producer.flush()

                return True

        except ConnectionRefusedError:
            print(f"[MONITOR] Error: Could not connect to Engine at {self.engine_ip}:{self.engine_port}")
            return False
        except socket.timeout:
            print(f"[MONITOR] Timeout connecting to Engine")
            return False
        except Exception as e:
            print(f"[MONITOR] Error connecting to Engine: {e}")
            return False
        finally:
            self.connected_to_engine = False

    def start_monitoring(self):
        """
        Inicia el proceso de monitorización continua del Engine.
        Envía mensajes de comprobación cada segundo según la especificación.
        """
        if not self.monitoring:
            self.monitoring = True
            monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            monitoring_thread.start()
            print(f"[MONITOR] Started monitoring loop")

    def _monitoring_loop(self):
        """
        Bucle principal de monitorización que se ejecuta cada segundo.
        Envía mensajes de comprobación de estado al Engine.
        """
        consecutive_failures = 0
        max_failures = 3  # Máximo número de fallos consecutivos antes de reportar al Central
        
        while self.monitoring:
            try:
                # Conectar al Engine para comprobar estado
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)  # Timeout corto para comprobaciones rápidas
                    s.connect((self.engine_ip, self.engine_port))
                    
                    # Enviar mensaje de comprobación de estado
                    health_check_msg = f"{self.monitor_id} {self.cp_id} health_check [cid={self.correlation_id}]"
                    s.sendall(health_check_msg.encode())
                    
                    # Recibir respuesta
                    response = s.recv(1024)
                    response_text = response.decode().strip()
                    
                    if "OK" in response_text:
                        if consecutive_failures > 0:
                            print(f"[MONITOR] Engine recovered after {consecutive_failures} failures")
                        consecutive_failures = 0
                        self.health_status = "OK"
                        
                        # Log periódico cada 10 segundos en estado OK
                        if int(time.time()) % 10 == 0:
                            print(f"[MONITOR] Engine health check: OK")
                    
                    elif "KO" in response_text:
                        consecutive_failures += 1
                        self.health_status = "KO"
                        print(f"[MONITOR] Engine health check: KO (failure #{consecutive_failures})")
                        
                        # Si hay muchos fallos consecutivos, reportar al Central
                        if consecutive_failures >= max_failures:
                            self._report_failure_to_central()
                    
                    # Publicar evento de monitorización en Kafka
                    if self.producer:
                        event = {
                            'message_id': generate_message_id(),
                            'component': 'monitor',
                            'cp_id': self.cp_id,
                            'monitor_id': self.monitor_id,
                            'action': 'health_check',
                            'status': self.health_status,
                            'engine_response': response_text,
                            'consecutive_failures': consecutive_failures,
                            'timestamp': current_timestamp(),
                            'correlation_id': self.correlation_id
                        }
                        self.producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.cp_id.encode())
                        
            except (ConnectionRefusedError, socket.timeout, OSError):
                consecutive_failures += 1
                self.health_status = "CONNECTION_ERROR"
                print(f"[MONITOR] Could not connect to Engine (failure #{consecutive_failures})")
                
                if consecutive_failures >= max_failures:
                    self._report_failure_to_central()
                
            except Exception as e:
                print(f"[MONITOR] Error in monitoring loop: {e}")
            
            # Esperar 1 segundo antes de la siguiente comprobación
            time.sleep(1)

    def _report_failure_to_central(self):
        """
        Reporta un fallo del Engine al EV_Central como indica la especificación.
        """
        try:
            print(f"[MONITOR] Reporting Engine failure to Central")
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                s.connect((self.central_ip, self.central_port))
                
                # Mensaje de avería como se especifica
                failure_message = f"{self.monitor_id} {self.cp_id} ENGINE_FAILURE [cid={self.correlation_id}]"
                s.sendall(failure_message.encode())
                
                response = s.recv(1024)
                print(f'[MONITOR] Central response to failure report: {response.decode()}')
                
                # Publicar evento de reporte de fallo en Kafka
                if self.producer:
                    event = {
                        'message_id': generate_message_id(),
                        'component': 'monitor',
                        'cp_id': self.cp_id,
                        'monitor_id': self.monitor_id,
                        'action': 'report_engine_failure',
                        'timestamp': current_timestamp(),
                        'correlation_id': self.correlation_id,
                        'central_response': response.decode()
                    }
                    self.producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.cp_id.encode())
                    self.producer.flush()
                    
        except Exception as e:
            print(f"[MONITOR] Error reporting failure to Central: {e}")

    def stop_monitoring(self):
        """Detiene el proceso de monitorización"""
        self.monitoring = False
        print(f"[MONITOR] Stopped monitoring")

    def run(self):
        """
        Ejecuta el flujo completo del Monitor según la especificación:
        1. Se conecta al EV_Central para autenticarse
        2. Se conecta al Engine del CP
        3. Inicia el monitoreo continuo
        """
        print(f"[MONITOR] Starting EV_CP_M for CP {self.cp_id}")
        
        # Inicializar Kafka
        self.initialize_kafka_producer()
        
        # Paso 1: Conectar y autenticarse con el Central
        if not self.connect_to_central():
            print(f"[MONITOR] Failed to authenticate with Central. Exiting.")
            return False
        
        # Paso 2: Conectar al Engine del CP
        if not self.connect_to_engine():
            print(f"[MONITOR] Failed to connect to Engine. Exiting.")
            return False
        
        # Paso 3: Iniciar monitorización continua
        self.start_monitoring()
        
        print(f"[MONITOR] Monitor is now running. Press Ctrl+C to stop.")
        
        try:
            # Mantener el programa corriendo
            while self.monitoring:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print(f"\n[MONITOR] Received interrupt signal. Shutting down...")
            self.stop_monitoring()
            
        return True

    def test_connection(self):
        """Método simple para probar las conexiones"""
        print(f"[MONITOR] Testing connections...")
        
        self.initialize_kafka_producer()
        
        central_ok = self.connect_to_central()
        engine_ok = self.connect_to_engine()
        
        print(f"[MONITOR] Central connection: {'OK' if central_ok else 'FAILED'}")
        print(f"[MONITOR] Engine connection: {'OK' if engine_ok else 'FAILED'}")
        
        return central_ok and engine_ok

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='EV Charging Point Monitor')
    parser.add_argument('--cp-id', default='CP_001', help='Charging Point ID')
    parser.add_argument('--central-ip', default=MONITOR_CONFIG['central_ip'], help='Central Server IP')
    parser.add_argument('--central-port', type=int, default=MONITOR_CONFIG['central_port'], help='Central Server Port')
    parser.add_argument('--engine-ip', default='localhost', help='Engine Server IP')
    parser.add_argument('--engine-port', type=int, default=5001, help='Engine Server Port')
    parser.add_argument('--test', action='store_true', help='Run connection test only')
    
    args = parser.parse_args()
    
    monitor = EV_CP_M(
        central_ip=args.central_ip,
        central_port=args.central_port,
        engine_ip=args.engine_ip,
        engine_port=args.engine_port,
        cp_id=args.cp_id
    )
    
    if args.test:
        print(f"[MONITOR] Running connection test...")
        monitor.test_connection()
    else:
        print(f"[MONITOR] Starting monitor for CP {args.cp_id}")
        print(f"[MONITOR] Central: {args.central_ip}:{args.central_port}")
        print(f"[MONITOR] Engine: {args.engine_ip}:{args.engine_port}")
        monitor.run()