import socket
import time
import sys
import os
import asyncio
import json
import threading
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
KAFKA_BROKER = os.environ.get('KAFKA_BROKER', KAFKA_BROKER_DEFAULT)
KAFKA_TOPICS_CONSUME = [KAFKA_TOPICS['central_events']]
KAFKA_TOPIC_PRODUCE = KAFKA_TOPICS['driver_events']
SERVER_PORT = DRIVER_CONFIG['ws_port']

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

    def initialize_kafka(self):
        """Inicializa el productor de Kafka"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_broker,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            self.consumer = KafkaConsumer(
                *KAFKA_TOPICS_CONSUME,
                bootstrap_servers=self.kafka_broker,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                group_id=f'ev_driver_group_{self.driver_id}'
            )
            print(f"[DRIVER] ✅ Kafka producer and consumer initialized")
        except Exception as e:
            print(f"[DRIVER] ⚠️  Warning: Kafka not available: {e}")
            
    def kafka_listener(self):
        """Escucha mensajes de Kafka, especialmente las respuestas de autorización"""
        print(f"[KAFKA] 📡 Consumer started, listening to {KAFKA_TOPICS_CONSUME}")
        while True:
            try:
                for message in self.consumer:
                    event = message.value
                    event_type = event.get('event_type')
                    print(f"[KAFKA] 📨 Received {event_type} from Central")
                    
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
                                    print(f"[DRIVER] ✅ Central autorizó carga en {cp_id}")
                                    
                                    # Enviar evento para que CENTRAL cree la sesión (solo Central modifica BD)
                                    correlation_id = generate_message_id()
                                    if self.producer:
                                        start_event = {
                                            'message_id': generate_message_id(),
                                            'event_type': 'charging_started',
                                            'action': 'charging_started',
                                            'driver_id': self.driver_id,
                                            'username': username,
                                            'user_id': auth_data['user_id'],
                                            'cp_id': cp_id,
                                            'correlation_id': correlation_id,
                                            'timestamp': current_timestamp()
                                        }
                                        self.producer.send(KAFKA_TOPIC_PRODUCE, start_event)
                                        self.producer.flush()
                                        print(f"[DRIVER] 📤 Enviado evento charging_started a Central para sesión en {cp_id}")
                                        
                                        # Almacenar en estado local (sin BD)
                                        shared_state.charging_sessions[username] = {
                                            'username': username,
                                            'cp_id': cp_id,
                                            'start_time': time.time(),
                                            'energy': 0.0,
                                            'cost': 0.0,
                                            'tariff': 0.30  # Tariff por defecto
                                        }
                                        
                                        # Notificar al websocket que la carga ha iniciado
                                        # NO poner websocket en la queue, guardar client_id
                                        print(f"[DRIVER] 📬 Encolando notificación charging_started para {username}, client_id={client_id}")
                                        shared_state.notification_queue.put({
                                            'type': 'charging_started',
                                            'username': username,
                                            'cp_id': cp_id,
                                            'client_id': client_id
                                        })
                                    
                                    # NO limpiar pending_authorizations todavía
                                    # Lo limpiaremos después de enviar la notificación
                                else:
                                    print(f"[DRIVER] ❌ Central rechazó autorización: {reason}")
                                    # Notificar rechazo al websocket
                                    shared_state.notification_queue.put({
                                        'type': 'authorization_rejected',
                                        'username': username,
                                        'reason': reason,
                                        'client_id': client_id
                                    })
                                    
                                    # NO limpiar aún, se limpiará en el procesador
                
            except Exception as e:
                print(f"[KAFKA] ⚠️ Consumer error: {e}")
                # Intentar reconectar
                try:
                    self.consumer = KafkaConsumer(
                        *KAFKA_TOPICS_CONSUME,
                        bootstrap_servers=self.kafka_broker,
                        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                        auto_offset_reset='latest',
                        group_id=f'ev_driver_group_{self.driver_id}'
                    )
                except:
                    pass

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
            print(f"[DRIVER] ✅ User {username} authenticated successfully")
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
            print(f"[DRIVER] ❌ Authentication failed for {username}")
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
                print(f"[DRIVER] 🔐 Solicitando autorización a Central (asignación automática de CP)")
                
                # Datos simulados de usuario (solo para tracking local)
                users = {'driver1': {'id': 1}, 'driver2': {'id': 2}, 'maria_garcia': {'id': 3}}
                
                # Guardar solicitud pendiente
                with shared_state.lock:
                    shared_state.pending_authorizations[client_id] = {
                        'username': username,
                        'cp_id': cp_id,
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
            print(f"[DRIVER] ❌ Charging request error: {e}")
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
                print(f"[DRIVER] 🔐 Solicitando autorización a Central para {cp_id}")
                
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
            print(f"[DRIVER] ❌ Charging request (specific CP) error: {e}")
            return {'success': False, 'message': str(e)}

    def stop_charging(self, username):
        """Detiene la carga actual (enviar evento a Central para procesar en BD)"""
        try:
            # Verificar si hay sesión activa local
            with shared_state.lock:
                session_data = shared_state.charging_sessions.get(username)
                if not session_data:
                    return {'success': False, 'message': 'No active charging session'}
                
                cp_id = session_data.get('cp_id')
                import time
                duration = time.time() - session_data.get('start_time', time.time())
                # Simular energía cargada basado en tiempo
                import random
                energy_kwh = random.uniform(5.0, 25.0)
            
            # Publicar evento de STOP a Central para que finalice en BD
            if self.producer:
                event = {
                    'message_id': generate_message_id(),
                    'driver_id': self.driver_id,
                    'action': 'charging_stopped',
                    'username': username,
                    'cp_id': cp_id,
                    'energy_kwh': energy_kwh,
                    'timestamp': current_timestamp()
                }
                self.producer.send(KAFKA_TOPIC_PRODUCE, event)
                self.producer.flush()
                print(f"[DRIVER] ⛔ Solicitando detener carga en {cp_id} (Central procesará en BD)")
                
                # Limpiar sesión local
                with shared_state.lock:
                    if username in shared_state.charging_sessions:
                        del shared_state.charging_sessions[username]
                
                return {
                    'success': True,
                    'energy': energy_kwh,
                    'total_cost': energy_kwh * 0.30,  # Simulado
                    'new_balance': 150.0  # Simulado
                }
            else:
                return {'success': False, 'message': 'Sistema de mensajería no disponible'}
                
        except Exception as e:
            print(f"[DRIVER] ❌ Stop charging error: {e}")
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
            
            print(f"[DRIVER] ⚠️ Simulando {error_type} en {cp_id} (Central procesará en BD)")
            return {
                'success': True,
                'cp_id': cp_id,
                'error_type': error_type,
                'new_status': new_status
            }
            
        except Exception as e:
            print(f"[DRIVER] ❌ Simulate error failed: {e}")
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
            
            print(f"[DRIVER] ✅ Solicitando reparar {cp_id} (Central procesará en BD)")
            return {
                'success': True,
                'cp_id': cp_id,
                'new_status': 'available'
            }
            
        except Exception as e:
            print(f"[DRIVER] ❌ Fix error failed: {e}")
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
            print(f"[DRIVER] ❌ Get CPs error: {e}")
            return {'success': False, 'message': str(e)}

    def get_session_status(self, username):
        """Obtiene el estado de la sesión actual del usuario - desde estado local"""
        try:
            with shared_state.lock:
                if username in shared_state.charging_sessions:
                    return shared_state.charging_sessions[username]
            return None
        except Exception as e:
            print(f"[DRIVER] ❌ Get session status error: {e}")
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
    print(f"[WS] 🔌 New client connected. Total clients: {len(shared_state.connected_clients)}")
    
    try:
        async for message in websocket:
            data = json.loads(message)
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
                else:
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': result.get('message', 'Failed to start charging at CP')
                    }))

            elif msg_type == 'batch_charging':
                # Procesa una lista de CPs secuencialmente
                username = data.get('username')
                cp_ids = data.get('cp_ids') or []
                duration_sec = int(data.get('duration_sec') or 2)
                print(f"[DRIVER] 📄 Batch charging request: user={username}, CPs={cp_ids}, duration={duration_sec}s")
                await websocket.send(json.dumps({'type': 'batch_started', 'total': len(cp_ids)}))

                idx = 0
                for cp_id in cp_ids:
                    idx += 1
                    # Intentar iniciar
                    start_res = driver_instance.request_charging_at_cp(username, cp_id)
                    if not start_res.get('success'):
                        await websocket.send(json.dumps({
                            'type': 'batch_progress',
                            'index': idx,
                            'cp_id': cp_id,
                            'status': 'skipped',
                            'reason': start_res.get('message', 'unknown')
                        }))
                        continue

                    await websocket.send(json.dumps({
                        'type': 'batch_progress',
                        'index': idx,
                        'cp_id': cp_id,
                        'status': 'started',
                        'session_id': start_res['session_id']
                    }))
                    # Esperar duración
                    try:
                        await asyncio.sleep(max(0, duration_sec))
                    except Exception:
                        pass

                    stop_res = driver_instance.stop_charging(username)
                    if stop_res.get('success'):
                        await websocket.send(json.dumps({
                            'type': 'batch_progress',
                            'index': idx,
                            'cp_id': cp_id,
                            'status': 'stopped',
                            'energy': stop_res.get('energy'),
                            'total_cost': stop_res.get('total_cost')
                        }))
                    else:
                        await websocket.send(json.dumps({
                            'type': 'batch_progress',
                            'index': idx,
                            'cp_id': cp_id,
                            'status': 'stopped',
                            'error': stop_res.get('message')
                        }))

                await websocket.send(json.dumps({'type': 'batch_complete'}))
            
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
                    
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"[WS] ❌ Error handling websocket message: {e}")
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
                                        print(f"[WS] 💾 Websocket guardado para client_id={client_id}, user={username}")
                                    else:
                                        print(f"[WS] ⚠️ client_id={client_id} no existe en pending_authorizations")
                                
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
                        username = data.get('username')
                        cp_ids = data.get('cp_ids') or []
                        duration_sec = int(data.get('duration_sec') or 2)
                        await ws.send_str(json.dumps({'type': 'batch_started', 'total': len(cp_ids)}))

                        idx = 0
                        for cp_id in cp_ids:
                            idx += 1
                            start_res = driver_instance.request_charging_at_cp(username, cp_id)
                            if not start_res.get('success'):
                                await ws.send_str(json.dumps({
                                    'type': 'batch_progress',
                                    'index': idx,
                                    'cp_id': cp_id,
                                    'status': 'skipped',
                                    'reason': start_res.get('message', 'unknown')
                                }))
                                continue

                            await ws.send_str(json.dumps({
                                'type': 'batch_progress',
                                'index': idx,
                                'cp_id': cp_id,
                                'status': 'started',
                                'session_id': start_res['session_id']
                            }))
                            try:
                                await asyncio.sleep(max(0, duration_sec))
                            except Exception:
                                pass

                            stop_res = driver_instance.stop_charging(username)
                            if stop_res.get('success'):
                                await ws.send_str(json.dumps({
                                    'type': 'batch_progress',
                                    'index': idx,
                                    'cp_id': cp_id,
                                    'status': 'stopped',
                                    'energy': stop_res.get('energy'),
                                    'total_cost': stop_res.get('total_cost')
                                }))
                            else:
                                await ws.send_str(json.dumps({
                                    'type': 'batch_progress',
                                    'index': idx,
                                    'cp_id': cp_id,
                                    'status': 'stopped',
                                    'error': stop_res.get('message')
                                }))

                        await ws.send_str(json.dumps({'type': 'batch_complete'}))
                    
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
    print(f"[HTTP] 🌐 Server started on http://0.0.0.0:{SERVER_PORT}")

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
                
                print(f"[NOTIF] 📨 Procesando charging_started: user={username}, cp={cp_id}, client_id={client_id}")
                
                message = json.dumps({
                    'type': 'charging_started',
                    'username': username,
                    'cp_id': cp_id,
                    'message': f'Carga iniciada en {cp_id}'
                })
                
                # Buscar el websocket usando client_id
                sent = False
                with shared_state.lock:
                    print(f"[NOTIF] 🔍 Buscando websocket para client_id={client_id}")
                    print(f"[NOTIF] 📋 pending_authorizations keys: {list(shared_state.pending_authorizations.keys())}")
                    
                    if client_id and client_id in shared_state.pending_authorizations:
                        ws = shared_state.pending_authorizations[client_id].get('websocket')
                        print(f"[NOTIF] 🎯 Websocket encontrado: {ws is not None}")
                        
                        # Limpiar pending_authorizations
                        shared_state.pending_authorizations.pop(client_id, None)
                        
                        # Enviar al websocket específico
                        if ws:
                            try:
                                if hasattr(ws, 'send_str'):
                                    await ws.send_str(message)
                                else:
                                    await ws.send(message)
                                print(f"[NOTIF] ✅ Notificación enviada a {username} en {cp_id}")
                                sent = True
                            except Exception as e:
                                print(f"[NOTIF] Error enviando a {username}: {e}")
                        else:
                            print(f"[NOTIF] ⚠️ Websocket no encontrado para client_id {client_id}")
                    else:
                        print(f"[NOTIF] ⚠️ client_id {client_id} NO está en pending_authorizations")
                
                # Fallback: enviar a todos los clientes si no se envió
                if not sent:
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
                                print(f"[NOTIF] ❌ Rechazo enviado a {username}")
                                sent = True
                            except Exception as e:
                                print(f"[NOTIF] Error enviando rechazo a {username}: {e}")
                
                # Fallback: enviar a todos si no se envió
                if not sent:
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
                        
        except Exception as e:
            print(f"[NOTIF] Error processing notification: {e}")

async def broadcast_updates():
    """Simula actualizaciones de carga y las broadcast a todos los clientes"""
    while True:
        await asyncio.sleep(2)
        
        with shared_state.lock:
            # Actualizar TODAS las sesiones activas
            for username, session in list(shared_state.charging_sessions.items()):
                # Simular incremento de energía basado en tiempo transcurrido
                elapsed = time.time() - session['start_time']
                # Simular carga a 7.4 kW (carga lenta típica)
                session['energy'] = (elapsed / 3600) * 7.4  # kWh
                session['cost'] = session['energy'] * session['tariff']
                
                # Broadcast a todos los clientes conectados
                if shared_state.connected_clients:
                    message = json.dumps({
                        'type': 'charging_update',
                        'username': username,  # Incluir username para que el cliente filtre
                        'energy': round(session['energy'], 2),
                        'cost': round(session['cost'], 2)
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
    print(" " * 25 + "🚗 EV DRIVER - WebSocket Server")
    print("=" * 80)
    print(f"  🌐 Local Access:     http://localhost:{SERVER_PORT}")
    print(f"  🌍 Network Access:   http://{local_ip}:{SERVER_PORT}")
    print(f"  🔌 WebSocket:        ws://{local_ip}:{SERVER_PORT}/ws")
    print(f"  💾 Database:         ev_charging.db")
    print(f"  📡 Kafka Broker:     {KAFKA_BROKER}")
    print(f"  📤 Publishing:       {KAFKA_TOPIC_PRODUCE}")
    print(f"  🏢 Central Server:   {DRIVER_CONFIG['central_ip']}:{DRIVER_CONFIG['central_port']}")
    print("=" * 80)
    print("\n🔐 Login credentials:")
    print("  driver1 / pass123   (Balance: €150.00)")
    print("  driver2 / pass456   (Balance: €200.00)")
    print("  maria_garcia / maria2025  (Balance: €180.00)")
    print("=" * 80)
    print(f"\n  ℹ️  Access from other PCs: http://{local_ip}:{SERVER_PORT}")
    print(f"  ⚠️  Make sure firewall allows port {SERVER_PORT}")
    print(f"  ⚠️  Kafka broker must be running at: {KAFKA_BROKER}")
    print("=" * 80 + "\n")
    
    if not WS_AVAILABLE:
        print("❌ ERROR: WebSocket dependencies not installed")
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
        print("⚠️  Database not found. Please run: python init_db.py")
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
        print(f"\n❌ Error starting server: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[DRIVER] 🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
