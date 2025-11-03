import socket
import time
import sys
import os
import asyncio
import json
import threading
import argparse
from pathlib import Path
from queue import Queue

# WebSocket y HTTP server
try:
    import websockets
    from aiohttp import web
    WS_AVAILABLE = True
except ImportError:
    print("[DRIVER] Warning: websockets or aiohttp not installed. Run: pip install websockets aiohttp")
    WS_AVAILABLE = False

# Kafka imports
from kafka import KafkaProducer, KafkaConsumer

# Añadir el directorio padre al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network_config import DRIVER_CONFIG, KAFKA_BROKER as KAFKA_BROKER_DEFAULT, KAFKA_TOPICS
from event_utils import generate_message_id, current_timestamp

# Configuración desde network_config o variables de entorno (Docker)
# Estos valores se sobrescribirán en main() si se pasan argumentos de línea de comandos
KAFKA_BROKER = os.environ.get('KAFKA_BROKER', KAFKA_BROKER_DEFAULT)
# También escuchar cp_events para recibir charging_progress del CP_E
KAFKA_TOPICS_CONSUME = [KAFKA_TOPICS['central_events'], KAFKA_TOPICS['cp_events']]
KAFKA_TOPIC_PRODUCE = KAFKA_TOPICS['driver_events']
SERVER_PORT = int(os.environ.get('DRIVER_PORT', DRIVER_CONFIG['ws_port']))

# Estado global compartido
class SharedState:
    def __init__(self):
        self.connected_clients = set()
        self.client_users = {}  # Mapeo: {client_id: username}
        self.charging_sessions = {}  # Diccionario: {username: session_data}
        self.pending_authorizations = {}  # Diccionario: {client_id: {cp_id, username, websocket}}
        self.notification_queue = Queue()  # Cola para notificaciones desde threads
        self.main_loop = None  # Loop principal de asyncio
        self.lock = threading.Lock()

shared_state = SharedState()

class EV_DriverWS:
    """Versión del driver con soporte WebSocket para la interfaz web"""
    
    def __init__(self, central_ip='localhost', central_port=5000, driver_id="Driver_WS_001", 
                 kafka_broker='localhost:9092'):
        self.central_ip = central_ip
        self.central_port = central_port
        self.driver_id = driver_id
        self.kafka_broker = kafka_broker
        self.producer = None
        self.consumer = None
        self.main_loop = None  # Guardar referencia al loop principal
        self.initialize_kafka()
        
        # Iniciar consumer en thread separado
        kafka_thread = threading.Thread(target=self.kafka_listener, daemon=True)
        kafka_thread.start()
        
        # Iniciar thread de timeout para sesiones sin confirmación
        timeout_thread = threading.Thread(target=self.check_charging_timeouts, daemon=True)
        timeout_thread.start()

    def initialize_kafka(self):
        """Inicializa el productor de Kafka"""
        try:
            # Producer sin api_version explícito (auto-detección)
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_broker,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                request_timeout_ms=30000,
                retries=3,
                acks='all'  # Esperar confirmación de todos los replicas
            )
            # Consumer sin api_version explícito (auto-detección)
            self.consumer = KafkaConsumer(
                *KAFKA_TOPICS_CONSUME,
                bootstrap_servers=self.kafka_broker,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                group_id=f'ev_driver_group_{self.driver_id}',
                request_timeout_ms=30000,
                session_timeout_ms=10000,
                consumer_timeout_ms=5000
            )
            print(f"[DRIVER] Kafka producer and consumer initialized")
            print(f"[DRIVER] Kafka broker: {self.kafka_broker}")
            print(f"[DRIVER] Consuming topics: {KAFKA_TOPICS_CONSUME}")
            print(f"[DRIVER] Publishing to: {KAFKA_TOPIC_PRODUCE}")
        except Exception as e:
            print(f"[DRIVER]  Warning: Kafka not available: {e}")
            import traceback
            traceback.print_exc()
            
    def kafka_listener(self):
        """Escucha mensajes de Kafka, especialmente las respuestas de autorización"""
        print(f"[KAFKA] Consumer started, listening to {KAFKA_TOPICS_CONSUME}")
        while True:
            try:
                # Verificar que consumer esté inicializado
                if self.consumer is None:
                    print(f"[KAFKA] Consumer not initialized, attempting to reconnect...")
                    # Intentar inicializar consumer
                    try:
                        # Sin api_version explícito (auto-detección)
                        self.consumer = KafkaConsumer(
                            *KAFKA_TOPICS_CONSUME,
                            bootstrap_servers=self.kafka_broker,
                            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                            auto_offset_reset='latest',
                            group_id=f'ev_driver_group_{self.driver_id}',
                            request_timeout_ms=30000,
                            session_timeout_ms=10000,
                            consumer_timeout_ms=5000
                        )
                        print(f"[KAFKA] Consumer reconnected successfully")
                    except Exception as e:
                        print(f"[KAFKA] Failed to reconnect consumer: {e}")
                        time.sleep(5)  # Esperar antes de reintentar
                        continue
                
                for message in self.consumer:
                    event = message.value
                    event_type = event.get('event_type')
                    print(f"[KAFKA] Received {event_type} from Central")
                    
                    if event_type == 'AUTHORIZATION_RESPONSE':
                        client_id = event.get('client_id')
                        cp_id = event.get('cp_id')
                        authorized = event.get('authorized', False)
                        reason = event.get('reason', '')
                        
                        # Procesar respuesta de autorización
                        with shared_state.lock:
                            if client_id in shared_state.pending_authorizations:
                                auth_data = shared_state.pending_authorizations[client_id]
                                username = auth_data.get('username')
                                websocket_ref = auth_data.get('websocket')
                                
                                if authorized:
                                    print(f"[DRIVER] Central autorizó carga en {cp_id}")
                                    
                                    # ARQUITECTURA REAL:
                                    # Central ya envió el comando 'charging_started' al CP_E.
                                    # Driver solo crea sesión local para tracking y espera actualizaciones del CP_E.
                                    
                                    # Obtener session_id del evento si está disponible
                                    session_id = event.get('session_id', 'unknown')
                                    
                                    # Almacenar en estado local (sin BD)
                                    shared_state.charging_sessions[username] = {
                                        'username': username,
                                        'cp_id': cp_id,
                                        'session_id': session_id,
                                        'start_time': time.time(),
                                        'authorization_time': time.time(),  # Tiempo de autorización para timeout
                                        'cp_charging_confirmed': False,  # Flag: CP confirma que está cargando
                                        'energy': 0.0,
                                        'cost': 0.0,
                                        'tariff': 0.30  # Tariff por defecto
                                    }
                                    
                                    # Notificar al websocket que la carga ha iniciado
                                    print(f"[DRIVER] Encolando notificación charging_started para {username}, client_id={client_id}")
                                    shared_state.notification_queue.put({
                                        'type': 'charging_started',
                                        'username': username,
                                        'cp_id': cp_id,
                                        'client_id': client_id
                                    })
                                    
                                    # NO limpiar pending_authorizations todavía
                                    # Lo limpiaremos después de enviar la notificación
                                else:
                                    print(f"[DRIVER] Central rechazó autorización: {reason}")
                                    # Marcar autorización como rechazada
                                    auth_data['rejected'] = True
                                    auth_data['reason'] = reason
                                    # Notificar rechazo al websocket
                                    shared_state.notification_queue.put({
                                        'type': 'authorization_rejected',
                                        'username': username,
                                        'reason': reason,
                                        'client_id': client_id
                                    })
                                    
                                    # NO limpiar aún, se limpiará en el procesador
                    
                    # PROCESAR EVENTOS DE ERROR DE CP
                    elif event_type == 'CP_ERROR_SIMULATED':
                        cp_id = event.get('cp_id')
                        error_type = event.get('error_type')
                        message_text = event.get('message')
                        
                        print(f"[DRIVER] CP {cp_id} tiene error: {error_type}")
                        
                        # Verificar si algún usuario está usando ese CP
                        with shared_state.lock:
                            for username, session in list(shared_state.charging_sessions.items()):
                                if session.get('cp_id') == cp_id:
                                    # Notificar al usuario
                                    notification = {
                                        'type': 'cp_error',
                                        'cp_id': cp_id,
                                        'error_type': error_type,
                                        'message': message_text,
                                        'username': username
                                    }
                                    shared_state.notification_queue.put(notification)
                                    print(f"[DRIVER] Notificando error a {username}")
                    
                    elif event_type == 'CP_ERROR_FIXED':
                        cp_id = event.get('cp_id')
                        message_text = event.get('message')
                        
                        print(f"[DRIVER] CP {cp_id} reparado")
                        
                        # Notificar a todos los usuarios conectados
                        notification = {
                            'type': 'cp_fixed',
                            'cp_id': cp_id,
                            'message': message_text
                        }
                        shared_state.notification_queue.put(notification)
                    
                    # RECIBIR ACTUALIZACIONES DE CARGA DEL CP_E
                    elif event_type == 'charging_progress':
                        # El CP_E publica progreso cada 5 segundos
                        username = event.get('username')
                        energy_kwh = event.get('energy_kwh', 0.0)
                        cost = event.get('cost', 0.0)
                        
                        # Actualizar sesión local con datos REALES del CP_E
                        with shared_state.lock:
                            if username in shared_state.charging_sessions:
                                shared_state.charging_sessions[username]['energy'] = energy_kwh
                                shared_state.charging_sessions[username]['cost'] = cost
                                shared_state.charging_sessions[username]['cp_charging_confirmed'] = True  # CP confirmó que está cargando
                                print(f"[DRIVER] Actualización de CP_E: {username} → {energy_kwh:.2f} kWh, €{cost:.2f}")
                    
                    # RECIBIR TICKET FINAL AL TERMINAR LA CARGA
                    elif event_type == 'CHARGING_TICKET':
                        username = event.get('username')
                        cp_id = event.get('cp_id')
                        energy_kwh = event.get('energy_kwh', 0.0)
                        cost = event.get('cost', 0.0)
                        duration_sec = event.get('duration_sec', 0)
                        reason = event.get('reason', 'completed')
                        
                        print(f"[DRIVER] Ticket recibido para {username}: {energy_kwh:.2f} kWh, €{cost:.2f}")
                        
                        # Notificar al websocket del usuario
                        shared_state.notification_queue.put({
                            'type': 'charging_ticket',
                            'username': username,
                            'cp_id': cp_id,
                            'energy_kwh': energy_kwh,
                            'cost': cost,
                            'duration_sec': duration_sec,
                            'reason': reason
                        })
                
            except Exception as e:
                print(f"[KAFKA] Consumer error: {e}")
                # Cerrar consumer anterior si existe
                if self.consumer:
                    try:
                        self.consumer.close()
                    except:
                        pass
                self.consumer = None
                
                # Intentar reconectar después de un tiempo
                try:
                    print(f"[KAFKA] Attempting to reconnect to Kafka...")
                    time.sleep(2)  # Esperar antes de reconectar
                    # Sin api_version explícito (auto-detección)
                    self.consumer = KafkaConsumer(
                        *KAFKA_TOPICS_CONSUME,
                        bootstrap_servers=self.kafka_broker,
                        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                        auto_offset_reset='latest',
                        group_id=f'ev_driver_group_{self.driver_id}',
                        request_timeout_ms=30000,
                        session_timeout_ms=10000,
                        consumer_timeout_ms=5000
                    )
                    print(f"[KAFKA] Consumer reconnected successfully")
                except Exception as reconnect_error:
                    print(f"[KAFKA] Failed to reconnect: {reconnect_error}")
                    self.consumer = None
                    time.sleep(5)  # Esperar más tiempo antes de reintentar

    def check_charging_timeouts(self):
        """
        Verifica periódicamente si hay sesiones autorizadas sin confirmación del CP.
        Si han pasado más de 15 segundos sin confirmación, cancela la sesión.
        """
        TIMEOUT_SECONDS = 15  # Tiempo máximo de espera para confirmación del CP
        
        while True:
            try:
                time.sleep(3)  # Verificar cada 3 segundos
                
                current_time = time.time()
                sessions_to_cancel = []
                
                with shared_state.lock:
                    for username, session in list(shared_state.charging_sessions.items()):
                        authorization_time = session.get('authorization_time')
                        cp_confirmed = session.get('cp_charging_confirmed', False)
                        
                        # Si la sesión fue autorizada pero el CP no confirma
                        if authorization_time and not cp_confirmed:
                            elapsed = current_time - authorization_time
                            if elapsed > TIMEOUT_SECONDS:
                                cp_id = session.get('cp_id')
                                sessions_to_cancel.append((username, cp_id))
                                print(f"[TIMEOUT] CP {cp_id} no respondió después de {elapsed:.1f}s. Cancelando sesión de {username}")
                
                # Cancelar sesiones fuera del lock para evitar deadlocks
                for username, cp_id in sessions_to_cancel:
                    with shared_state.lock:
                        if username in shared_state.charging_sessions:
                            del shared_state.charging_sessions[username]
                    
                    # Notificar al usuario que el CP no respondió
                    shared_state.notification_queue.put({
                        'type': 'charging_timeout',
                        'username': username,
                        'cp_id': cp_id,
                        'message': f'El punto de carga {cp_id} no respondió. La carga no pudo iniciarse.'
                    })
                    
                    # Notificar a Central vía Kafka para liberar el CP
                    if self.producer:
                        try:
                            self.producer.send(KAFKA_TOPIC_PRODUCE, {
                                'message_id': generate_message_id(),
                                'event_type': 'CHARGING_TIMEOUT',
                                'action': 'charging_timeout',
                                'cp_id': cp_id,
                                'username': username,
                                'reason': 'CP no respondió después de autorización',
                                'timestamp': current_timestamp()
                            })
                            self.producer.flush()
                            print(f"[TIMEOUT] Evento CHARGING_TIMEOUT enviado a Central para CP {cp_id}")
                        except Exception as e:
                            print(f"[TIMEOUT] Error enviando evento a Central: {e}")
                    
            except Exception as e:
                print(f"[TIMEOUT] Error en check_charging_timeouts: {e}")
                time.sleep(5)  # Esperar más tiempo si hay error

    def authenticate_user(self, username, password):
        """Autentica un usuario (SIMULADO - Central valida en BD)"""
        # Datos simulados para autenticación local
        users = {
            'driver1': {'id': 1, 'nombre': 'driver1', 'email': 'driver1@example.com', 'balance': 150.0, 'role': 'driver'},
            'driver2': {'id': 2, 'nombre': 'driver2', 'email': 'driver2@example.com', 'balance': 200.0, 'role': 'driver'},
            'maria_garcia': {'id': 3, 'nombre': 'maria_garcia', 'email': 'maria@example.com', 'balance': 180.0, 'role': 'driver'}
        }
        passwords = {
            'driver1': 'pass123',
            'driver2': 'pass456',
            'maria_garcia': 'maria2025'
        }
        
        if username in users and passwords.get(username) == password:
            print(f"[DRIVER] User {username} authenticated successfully")
            return {
                'success': True,
                'user': {
                    'id': users[username]['id'],
                    'username': users[username]['nombre'],
                    'email': users[username]['email'],
                    'balance': users[username]['balance'],
                    'role': users[username]['role']
                },
                'active_session': None
            }
        else:
            print(f"[DRIVER] Authentication failed for {username}")
            return {'success': False, 'message': 'Invalid credentials'}

    def request_charging(self, username):
        """
        Solicita inicio de carga mediante flujo de autorización.
        
        ============================================================================
        REQUISITO b) AUTORIZACIÓN DE SUMINISTRO - ARQUITECTURA CORRECTA
        ============================================================================
        Según la arquitectura, SOLO CENTRAL tiene acceso a la BD.
        
        El Driver:
        1. NO hace validaciones locales (Central valida TODO)
        2. Envía petición de autorización a Central vía Kafka
        3. Espera respuesta de Central
        4. Solo si Central autoriza, procede con la carga
        
        Central:
        1. Recibe petición de autorización
        2. Valida en BD: usuario, balance, sesiones activas, CP disponible
        3. Responde AUTORIZADO o RECHAZADO vía Kafka
        ============================================================================
        """
        try:
            # ====================================================================
            # NO especificar CP - Central asignará uno disponible automáticamente
            # ====================================================================
            client_id = generate_message_id()
            
            if self.producer:
                event = {
                    'message_id': generate_message_id(),
                    'event_type': 'AUTHORIZATION_REQUEST',
                    'driver_id': self.driver_id,
                    'username': username,
                    'cp_id': None,  # Central asignará automáticamente
                    'client_id': client_id,
                    'timestamp': current_timestamp()
                }
                self.producer.send(KAFKA_TOPIC_PRODUCE, event)
                self.producer.flush()
                print(f"[DRIVER] Solicitando autorización a Central (asignación automática de CP)")
                
                # Datos simulados de usuario (solo para tracking local)
                users = {'driver1': {'id': 1}, 'driver2': {'id': 2}, 'maria_garcia': {'id': 3}}
                
                # Guardar solicitud pendiente
                with shared_state.lock:
                    shared_state.pending_authorizations[client_id] = {
                        'username': username,
                        'cp_id': None,  # Central asignará el CP
                        'user_id': users.get(username, {}).get('id', 1),
                        'websocket': None  # Se asignará en el handler
                    }
                
                return {
                    'success': True,
                    'pending': True,
                    'client_id': client_id,
                    'message': 'Solicitud enviada a Central'
                }
            else:
                return {'success': False, 'message': 'Sistema de mensajería no disponible'}
                
        except Exception as e:
            print(f"[DRIVER] Charging request error: {e}")
            return {'success': False, 'message': str(e)}

    def request_charging_at_cp(self, username, cp_id):
        """
        Solicita inicio de carga en un CP específico (por ID).
        Central valida TODO en BD.
        """
        try:
            # Generar ID único para esta solicitud
            client_id = generate_message_id()
            
            # Publicar solicitud de autorización
            if self.producer:
                event = {
                    'message_id': generate_message_id(),
                    'event_type': 'AUTHORIZATION_REQUEST',
                    'driver_id': self.driver_id,
                    'username': username,
                    'cp_id': cp_id,
                    'client_id': client_id,
                    'timestamp': current_timestamp()
                }
                self.producer.send(KAFKA_TOPIC_PRODUCE, event)
                self.producer.flush()
                print(f"[DRIVER] Solicitando autorización a Central para {cp_id}")
                
                # Datos simulados de usuario (solo para tracking local)
                users = {'driver1': {'id': 1}, 'driver2': {'id': 2}, 'maria_garcia': {'id': 3}}
                
                # Guardar solicitud pendiente
                with shared_state.lock:
                    shared_state.pending_authorizations[client_id] = {
                        'username': username,
                        'cp_id': cp_id,
                        'user_id': users.get(username, {}).get('id', 1),
                        'websocket': None  # Se asignará en el handler de websocket
                    }
                
                return {
                    'success': True,
                    'pending': True,
                    'client_id': client_id,
                    'message': 'Solicitud enviada a Central'
                }
            else:
                return {'success': False, 'message': 'Sistema de mensajería no disponible'}
        except Exception as e:
            print(f"[DRIVER] Charging request (specific CP) error: {e}")
            return {'success': False, 'message': str(e)}

    def stop_charging(self, username):
        """
        Detiene la carga actual (enviar evento a Central para procesar en BD)
        
        ARQUITECTURA REAL: Usa la energía REAL reportada por CP_E, no simulada.
        """
        try:
            # Verificar si hay sesión activa local
            with shared_state.lock:
                session_data = shared_state.charging_sessions.get(username)
                if not session_data:
                    return {'success': False, 'message': 'No active charging session'}
                
                cp_id = session_data.get('cp_id')
                # Usar energía REAL del CP_E (no simulada)
                energy_kwh = session_data.get('energy', 0.0)
                cost = session_data.get('cost', 0.0)
            
            # Publicar evento de STOP a Central para que finalice en BD
            if self.producer:
                # Buscar user_id (simulado o desde auth_data)
                users = {'driver1': {'id': 1}, 'driver2': {'id': 2}, 'maria_garcia': {'id': 3}}
                user_id = users.get(username, {}).get('id', 1)
                
                event = {
                    'message_id': generate_message_id(),
                    'driver_id': self.driver_id,
                    'action': 'charging_stopped',
                    'username': username,
                    'user_id': user_id,
                    'cp_id': cp_id,
                    'energy_kwh': energy_kwh,  # Energía REAL del CP_E
                    'timestamp': current_timestamp()
                }
                self.producer.send(KAFKA_TOPIC_PRODUCE, event)
                self.producer.flush()
                print(f"[DRIVER] Solicitando detener carga en {cp_id} (energy={energy_kwh:.2f} kWh del CP_E)")
                
                # Limpiar sesión local
                with shared_state.lock:
                    if username in shared_state.charging_sessions:
                        del shared_state.charging_sessions[username]
                
                return {
                    'success': True,
                    'energy': energy_kwh,
                    'total_cost': cost,
                    'new_balance': 150.0  # Simulado (se actualiza en BD por Central)
                }
            else:
                return {'success': False, 'message': 'Sistema de mensajería no disponible'}
                
        except Exception as e:
            print(f"[DRIVER] Stop charging error: {e}")
            return {'success': False, 'message': str(e)}

    def simulate_cp_error(self, cp_id, error_type='malfunction'):
        """Simula un error en un punto de carga (solo para admin) - Central procesa"""
        try:
            # Mapear el tipo de error al estado correcto
            if error_type == 'fault':
                new_status = 'fault'
            elif error_type == 'out_of_service':
                new_status = 'out_of_service'
            elif error_type == 'offline':
                new_status = 'offline'
            else:
                new_status = error_type
            
            # Publicar evento en Kafka para que Central procese en BD
            if self.producer:
                event = {
                    'message_id': generate_message_id(),
                    'driver_id': self.driver_id,
                    'action': 'cp_error_simulated',
                    'cp_id': cp_id,
                    'error_type': error_type,
                    'new_status': new_status,
                    'timestamp': current_timestamp()
                }
                self.producer.send(KAFKA_TOPIC_PRODUCE, event, key=cp_id.encode())
                self.producer.flush()
            
            print(f"[DRIVER] Simulando {error_type} en {cp_id} (Central procesará en BD)")
            return {
                'success': True,
                'cp_id': cp_id,
                'error_type': error_type,
                'new_status': new_status
            }
            
        except Exception as e:
            print(f"[DRIVER] Simulate error failed: {e}")
            return {'success': False, 'message': str(e)}

    def fix_cp_error(self, cp_id):
        """Corrige un error en un punto de carga (solo para admin) - Central procesa"""
        try:
            # Publicar evento en Kafka para que Central procese en BD
            if self.producer:
                event = {
                    'message_id': generate_message_id(),
                    'driver_id': self.driver_id,
                    'action': 'cp_error_fixed',
                    'cp_id': cp_id,
                    'new_status': 'available',
                    'timestamp': current_timestamp()
                }
                self.producer.send(KAFKA_TOPIC_PRODUCE, event, key=cp_id.encode())
                self.producer.flush()
            
            print(f"[DRIVER] Solicitando reparar {cp_id} (Central procesará en BD)")
            return {
                'success': True,
                'cp_id': cp_id,
                'new_status': 'available'
            }
            
        except Exception as e:
            print(f"[DRIVER] Fix error failed: {e}")
            return {'success': False, 'message': str(e)}
    
    def get_all_charging_points_status(self):
        """Obtiene el estado de todos los puntos de carga (para admin) - SIMULADO"""
        try:
            # Retornar lista vacía - Central tiene la info real
            return {
                'success': True,
                'charging_points': []
            }
        except Exception as e:
            print(f"[DRIVER] Get CPs error: {e}")
            return {'success': False, 'message': str(e)}

    def get_session_status(self, username):
        """Obtiene el estado de la sesión actual del usuario - desde estado local"""
        try:
            with shared_state.lock:
                if username in shared_state.charging_sessions:
                    return shared_state.charging_sessions[username]
            return None
        except Exception as e:
            print(f"[DRIVER] Get session status error: {e}")
            return None

# Instancia global del driver
driver_instance = EV_DriverWS(
    central_ip=DRIVER_CONFIG['central_ip'],
    central_port=DRIVER_CONFIG['central_port'],
    driver_id="Driver_WS_001",
    kafka_broker=KAFKA_BROKER
)

def get_local_ip():
    """Obtiene la IP local del sistema"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "localhost"

async def websocket_handler(websocket, path):
    """Maneja conexiones WebSocket de la interfaz web"""
    shared_state.connected_clients.add(websocket)
    print(f"[WS] New client connected. Total clients: {len(shared_state.connected_clients)}")
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get('type')
                print(f"[WS] [DEBUG] Mensaje recibido: type={msg_type}")
            except json.JSONDecodeError as e:
                print(f"[WS] Error decodificando JSON: {e}")
                continue
            except Exception as e:
                print(f"[WS] Error procesando mensaje: {e}")
                continue
            
            try:
                if msg_type == 'login':
                    # Autenticar usuario
                    result = driver_instance.authenticate_user(
                        data.get('username'),
                        data.get('password')
                    )
                    
                    if result['success']:
                        username = result['user']['username']
                        
                        # Si hay sesión activa, restaurarla en el shared_state
                        if result.get('active_session'):
                            session = result['active_session']
                            # Usar tariff por defecto (no tenemos acceso a BD)
                            with shared_state.lock:
                                shared_state.charging_sessions[username] = {
                                    'username': username,
                                    'session_id': session.get('session_id', 'unknown'),
                                    'cp_id': session.get('cp_id', 'unknown'),
                                    'start_time': session.get('start_time', time.time()),
                                    'energy': 0.0,
                                    'cost': 0.0,
                                    'tariff': 0.30  # Tariff por defecto
                                }
                        
                        response = {
                            'type': 'login_response',
                            'success': True,
                            'user': result['user']
                        }
                        
                        # Incluir sesión activa si existe
                        if result.get('active_session'):
                            response['active_session'] = result['active_session']
                        
                        await websocket.send(json.dumps(response))
                    else:
                        await websocket.send(json.dumps({
                            'type': 'login_response',
                            'success': False,
                            'message': result.get('message', 'Authentication failed')
                        }))
                
                elif msg_type == 'request_charging':
                    # Solicitar carga
                    username = data.get('username')
                    result = driver_instance.request_charging(username)
                    
                    if result.get('success'):
                        if result.get('pending'):
                            # Guardar el websocket para la respuesta
                            client_id = result['client_id']
                            with shared_state.lock:
                                if client_id in shared_state.pending_authorizations:
                                    shared_state.pending_authorizations[client_id]['websocket'] = websocket
                            
                            await websocket.send(json.dumps({
                                'type': 'charging_pending',
                                'message': 'Esperando autorización de Central...'
                            }))
                        else:
                            # Respuesta directa (no debería pasar con el nuevo flujo)
                            await websocket.send(json.dumps({
                                'type': 'error',
                                'message': result.get('message', 'Error en el flujo de autorización')
                            }))
                    else:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': result.get('message', 'Failed to start charging')
                        }))
                
                elif msg_type == 'stop_charging':
                    # Detener carga
                    username = data.get('username')
                    result = driver_instance.stop_charging(username)
                    
                    if result['success']:
                        with shared_state.lock:
                            # Eliminar la sesión del usuario específico
                            if username in shared_state.charging_sessions:
                                del shared_state.charging_sessions[username]
                        
                        await websocket.send(json.dumps({
                            'type': 'charging_stopped',
                            'energy': result['energy'],
                            'total_cost': result['total_cost'],
                            'new_balance': result['new_balance']
                        }))
                    else:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': result.get('message', 'Failed to stop charging')
                        }))
                
                elif msg_type == 'request_charging_at_cp':
                    username = data.get('username')
                    cp_id = data.get('cp_id')
                    result = driver_instance.request_charging_at_cp(username, cp_id)
                    
                    if result.get('success'):
                        if result.get('pending'):
                            # Guardar el websocket para la respuesta
                            client_id = result['client_id']
                            with shared_state.lock:
                                if client_id in shared_state.pending_authorizations:
                                    shared_state.pending_authorizations[client_id]['websocket'] = websocket
                            
                            await websocket.send(json.dumps({
                                'type': 'charging_pending',
                                'message': 'Esperando autorización de Central...'
                            }))
                    else:
                        # Respuesta directa (error de validación local)
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': result.get('message', 'Error en validación local')
                        }))
                
                elif msg_type == 'batch_charging':
                    # MÓDULO SIMPLE DE BATCH CHARGING
                    # Lee cada línea del txt → Inicia carga → Espera tiempo → Desenchufa → Siguiente CP
                    username = data.get('username')
                    cp_ids = data.get('cp_ids') or []
                    duration_sec = int(data.get('duration_sec') or 2)
                    
                    print(f"[DRIVER] [BATCH] === INICIANDO BATCH CHARGING ===")
                    print(f"[DRIVER] [BATCH] Usuario: {username}, CPs: {len(cp_ids)}, Duración: {duration_sec}s")
                    print(f"[DRIVER] [BATCH] Lista de CPs: {cp_ids}")
                    
                    try:
                        await websocket.send(json.dumps({'type': 'batch_started', 'total': len(cp_ids)}))
                    except:
                        pass
                    
                    # Procesar cada CP del archivo txt
                    for idx, cp_id in enumerate(cp_ids, 1):
                        print(f"[DRIVER] =========================================")
                        print(f"[DRIVER] [BATCH] CP {idx}/{len(cp_ids)}: {cp_id}")
                        print(f"[DRIVER] =========================================")
                        
                        try:
                            # 1. Limpiar sesión anterior si existe
                            with shared_state.lock:
                                if username in shared_state.charging_sessions:
                                    old_cp = shared_state.charging_sessions[username].get('cp_id')
                                    print(f"[DRIVER] [BATCH] Limpiando sesión anterior: {old_cp}")
                                    del shared_state.charging_sessions[username]
                            
                            # 2. Iniciar carga en este CP (enchufar)
                            print(f"[DRIVER] [BATCH] Iniciando carga en {cp_id}...")
                            start_res = driver_instance.request_charging_at_cp(username, cp_id)
                            
                            if not start_res or not start_res.get('success'):
                                print(f"[DRIVER] [BATCH] Error iniciando {cp_id}, saltando...")
                                try:
                                    await websocket.send(json.dumps({
                                        'type': 'batch_progress',
                                        'index': idx,
                                        'cp_id': cp_id,
                                        'status': 'skipped'
                                    }))
                                except:
                                    pass
                                continue
                            
                            # 3. Esperar 2 segundos por autorización (no bloquea)
                            print(f"[DRIVER] [BATCH] Esperando autorización para {cp_id} (2s máximo)...")
                            for _ in range(10):  # 10 x 0.2s = 2 segundos
                                await asyncio.sleep(0.2)
                                with shared_state.lock:
                                    if username in shared_state.charging_sessions:
                                        session = shared_state.charging_sessions[username]
                                        if session.get('cp_id') == cp_id:
                                            session['cp_charging_confirmed'] = True  # Evitar timeout
                                            print(f"[DRIVER] [BATCH] Autorización recibida para {cp_id}")
                                            break
                            
                            # Enviar evento started
                            try:
                                await websocket.send(json.dumps({
                                    'type': 'batch_progress',
                                    'index': idx,
                                    'cp_id': cp_id,
                                    'status': 'started'
                                }))
                            except:
                                pass
                            
                            # 4. Esperar el tiempo configurado (tiempo de carga)
                            print(f"[DRIVER] [BATCH] Carga iniciada en {cp_id}, esperando {duration_sec}s...")
                            
                            # Esperar en intervalos de 1 segundo con logs
                            waited = 0
                            while waited < duration_sec:
                                await asyncio.sleep(1.0)
                                waited += 1.0
                                if waited % 2 == 0 or waited >= duration_sec:
                                    print(f"[DRIVER] [BATCH] {cp_id}: {waited:.0f}s/{duration_sec}s")
                            
                            print(f"[DRIVER] [BATCH] Duración completada ({duration_sec}s) en {cp_id}")
                            
                            # 5. Desenchufar (stop_charging como en CLI)
                            print(f"[DRIVER] [BATCH] Desenchufando {cp_id} (stop_charging)...")
                            
                            try:
                                import concurrent.futures
                                loop = asyncio.get_event_loop()
                                with concurrent.futures.ThreadPoolExecutor() as executor:
                                    future = loop.run_in_executor(executor, driver_instance.stop_charging, username)
                                    stop_res = await asyncio.wait_for(future, timeout=5.0)
                                print(f"[DRIVER] [BATCH] stop_charging ejecutado para {cp_id}")
                            except Exception as e:
                                print(f"[DRIVER] [BATCH] Error en stop_charging para {cp_id}: {e}")
                            
                            # 6. Limpiar sesión
                            with shared_state.lock:
                                if username in shared_state.charging_sessions:
                                    del shared_state.charging_sessions[username]
                            
                            # Enviar evento stopped
                            try:
                                await websocket.send(json.dumps({
                                    'type': 'batch_progress',
                                    'index': idx,
                                    'cp_id': cp_id,
                                    'status': 'stopped'
                                }))
                            except:
                                pass
                            
                            print(f"[DRIVER] [BATCH] {cp_id} completado - Pasando al siguiente CP")
                            await asyncio.sleep(0.5)  # Pausa breve entre CPs
                            
                        except Exception as e:
                            print(f"[DRIVER] [BATCH] Error procesando {cp_id}: {e}")
                            import traceback
                            traceback.print_exc()
                            
                            # Limpiar y continuar
                            with shared_state.lock:
                                if username in shared_state.charging_sessions:
                                    del shared_state.charging_sessions[username]
                            
                            try:
                                await websocket.send(json.dumps({
                                    'type': 'batch_progress',
                                    'index': idx,
                                    'cp_id': cp_id,
                                    'status': 'stopped',
                                    'error': str(e)
                                }))
                            except:
                                pass
                            
                            await asyncio.sleep(0.5)
                    
                    # Batch completado
                    print(f"[DRIVER] [BATCH] === BATCH COMPLETADO: {len(cp_ids)} CPs procesados ===")
                    try:
                        await websocket.send(json.dumps({'type': 'batch_complete'}))
                    except:
                        pass
                
                elif msg_type == 'simulate_error':
                    # Simular error en CP (solo admin)
                    cp_id = data.get('cp_id')
                    error_type = data.get('error_type', 'malfunction')
                    result = driver_instance.simulate_cp_error(cp_id, error_type)
                    
                    if result['success']:
                        await websocket.send(json.dumps({
                            'type': 'error_simulated',
                            'cp_id': result['cp_id'],
                            'error_type': result['error_type'],
                            'new_status': result['new_status']
                        }))
                    else:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': result.get('message', 'Failed to simulate error')
                        }))
                
                elif msg_type == 'fix_error':
                    # Corregir error en CP (solo admin)
                    cp_id = data.get('cp_id')
                    result = driver_instance.fix_cp_error(cp_id)
                    
                    if result['success']:
                        await websocket.send(json.dumps({
                            'type': 'error_fixed',
                            'cp_id': result['cp_id'],
                            'new_status': result['new_status']
                        }))
                    else:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': result.get('message', 'Failed to fix error')
                        }))
                
                elif msg_type == 'get_all_cps':
                    # Obtener todos los CPs (solo admin)
                    result = driver_instance.get_all_charging_points_status()
                    
                    if result['success']:
                        await websocket.send(json.dumps({
                            'type': 'all_cps_status',
                            'charging_points': result['charging_points']
                        }))
                    else:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': result.get('message', 'Failed to get CPs')
                        }))
                        
            except Exception as e:
                print(f"[WS] Error procesando mensaje tipo '{msg_type}': {e}")
                import traceback
                traceback.print_exc()
                # Intentar notificar el error al cliente sin desconectar
                try:
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': f'Error procesando {msg_type}: {str(e)}'
                    }))
                except:
                    # Si no se puede enviar, continuar de todos modos
                    pass
                    
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"[WS] Error handling websocket message: {e}")
    finally:
        shared_state.connected_clients.remove(websocket)

async def websocket_handler_http(request):
    """Manejador de WebSocket para aiohttp"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    client_id = id(ws)
    shared_state.connected_clients.add(ws)
    print(f"[WS] Connected client {client_id}. Total: {len(shared_state.connected_clients)}")
    
    try:
        # Escuchar mensajes del cliente
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get('type')
                    
                    if msg_type == 'login':
                        # Autenticar usuario
                        result = driver_instance.authenticate_user(
                            data.get('username'),
                            data.get('password')
                        )
                        
                        if result['success']:
                            username = result['user']['username']
                            
                            # Si hay sesión activa, restaurarla en el shared_state
                            if result.get('active_session'):
                                session = result['active_session']
                                # Usar tariff por defecto (no tenemos acceso a BD)
                                with shared_state.lock:
                                    shared_state.charging_sessions[username] = {
                                        'username': username,
                                        'session_id': session['session_id'],
                                        'cp_id': session['cp_id'],
                                        'start_time': session['start_time'],
                                        'energy': 0.0,
                                        'cost': 0.0,
                                        'tariff': 0.30  # Tariff por defecto
                                    }
                            
                            response = {
                                'type': 'login_response',
                                'success': True,
                                'user': result['user']
                            }
                            
                            # Incluir sesión activa si existe
                            if result.get('active_session'):
                                response['active_session'] = result['active_session']
                            
                            await ws.send_str(json.dumps(response))
                        else:
                            await ws.send_str(json.dumps({
                                'type': 'login_response',
                                'success': False,
                                'message': result.get('message', 'Authentication failed')
                            }))
                    
                    elif msg_type == 'request_charging':
                        # Solicitar carga
                        username = data.get('username')
                        result = driver_instance.request_charging(username)
                        
                        if result.get('success'):
                            if result.get('pending'):
                                # Guardar el websocket para la respuesta
                                client_id = result['client_id']
                                with shared_state.lock:
                                    if client_id in shared_state.pending_authorizations:
                                        shared_state.pending_authorizations[client_id]['websocket'] = ws
                                        print(f"[WS]  Websocket guardado para client_id={client_id}, user={username}")
                                    else:
                                        print(f"[WS] client_id={client_id} no existe en pending_authorizations")
                                
                                await ws.send_str(json.dumps({
                                    'type': 'charging_pending',
                                    'message': 'Esperando autorización de Central...'
                                }))
                            else:
                                # Respuesta directa (no debería pasar con el nuevo flujo)
                                await ws.send_str(json.dumps({
                                    'type': 'error',
                                    'message': result.get('message', 'Error en el flujo de autorización')
                                }))
                        else:
                            await ws.send_str(json.dumps({
                                'type': 'error',
                                'message': result.get('message', 'Failed to start charging')
                            }))
                    
                    elif msg_type == 'stop_charging':
                        # Detener carga
                        username = data.get('username')
                        result = driver_instance.stop_charging(username)
                        
                        if result['success']:
                            with shared_state.lock:
                                # Eliminar la sesión del usuario específico
                                if username in shared_state.charging_sessions:
                                    del shared_state.charging_sessions[username]
                            
                            await ws.send_str(json.dumps({
                                'type': 'charging_stopped',
                                'username': username,  # Incluir username para filtrado en frontend
                                'energy': result['energy'],
                                'total_cost': result['total_cost'],
                                'new_balance': result['new_balance']
                            }))
                        else:
                            await ws.send_str(json.dumps({
                                'type': 'error',
                                'message': result.get('message', 'Failed to stop charging')
                            }))

                    elif msg_type == 'request_charging_at_cp':
                        username = data.get('username')
                        cp_id = data.get('cp_id')
                        result = driver_instance.request_charging_at_cp(username, cp_id)

                        if result.get('success'):
                            if result.get('pending'):
                                # Guardar el websocket para la respuesta
                                client_id = result['client_id']
                                with shared_state.lock:
                                    if client_id in shared_state.pending_authorizations:
                                        shared_state.pending_authorizations[client_id]['websocket'] = ws
                                
                                await ws.send_str(json.dumps({
                                    'type': 'charging_pending',
                                    'message': 'Esperando autorización de Central...'
                                }))
                            else:
                                # Respuesta directa (error de validación local)
                                await ws.send_str(json.dumps({
                                    'type': 'error',
                                    'message': result.get('message', 'Error en validación local')
                                }))
                        else:
                            await ws.send_str(json.dumps({
                                'type': 'error',
                                'message': result.get('message', 'Failed to start charging at CP')
                            }))

                    elif msg_type == 'batch_charging':
                        # MÓDULO SIMPLE DE BATCH CHARGING
                        # Lee cada línea del txt → Inicia carga → Espera tiempo → Desenchufa → Siguiente CP
                        username = data.get('username')
                        cp_ids = data.get('cp_ids') or []
                        duration_sec = int(data.get('duration_sec') or 2)
                        
                        print(f"[DRIVER] [BATCH] === INICIANDO BATCH CHARGING ===")
                        print(f"[DRIVER] [BATCH] Usuario: {username}, CPs: {len(cp_ids)}, Duración: {duration_sec}s")
                        print(f"[DRIVER] [BATCH] Lista de CPs: {cp_ids}")
                        
                        try:
                            await ws.send_str(json.dumps({'type': 'batch_started', 'total': len(cp_ids)}))
                        except:
                            pass
                        
                        # Procesar cada CP del archivo txt
                        for idx, cp_id in enumerate(cp_ids, 1):
                            print(f"[DRIVER] =========================================")
                            print(f"[DRIVER] [BATCH] CP {idx}/{len(cp_ids)}: {cp_id}")
                            print(f"[DRIVER] =========================================")
                            
                            try:
                                # 1. Limpiar sesión anterior si existe
                                with shared_state.lock:
                                    if username in shared_state.charging_sessions:
                                        old_cp = shared_state.charging_sessions[username].get('cp_id')
                                        print(f"[DRIVER] [BATCH] Limpiando sesión anterior: {old_cp}")
                                        del shared_state.charging_sessions[username]
                                
                                # 2. Iniciar carga en este CP (enchufar)
                                print(f"[DRIVER] [BATCH] Iniciando carga en {cp_id}...")
                                start_res = driver_instance.request_charging_at_cp(username, cp_id)
                                
                                if not start_res or not start_res.get('success'):
                                    print(f"[DRIVER] [BATCH] Error iniciando {cp_id}, saltando...")
                                    try:
                                        await ws.send_str(json.dumps({
                                            'type': 'batch_progress',
                                            'index': idx,
                                            'cp_id': cp_id,
                                            'status': 'skipped',
                                            'reason': start_res.get('message', 'unknown') if start_res else 'unknown'
                                        }))
                                    except:
                                        pass
                                    # REQUISITO 12: Esperar 4 segundos antes del siguiente servicio
                                    if idx < len(cp_ids):
                                        await asyncio.sleep(4)
                                    continue
                                
                                # 3. Esperar 2 segundos por autorización (no bloquea)
                                print(f"[DRIVER] [BATCH] Esperando autorización para {cp_id} (2s máximo)...")
                                authorized = False
                                for _ in range(10):  # 10 x 0.2s = 2 segundos
                                    await asyncio.sleep(0.2)
                                    with shared_state.lock:
                                        if username in shared_state.charging_sessions:
                                            session = shared_state.charging_sessions[username]
                                            if session.get('cp_id') == cp_id:
                                                session['cp_charging_confirmed'] = True  # Evitar timeout
                                                authorized = True
                                                print(f"[DRIVER] [BATCH] Autorización recibida para {cp_id}")
                                                break
                                
                                if not authorized:
                                    print(f"[DRIVER] [BATCH] Autorización no recibida para {cp_id}, saltando...")
                                    try:
                                        await ws.send_str(json.dumps({
                                            'type': 'batch_progress',
                                            'index': idx,
                                            'cp_id': cp_id,
                                            'status': 'skipped',
                                            'reason': 'Autorización no recibida'
                                        }))
                                    except:
                                        pass
                                    # REQUISITO 12: Esperar 4 segundos antes del siguiente servicio
                                    if idx < len(cp_ids):
                                        await asyncio.sleep(4)
                                    continue
                                
                                # Enviar evento started
                                try:
                                    await ws.send_str(json.dumps({
                                        'type': 'batch_progress',
                                        'index': idx,
                                        'cp_id': cp_id,
                                        'status': 'started'
                                    }))
                                except:
                                    pass
                                
                                # 4. Esperar el tiempo configurado (tiempo de carga)
                                print(f"[DRIVER] [BATCH] Carga iniciada en {cp_id}, esperando {duration_sec}s...")
                                
                                # Esperar en intervalos de 1 segundo con logs
                                waited = 0
                                while waited < duration_sec:
                                    await asyncio.sleep(1.0)
                                    waited += 1.0
                                    if waited % 2 == 0 or waited >= duration_sec:
                                        print(f"[DRIVER] [BATCH] {cp_id}: {waited:.0f}s/{duration_sec}s")
                                
                                print(f"[DRIVER] [BATCH] Duración completada ({duration_sec}s) en {cp_id}")
                                
                                # 5. Desenchufar (stop_charging como en CLI)
                                print(f"[DRIVER] [BATCH] Desenchufando {cp_id} (stop_charging)...")
                                
                                try:
                                    import concurrent.futures
                                    loop = asyncio.get_event_loop()
                                    with concurrent.futures.ThreadPoolExecutor() as executor:
                                        future = loop.run_in_executor(executor, driver_instance.stop_charging, username)
                                        stop_res = await asyncio.wait_for(future, timeout=5.0)
                                    print(f"[DRIVER] [BATCH] stop_charging ejecutado para {cp_id}")
                                except Exception as e:
                                    print(f"[DRIVER] [BATCH] Error en stop_charging para {cp_id}: {e}")
                                    stop_res = {'success': False, 'message': str(e)}
                                
                                # 6. Limpiar sesión
                                with shared_state.lock:
                                    if username in shared_state.charging_sessions:
                                        del shared_state.charging_sessions[username]
                                
                                # Enviar evento stopped
                                try:
                                    if stop_res.get('success'):
                                        await ws.send_str(json.dumps({
                                            'type': 'batch_progress',
                                            'index': idx,
                                            'cp_id': cp_id,
                                            'status': 'stopped',
                                            'energy': stop_res.get('energy', 0),
                                            'total_cost': stop_res.get('total_cost', 0)
                                        }))
                                    else:
                                        await ws.send_str(json.dumps({
                                            'type': 'batch_progress',
                                            'index': idx,
                                            'cp_id': cp_id,
                                            'status': 'stopped',
                                            'error': stop_res.get('message', 'unknown')
                                        }))
                                except:
                                    pass
                                
                                print(f"[DRIVER] [BATCH] {cp_id} completado - Pasando al siguiente CP")
                                
                                # REQUISITO 12: Esperar 4 segundos antes del siguiente servicio
                                if idx < len(cp_ids):
                                    print(f"[DRIVER] [BATCH] Esperando 4 segundos antes del siguiente servicio...")
                                    await asyncio.sleep(4)
                                
                            except Exception as e:
                                print(f"[DRIVER] [BATCH] Error procesando {cp_id}: {e}")
                                import traceback
                                traceback.print_exc()
                                
                                # Limpiar y continuar
                                with shared_state.lock:
                                    if username in shared_state.charging_sessions:
                                        del shared_state.charging_sessions[username]
                                
                                try:
                                    await ws.send_str(json.dumps({
                                        'type': 'batch_progress',
                                        'index': idx,
                                        'cp_id': cp_id,
                                        'status': 'stopped',
                                        'error': str(e)
                                    }))
                                except:
                                    pass
                                
                                # REQUISITO 12: Esperar 4 segundos antes del siguiente servicio
                                if idx < len(cp_ids):
                                    await asyncio.sleep(4)
                        
                        # Batch completado
                        print(f"[DRIVER] [BATCH] === BATCH COMPLETADO: {len(cp_ids)} CPs procesados ===")
                        try:
                            await ws.send_str(json.dumps({'type': 'batch_complete'}))
                        except:
                            pass
                    
                    elif msg_type == 'simulate_error':
                        # Simular error en CP (solo admin)
                        cp_id = data.get('cp_id')
                        error_type = data.get('error_type', 'malfunction')
                        result = driver_instance.simulate_cp_error(cp_id, error_type)
                        
                        if result['success']:
                            await ws.send_str(json.dumps({
                                'type': 'error_simulated',
                                'cp_id': result['cp_id'],
                                'error_type': result['error_type'],
                                'new_status': result['new_status']
                            }))
                        else:
                            await ws.send_str(json.dumps({
                                'type': 'error',
                                'message': result.get('message', 'Failed to simulate error')
                            }))
                    
                    elif msg_type == 'fix_error':
                        # Corregir error en CP (solo admin)
                        cp_id = data.get('cp_id')
                        result = driver_instance.fix_cp_error(cp_id)
                        
                        if result['success']:
                            await ws.send_str(json.dumps({
                                'type': 'error_fixed',
                                'cp_id': result['cp_id'],
                                'new_status': result['new_status']
                            }))
                        else:
                            await ws.send_str(json.dumps({
                                'type': 'error',
                                'message': result.get('message', 'Failed to fix error')
                            }))
                    
                    elif msg_type == 'get_all_cps':
                        # Obtener todos los CPs (solo admin)
                        result = driver_instance.get_all_charging_points_status()
                        
                        if result['success']:
                            await ws.send_str(json.dumps({
                                'type': 'all_cps_status',
                                'charging_points': result['charging_points']
                            }))
                        else:
                            await ws.send_str(json.dumps({
                                'type': 'error',
                                'message': result.get('message', 'Failed to get CPs')
                            }))
                            
                except json.JSONDecodeError:
                    print(f"[WS] Invalid JSON from {client_id}")
            elif msg.type == web.WSMsgType.ERROR:
                print(f"[WS] WebSocket error: {ws.exception()}")
                
    except Exception as e:
        print(f"[WS] Error with client {client_id}: {e}")
    finally:
        shared_state.connected_clients.discard(ws)
        print(f"[WS] Disconnected client {client_id}. Total: {len(shared_state.connected_clients)}")
    
    return ws

async def serve_dashboard(request):
    """Sirve el archivo dashboard.html"""
    dashboard_path = Path(__file__).parent / 'dashboard.html'
    try:
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return web.Response(text=html_content, content_type='text/html')
    except FileNotFoundError:
        return web.Response(text="Dashboard not found", status=404)

async def start_http_server():
    """Inicia el servidor HTTP para servir el dashboard"""
    app = web.Application()
    app.router.add_get('/', serve_dashboard)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', SERVER_PORT)
    await site.start()
    print(f"[HTTP] Server started on http://0.0.0.0:{SERVER_PORT}")

async def process_notifications():
    """Procesa notificaciones desde la cola y las envía a los websockets específicos"""
    while True:
        try:
            # Obtener notificación de la cola (sin bloquear)
            try:
                notification = shared_state.notification_queue.get_nowait()
            except:
                await asyncio.sleep(0.1)
                continue
            
            if notification['type'] == 'charging_started':
                username = notification['username']
                cp_id = notification['cp_id']
                client_id = notification.get('client_id')
                
                print(f"[NOTIF] Procesando charging_started: user={username}, cp={cp_id}, client_id={client_id}")
                
                message = json.dumps({
                    'type': 'charging_started',
                    'username': username,
                    'cp_id': cp_id,
                    'message': f'Carga iniciada en {cp_id}'
                })
                
                # Buscar el websocket usando client_id
                sent = False
                ws_to_send = None
                
                with shared_state.lock:
                    print(f"[NOTIF] Buscando websocket para client_id={client_id}")
                    print(f"[NOTIF] pending_authorizations keys: {list(shared_state.pending_authorizations.keys())}")
                    
                    if client_id and client_id in shared_state.pending_authorizations:
                        auth_data = shared_state.pending_authorizations[client_id]
                        ws = auth_data.get('websocket')
                        print(f"[NOTIF] Websocket encontrado: {ws is not None}")
                        
                        # Verificar si websocket es válido ANTES de limpiar
                        if ws:
                            # Limpiar pending_authorizations solo si websocket es válido
                            shared_state.pending_authorizations.pop(client_id, None)
                            
                            # Guardar referencia al websocket para enviar fuera del lock
                            ws_to_send = ws
                        else:
                            # Websocket es None, limpiar de todas formas
                            shared_state.pending_authorizations.pop(client_id, None)
                            print(f"[NOTIF] Websocket es None para client_id {client_id}")
                    else:
                        print(f"[NOTIF] client_id {client_id} NO está en pending_authorizations")
                
                # Enviar al websocket específico (fuera del lock para evitar deadlock)
                if ws_to_send:
                    try:
                        if hasattr(ws_to_send, 'send_str'):
                            await ws_to_send.send_str(message)
                        else:
                            await ws_to_send.send(message)
                        print(f"[NOTIF] Notificación enviada a {username} en {cp_id}")
                        sent = True
                    except Exception as e:
                        print(f"[NOTIF] Error enviando a {username}: {e}")
                
                # Fallback: enviar a todos los clientes si no se envió
                if not sent:
                    print(f"[NOTIF] WARNING: Usando BROADCAST a todos los clientes para {username}")
                    with shared_state.lock:
                        clients_to_notify = list(shared_state.connected_clients)
                    for client in clients_to_notify:
                        try:
                            if hasattr(client, 'send_str'):
                                await client.send_str(message)
                            else:
                                await client.send(message)
                        except:
                            pass
                    print(f"[NOTIF] Broadcast enviado a {len(clients_to_notify)} clientes")
                        
            elif notification['type'] == 'authorization_rejected':
                username = notification['username']
                reason = notification['reason']
                client_id = notification.get('client_id')
                
                message = json.dumps({
                    'type': 'error',
                    'message': f'Autorización rechazada: {reason}'
                })
            
            # NOTIFICACIÓN DE TIMEOUT: CP no respondió después de autorización
            elif notification['type'] == 'charging_timeout':
                username = notification['username']
                cp_id = notification['cp_id']
                message_text = notification.get('message', f'El punto de carga {cp_id} no respondió. La carga no pudo iniciarse.')
                
                message = json.dumps({
                    'type': 'error',
                    'message': message_text,
                    'cp_id': cp_id,
                    'username': username
                })
                
                print(f"[NOTIF] Enviando notificación de timeout a {username} para CP {cp_id}")
                
                # Broadcast a todos los clientes (el frontend filtrará por username)
                with shared_state.lock:
                    clients = list(shared_state.connected_clients)
                for client in clients:
                    try:
                        if hasattr(client, 'send_str'):
                            await client.send_str(message)
                        else:
                            await client.send(message)
                    except Exception as e:
                        print(f"[NOTIF] Error enviando timeout: {e}")
                
                print(f"[NOTIF] Timeout broadcast enviado a {len(clients)} clientes")
            
            elif notification['type'] == 'authorization_rejected':
                username = notification['username']
                reason = notification['reason']
                client_id = notification.get('client_id')
                
                message = json.dumps({
                    'type': 'error',
                    'message': f'Autorización rechazada: {reason}'
                })
                
                # Buscar el websocket usando client_id
                sent = False
                with shared_state.lock:
                    if client_id and client_id in shared_state.pending_authorizations:
                        ws = shared_state.pending_authorizations[client_id].get('websocket')
                        
                        # Limpiar pending_authorizations
                        shared_state.pending_authorizations.pop(client_id, None)
                        
                        # Enviar al websocket específico
                        if ws:
                            try:
                                if hasattr(ws, 'send_str'):
                                    await ws.send_str(message)
                                else:
                                    await ws.send(message)
                                print(f"[NOTIF] Rechazo enviado a {username}")
                                sent = True
                            except Exception as e:
                                print(f"[NOTIF] Error enviando rechazo a {username}: {e}")
                
                # Fallback: enviar a todos si no se envió
                if not sent:
                    print(f"[NOTIF] WARNING: Usando BROADCAST a todos los clientes para rechazo de {username}")
                    with shared_state.lock:
                        clients_to_notify = list(shared_state.connected_clients)
                    for client in clients_to_notify:
                        try:
                            if hasattr(client, 'send_str'):
                                await client.send_str(message)
                            else:
                                await client.send(message)
                        except:
                            pass
                    print(f"[NOTIF] Broadcast de rechazo enviado a {len(clients_to_notify)} clientes")
            
            # NOTIFICACIONES DE ERROR DE CP
            elif notification['type'] == 'cp_error':
                username = notification.get('username')
                cp_id = notification['cp_id']
                message_text = notification['message']
                
                message = json.dumps({
                    'type': 'cp_error',
                    'cp_id': cp_id,
                    'message': message_text,
                    'username': username
                })
                
                # Broadcast a todos (el frontend filtrará)
                with shared_state.lock:
                    clients = list(shared_state.connected_clients)
                for client in clients:
                    try:
                        if hasattr(client, 'send_str'):
                            await client.send_str(message)
                        else:
                            await client.send(message)
                        print(f"[NOTIF] Error de CP notificado a cliente")
                    except:
                        pass
            
            elif notification['type'] == 'cp_fixed':
                cp_id = notification['cp_id']
                message_text = notification['message']
                
                message = json.dumps({
                    'type': 'cp_fixed',
                    'cp_id': cp_id,
                    'message': message_text
                })
                
                # Broadcast a todos
                with shared_state.lock:
                    clients = list(shared_state.connected_clients)
                for client in clients:
                    try:
                        if hasattr(client, 'send_str'):
                            await client.send_str(message)
                        else:
                            await client.send(message)
                        print(f"[NOTIF] Reparación de CP notificada a cliente")
                    except:
                        pass
            
            # NOTIFICACIÓN DE TICKET FINAL DE CARGA
            elif notification['type'] == 'charging_ticket':
                username = notification['username']
                cp_id = notification['cp_id']
                energy_kwh = notification['energy_kwh']
                cost = notification['cost']
                duration_sec = notification['duration_sec']
                reason = notification['reason']
                
                # Formatear duración
                duration_min = int(duration_sec / 60)
                duration_display = f"{duration_min} minutos" if duration_min > 0 else f"{duration_sec} segundos"
                
                message = json.dumps({
                    'type': 'charging_ticket',
                    'username': username,
                    'cp_id': cp_id,
                    'energy_kwh': round(energy_kwh, 2),
                    'cost': round(cost, 2),
                    'duration': duration_display,
                    'reason': reason,
                    'message': f'Ticket de carga: {energy_kwh:.2f} kWh por €{cost:.2f}'
                })
                
                print(f"[NOTIF] Enviando ticket a {username}: {energy_kwh:.2f} kWh, €{cost:.2f}")
                
                # Broadcast a todos los clientes (el frontend filtrará por username)
                with shared_state.lock:
                    clients = list(shared_state.connected_clients)
                for client in clients:
                    try:
                        if hasattr(client, 'send_str'):
                            await client.send_str(message)
                        else:
                            await client.send(message)
                    except Exception as e:
                        print(f"[NOTIF] Error enviando ticket: {e}")
                
                print(f"[NOTIF] Ticket broadcast enviado a {len(clients)} clientes")
                        
        except Exception as e:
            print(f"[NOTIF] Error processing notification: {e}")

async def broadcast_updates():
    """
    ARQUITECTURA REAL CON EV_CP_E:
    Ya NO simulamos la carga aquí. El CP_E (Engine) publica eventos 'charging_progress'
    vía Kafka que son consumidos en kafka_listener() y actualizan shared_state.charging_sessions.
    
    Esta función ahora solo hace broadcast de los datos que recibimos del CP_E real.
    """
    while True:
        await asyncio.sleep(2)
        
        with shared_state.lock:
            # Broadcast del estado actual (sin modificar, solo mostrar)
            for username, session in list(shared_state.charging_sessions.items()):
                # Los datos vienen del CP_E vía Kafka, no los calculamos aquí
                if shared_state.connected_clients:
                    message = json.dumps({
                        'type': 'charging_update',
                        'username': username,
                        'energy': round(session.get('energy', 0.0), 2),
                        'cost': round(session.get('cost', 0.0), 2)
                    })
                    
                    disconnected_clients = set()
                    for client in shared_state.connected_clients:
                        try:
                            # Compatibilidad con aiohttp WebSockets
                            if hasattr(client, 'send_str'):
                                await client.send_str(message)
                            else:
                                await client.send(message)
                        except:
                            disconnected_clients.add(client)
                    
                    # Remover clientes desconectados
                    for client in disconnected_clients:
                        shared_state.connected_clients.discard(client)

async def main():
    """Función principal que inicia todos los servicios"""
    local_ip = get_local_ip()
    
    print("\n" + "=" * 80)
    print(" " * 25 + "EV DRIVER - WebSocket Server")
    print("=" * 80)
    print(f"  Local Access:     http://localhost:{SERVER_PORT}")
    print(f"  Network Access:   http://{local_ip}:{SERVER_PORT}")
    print(f"  WebSocket:        ws://{local_ip}:{SERVER_PORT}/ws")
    print(f"   Database:         ev_charging.db")
    print(f"  Kafka Broker:     {KAFKA_BROKER}")
    print(f"  Publishing:       {KAFKA_TOPIC_PRODUCE}")
    print(f"  Central Server:   {DRIVER_CONFIG['central_ip']}:{DRIVER_CONFIG['central_port']}")
    print("=" * 80)
    print("\nLogin credentials:")
    print("  driver1 / pass123   (Balance: €150.00)")
    print("  driver2 / pass456   (Balance: €200.00)")
    print("  maria_garcia / maria2025  (Balance: €180.00)")
    print("=" * 80)
    print(f"\n   Access from other PCs: http://{local_ip}:{SERVER_PORT}")
    print(f"   Make sure firewall allows port {SERVER_PORT}")
    print(f"   Kafka broker must be running at: {KAFKA_BROKER}")
    print("=" * 80 + "\n")
    
    if not WS_AVAILABLE:
        print("ERROR: WebSocket dependencies not installed")
        print("Run: pip install websockets aiohttp")
        return
    
    # Inicializar base de datos si no existe
    # En Docker: /app/ev_charging.db
    # Fuera de Docker: ../ev_charging.db
    if Path('/app/ev_charging.db').exists():
        db_path = Path('/app/ev_charging.db')
    elif (Path(__file__).parent.parent / 'ev_charging.db').exists():
        db_path = Path(__file__).parent.parent / 'ev_charging.db'
    else:
        db_path = None
    
    if not db_path or not db_path.exists():
        print(" Database not found. Please run: python init_db.py")
        return
    
    try:
        # Crear aplicación web que maneje tanto HTTP como WebSocket
        app = web.Application()
        app.router.add_get('/', serve_dashboard)
        app.router.add_get('/ws', websocket_handler_http)
        
        # Iniciar servidor
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', SERVER_PORT)
        await site.start()
        
        print(f"[HTTP] Server started on http://0.0.0.0:{SERVER_PORT}")
        print(f"[WS] WebSocket endpoint at ws://0.0.0.0:{SERVER_PORT}/ws")
        
        # Iniciar broadcast de actualizaciones
        broadcast_task = asyncio.create_task(broadcast_updates())
        # Iniciar procesador de notificaciones
        notification_task = asyncio.create_task(process_notifications())
        
        print("\n All services started successfully!")
        print(f" Open http://localhost:{SERVER_PORT} in your browser\n")
        
        # Mantener el servidor corriendo - ambas tareas en paralelo
        await asyncio.gather(broadcast_task, notification_task)
        
    except Exception as e:
        print(f"\nError starting server: {e}")

if __name__ == "__main__":
    # ========================================================================
    # ARGUMENTOS DE LÍNEA DE COMANDOS
    # ========================================================================
    parser = argparse.ArgumentParser(
        description='EV Driver - Aplicación del Conductor'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.environ.get('DRIVER_PORT', DRIVER_CONFIG['ws_port'])),
        help=f'Puerto del servidor WebSocket (default: {DRIVER_CONFIG["ws_port"]} o env DRIVER_PORT)'
    )
    parser.add_argument(
        '--kafka-broker',
        default=os.environ.get('KAFKA_BROKER', KAFKA_BROKER_DEFAULT),
        help='Kafka broker address (default: from env KAFKA_BROKER or config)'
    )
    parser.add_argument(
        '--central-ip',
        default=os.environ.get('CENTRAL_IP', 'localhost'),
        help='IP de Central (default: localhost o env CENTRAL_IP)'
    )
    
    args = parser.parse_args()
    
    # Actualizar configuración global (no necesita 'global' en el scope del módulo)
    SERVER_PORT = args.port
    KAFKA_BROKER = args.kafka_broker
    
    print(f"""
================================================================================
  EV DRIVER - Aplicación del Conductor
================================================================================
  WebSocket Port:  {SERVER_PORT}
  Kafka Broker:    {KAFKA_BROKER}
  Central IP:      {args.central_ip}
  Dashboard:       http://localhost:{SERVER_PORT}
================================================================================
""")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[DRIVER] Server stopped by user")
    except Exception as e:
        print(f"\nFatal error: {e}")
