import socket
import time
import random
import sys
import os
import threading
import select
# Kafka imports
from kafka import KafkaProducer
import json

# Añadir el directorio padre al path para importar network_config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network_config import ENGINE_CONFIG
from event_utils import generate_message_id, current_timestamp

# Configuración de Kafka
KAFKA_BROKER = 'localhost:9092'  # Cambia si tu broker está en otra IP
KAFKA_TOPIC_PRODUCE = 'cp-events'

class EV_CP_E:
    def __init__(self, central_ip='localhost', central_port=5000, engine_id="Engine_001", correlation_id: str | None = None):
        self.central_ip = central_ip
        self.central_port = central_port
        self.engine_id = engine_id
        self.connected = False
        self.charging_status = "IDLE"
        self.power_output = 0
        self.engine_failure = False  # Estado de fallo del motor
        self.simulation_running = False
        self.correlation_id = correlation_id or generate_message_id()

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
                initial_message = f"EV_CP_E {self.engine_id} ready for charging operations [cid={self.correlation_id}]"
                s.sendall(initial_message.encode())

                # Publicar evento de conexión en Kafka
                event = {
                    'message_id': generate_message_id(),
                    'component': 'engine',
                    'engine_id': self.engine_id,
                    'action': 'connect',
                    'timestamp': current_timestamp(),
                    'correlation_id': self.correlation_id
                }
                producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.engine_id.encode())
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
        En modo interactivo, mantiene la conexión activa para recibir comandos de teclado.
        """
        try:
            if self.simulation_running:
                # Modo interactivo - mantener conexión activa
                print(f"[ENGINE] Modo interactivo activado. Motor listo para recibir comandos...")
                
                while self.simulation_running:
                    time.sleep(1)
                    
                    # Publicar estado actual cada 5 segundos
                    if int(time.time()) % 5 == 0:
                        status = "FAILED" if self.engine_failure else self.charging_status
                        event = {
                            'message_id': generate_message_id(),
                            'component': 'engine',
                            'engine_id': self.engine_id,
                            'action': 'status_update',
                            'status': status,
                            'power_output': self.power_output if not self.engine_failure else 0,
                            'engine_failure': self.engine_failure,
                            'timestamp': current_timestamp(),
                            'correlation_id': self.correlation_id
                        }
                        producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.engine_id.encode())
                        producer.flush()
                        
                        # Enviar estado al Central
                        status_msg = f"ENGINE_STATUS:{status}:{self.power_output if not self.engine_failure else 0}:{self.engine_failure}"
                        socket_conn.sendall(status_msg.encode())
                        
            else:
                # Modo de prueba original
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

                    status_msg = f"EV_CP_E {self.engine_id}: Status {self.charging_status}, Power: {self.power_output}kW [cid={self.correlation_id}]"
                    socket_conn.sendall(status_msg.encode())

                    # Publicar evento de estado en Kafka
                    event = {
                        'message_id': generate_message_id(),
                        'component': 'engine',
                        'engine_id': self.engine_id,
                        'action': 'charging_status',
                        'status': self.charging_status,
                        'power': self.power_output,
                        'timestamp': current_timestamp(),
                        'correlation_id': self.correlation_id
                    }
                    producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.engine_id.encode())
                    producer.flush()

                    response = socket_conn.recv(1024)
                print(f'[ENGINE] Central response: {response.decode()}')

            # Mensaje de desconexión
            socket_conn.sendall(f"EV_CP_E {self.engine_id}: Operations complete, going idle [cid={self.correlation_id}]".encode())

            # Publicar evento de fin de operaciones en Kafka
            event = {
                'message_id': generate_message_id(),
                'component': 'engine',
                'engine_id': self.engine_id,
                'action': 'operations_complete',
                'timestamp': current_timestamp(),
                'correlation_id': self.correlation_id
            }
            producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.engine_id.encode())
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
        if not self.engine_failure:
            self.charging_status = "CHARGING"
            self.power_output = power_level
            print(f"[ENGINE] Charging started at {power_level}kW")
        else:
            print(f"[ENGINE] ⚠️  Cannot start charging - Engine failure active!")

    def stop_charging(self):
        """Detiene proceso de carga"""
        self.charging_status = "IDLE"
        self.power_output = 0
        print(f"[ENGINE] Charging stopped")

    def simulate_failure(self):
        """Simula un fallo en el motor"""
        self.engine_failure = True
        if self.charging_status == "CHARGING":
            self.charging_status = "FAILED"
            self.power_output = 0
        print(f"[ENGINE] 🔴 FALLO SIMULADO - Motor en estado KO")

    def restore_normal_operation(self):
        """Restaura el funcionamiento normal del motor"""
        self.engine_failure = False
        if self.charging_status == "FAILED":
            self.charging_status = "IDLE"
        print(f"[ENGINE] 🟢 Motor restaurado - Estado OK")

    def keyboard_simulation_thread(self):
        """Hilo para capturar entrada de teclado durante la simulación"""
        print("\n" + "="*60)
        print("🎮 SIMULACIÓN INTERACTIVA DE MOTOR")
        print("="*60)
        print("Presiona las siguientes teclas durante la operación:")
        print("  🔴 'K' + ENTER → Simular FALLO del motor (KO)")
        print("  🟢 'O' + ENTER → Restaurar funcionamiento (OK)")
        print("  ❌ 'Q' + ENTER → Salir de la simulación")
        print("="*60)
        
        while self.simulation_running:
            try:
                key = input().strip().upper()
                
                if key == 'K':
                    self.simulate_failure()
                elif key == 'O':
                    self.restore_normal_operation()
                elif key == 'Q':
                    print(f"[ENGINE] Finalizando simulación...")
                    self.simulation_running = False
                    break
                else:
                    print(f"[ENGINE] Tecla no reconocida. Usa K (fallo), O (OK), Q (salir)")
                    
            except EOFError:
                break
            except Exception as e:
                print(f"[ENGINE] Error en simulación de teclado: {e}")

    def start_interactive_simulation(self):
        """Inicia la simulación interactiva con captura de teclado"""
        self.simulation_running = True
        
        # Iniciar hilo para captura de teclado
        keyboard_thread = threading.Thread(target=self.keyboard_simulation_thread, daemon=True)
        keyboard_thread.start()
        
        # Conectar al central y mantener la conexión
        self.connect_to_central()

    def test_connection(self):
        """Método simple para probar la conexión"""
        print(f"[ENGINE] Testing connection to Central...")
        self.connect_to_central()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='EV Charging Point Engine - Motor de Carga')
    parser.add_argument('--central-ip', default=ENGINE_CONFIG['central_ip'], 
                       help='IP del servidor central')
    parser.add_argument('--central-port', type=int, default=ENGINE_CONFIG['central_port'], 
                       help='Puerto del servidor central')
    parser.add_argument('--engine-id', default="Engine_001", 
                       help='Identificador del motor')
    parser.add_argument('--interactive', action='store_true', 
                       help='Activar simulación interactiva con teclado')
    
    args = parser.parse_args()
    
    engine = EV_CP_E(
        central_ip=args.central_ip, 
        central_port=args.central_port,
        engine_id=args.engine_id
    )
    
    print(f"[ENGINE] {args.engine_id} starting...")
    print(f"[ENGINE] Central server: {args.central_ip}:{args.central_port}")
    
    if args.interactive:
        # Modo simulación interactiva
        engine.start_interactive_simulation()
    else:
        # Modo prueba de conexión simple
        engine.test_connection()