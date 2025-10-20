import socket
import time
import sys
import os
import asyncio
import json
import threading
from pathlib import Path

# WebSocket y HTTP server
try:
    import websockets
    from aiohttp import web
    WS_AVAILABLE = True
except ImportError:
    print("[DRIVER] Warning: websockets or aiohttp not installed. Run: pip install websockets aiohttp")
    WS_AVAILABLE = False

# Kafka imports
from kafka import KafkaProducer

# Añadir el directorio padre al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network_config import DRIVER_CONFIG
from event_utils import generate_message_id, current_timestamp
import database as db

# Configuración
KAFKA_BROKER = 'localhost:9092'
KAFKA_TOPIC_PRODUCE = 'driver-events'
SERVER_PORT = 8001  # Un solo puerto para HTTP y WebSocket

# Estado global compartido
class SharedState:
    def __init__(self):
        self.connected_clients = set()
        self.current_user = None
        self.charging_session = None
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
        self.initialize_kafka()

    def initialize_kafka(self):
        """Inicializa el productor de Kafka"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_broker,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            print(f"[DRIVER] ✅ Kafka producer initialized")
        except Exception as e:
            print(f"[DRIVER] ⚠️  Warning: Kafka not available: {e}")

    def authenticate_user(self, username, password):
        """Autentica un usuario usando la base de datos"""
        try:
            user = db.authenticate_user(username, password)
            if user:
                print(f"[DRIVER] ✅ User {username} authenticated successfully")
                return {
                    'success': True,
                    'user': {
                        'id': user['id'],
                        'username': user['username'],
                        'email': user['email'],
                        'balance': user['balance'],
                        'role': user['role']
                    }
                }
            else:
                print(f"[DRIVER] ❌ Authentication failed for {username}")
                return {'success': False, 'message': 'Invalid credentials'}
        except Exception as e:
            print(f"[DRIVER] ❌ Auth error: {e}")
            return {'success': False, 'message': str(e)}

    def request_charging(self, username):
        """Solicita inicio de carga"""
        try:
            # Obtener usuario de la BD
            user = db.get_user_by_username(username)
            if not user:
                return {'success': False, 'message': 'User not found'}
            
            # Verificar balance mínimo
            if user['balance'] < 5.0:
                return {'success': False, 'message': 'Insufficient balance (min €5.00 required)'}
            
            # Obtener punto de carga disponible
            available_cps = db.get_available_charging_points()
            if not available_cps:
                return {'success': False, 'message': 'No charging points available'}
            
            cp = available_cps[0]
            
            # Crear sesión de carga
            correlation_id = generate_message_id()
            session_id = db.create_charging_session(user['id'], cp['cp_id'], correlation_id)
            
            if session_id:
                # Publicar evento en Kafka
                if self.producer:
                    event = {
                        'message_id': generate_message_id(),
                        'driver_id': self.driver_id,
                        'action': 'charging_started',
                        'username': username,
                        'cp_id': cp['cp_id'],
                        'session_id': session_id,
                        'timestamp': current_timestamp(),
                        'correlation_id': correlation_id
                    }
                    self.producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.driver_id.encode())
                    self.producer.flush()
                
                print(f"[DRIVER] ⚡ Charging session {session_id} started for {username} at {cp['cp_id']}")
                return {
                    'success': True,
                    'session_id': session_id,
                    'cp_id': cp['cp_id'],
                    'location': cp['location'],
                    'power_output': cp.get('max_power_kw', 22.0),
                    'tariff': cp.get('tariff_per_kwh', 0.30)
                }
            else:
                return {'success': False, 'message': 'Failed to create charging session'}
                
        except Exception as e:
            print(f"[DRIVER] ❌ Charging request error: {e}")
            return {'success': False, 'message': str(e)}

    def stop_charging(self, username):
        """Detiene la carga actual"""
        try:
            # Obtener sesión activa del usuario
            user = db.get_user_by_username(username)
            if not user:
                return {'success': False, 'message': 'User not found'}
            
            active_session = db.get_active_session_for_user(user['id'])
            if not active_session:
                return {'success': False, 'message': 'No active charging session'}
            
            # Simular energía cargada (en producción vendría del hardware)
            # Por ahora, calcular basado en tiempo transcurrido
            import random
            energy_kwh = random.uniform(5.0, 25.0)  # Simular entre 5 y 25 kWh
            
            # Finalizar sesión
            result = db.end_charging_session(active_session['id'], energy_kwh)
            
            if result['success']:
                # Publicar evento en Kafka
                if self.producer:
                    event = {
                        'message_id': generate_message_id(),
                        'driver_id': self.driver_id,
                        'action': 'charging_stopped',
                        'username': username,
                        'session_id': active_session['id'],
                        'energy_kwh': energy_kwh,
                        'cost': result['cost'],
                        'timestamp': current_timestamp(),
                        'correlation_id': active_session.get('correlation_id', '')
                    }
                    self.producer.send(KAFKA_TOPIC_PRODUCE, event, key=self.driver_id.encode())
                    self.producer.flush()
                
                print(f"[DRIVER] ⛔ Charging stopped: {energy_kwh:.2f} kWh, €{result['cost']:.2f}")
                return {
                    'success': True,
                    'energy': energy_kwh,
                    'total_cost': result['cost'],
                    'new_balance': result['new_balance']
                }
            else:
                return {'success': False, 'message': result.get('message', 'Failed to stop charging')}
                
        except Exception as e:
            print(f"[DRIVER] ❌ Stop charging error: {e}")
            return {'success': False, 'message': str(e)}

    def get_session_status(self, username):
        """Obtiene el estado de la sesión actual del usuario"""
        try:
            user = db.get_user_by_username(username)
            if not user:
                return None
            
            active_session = db.get_active_session_for_user(user['id'])
            return active_session
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
                    with shared_state.lock:
                        shared_state.current_user = result['user']
                    
                    await websocket.send(json.dumps({
                        'type': 'login_response',
                        'success': True,
                        'user': result['user']
                    }))
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
                
                if result['success']:
                    with shared_state.lock:
                        shared_state.charging_session = {
                            'username': username,
                            'session_id': result['session_id'],
                            'cp_id': result['cp_id'],
                            'start_time': time.time(),
                            'energy': 0.0,
                            'cost': 0.0,
                            'tariff': result['tariff']
                        }
                    
                    await websocket.send(json.dumps({
                        'type': 'charging_started',
                        'cp_id': result['cp_id'],
                        'location': result['location'],
                        'power_output': result['power_output'],
                        'tariff': result['tariff']
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
                        shared_state.charging_session = None
                    
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
                            with shared_state.lock:
                                shared_state.current_user = result['user']
                            
                            await ws.send_str(json.dumps({
                                'type': 'login_response',
                                'success': True,
                                'user': result['user']
                            }))
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
                        
                        if result['success']:
                            with shared_state.lock:
                                shared_state.charging_session = {
                                    'username': username,
                                    'session_id': result['session_id'],
                                    'cp_id': result['cp_id'],
                                    'start_time': time.time(),
                                    'energy': 0.0,
                                    'cost': 0.0,
                                    'tariff': result['tariff']
                                }
                            
                            await ws.send_str(json.dumps({
                                'type': 'charging_started',
                                'session_id': result['session_id'],
                                'cp_id': result['cp_id'],
                                'location': result['location'],
                                'power_output': result['power_output'],
                                'tariff': result['tariff']
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
                                shared_state.charging_session = None
                            
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

async def broadcast_updates():
    """Simula actualizaciones de carga y las broadcast a todos los clientes"""
    while True:
        await asyncio.sleep(2)
        
        with shared_state.lock:
            if shared_state.charging_session:
                # Simular incremento de energía basado en tiempo transcurrido
                elapsed = time.time() - shared_state.charging_session['start_time']
                # Simular carga a 7.4 kW (carga lenta típica)
                shared_state.charging_session['energy'] = (elapsed / 3600) * 7.4  # kWh
                shared_state.charging_session['cost'] = shared_state.charging_session['energy'] * shared_state.charging_session['tariff']
                
                # Broadcast a todos los clientes conectados
                if shared_state.connected_clients:
                    message = json.dumps({
                        'type': 'charging_update',
                        'energy': round(shared_state.charging_session['energy'], 2),
                        'cost': round(shared_state.charging_session['cost'], 2)
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
    print("\n" + "=" * 70)
    print(" " * 20 + "🚗 EV DRIVER - WebSocket Server")
    print("=" * 70)
    print(f"  📱 Dashboard URL:  http://localhost:{SERVER_PORT}")
    print(f"  🔌 WebSocket URL:  ws://localhost:{SERVER_PORT}/ws")
    print(f"  💾 Database:       ev_charging.db")
    print(f"  📡 Kafka Broker:   {KAFKA_BROKER}")
    print("=" * 70)
    print("\n🔐 Login credentials:")
    print("  driver1 / pass123   (Balance: €150.00)")
    print("  driver2 / pass456   (Balance: €200.00)")
    print("  maria_garcia / maria2025  (Balance: €180.00)")
    print("=" * 70 + "\n")
    
    if not WS_AVAILABLE:
        print("❌ ERROR: WebSocket dependencies not installed")
        print("Run: pip install websockets aiohttp")
        return
    
    # Inicializar base de datos si no existe
    db_path = Path(__file__).parent.parent / 'ev_charging.db'
    if not db_path.exists():
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
        
        print("\n All services started successfully!")
        print(f" Open http://localhost:{SERVER_PORT} in your browser\n")
        
        # Mantener el servidor corriendo
        await broadcast_task
        
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[DRIVER] 🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
