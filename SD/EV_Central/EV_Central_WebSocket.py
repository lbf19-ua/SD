import sys
import os
import asyncio
import json
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta

# WebSocket y HTTP server
try:
    import websockets
    from aiohttp import web
    WS_AVAILABLE = True
except ImportError:
    print("[CENTRAL] Warning: websockets or aiohttp not installed. Run: pip install websockets aiohttp")
    WS_AVAILABLE = False

# Kafka imports
from kafka import KafkaProducer, KafkaConsumer

# Añadir el directorio padre al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network_config import CENTRAL_CONFIG, KAFKA_BROKER, KAFKA_TOPICS
from event_utils import generate_message_id, current_timestamp
import database as db

# Configuración desde network_config
KAFKA_TOPICS_CONSUME = [KAFKA_TOPICS['driver_events'], KAFKA_TOPICS['cp_events']]
KAFKA_TOPIC_PRODUCE = KAFKA_TOPICS['central_events']
SERVER_PORT = CENTRAL_CONFIG['ws_port']

# Estado global compartido
class SharedState:
    def __init__(self):
        self.connected_clients = set()
        self.lock = threading.Lock()

shared_state = SharedState()

class EV_CentralWS:
    """Versión de EV_Central con soporte WebSocket para la interfaz web"""
    
    def __init__(self, kafka_broker='localhost:9092'):
        self.kafka_broker = kafka_broker
        self.producer = None
        self.consumer = None
        self.initialize_kafka()

    def initialize_kafka(self):
        """Inicializa el productor de Kafka"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_broker,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            print(f"[CENTRAL] ✅ Kafka producer initialized")
        except Exception as e:
            print(f"[CENTRAL] ⚠️  Warning: Kafka not available: {e}")

    def get_dashboard_data(self):
        """Obtiene todos los datos para el dashboard administrativo"""
        try:
            # Obtener usuarios
            users = db.get_all_users()
            
            # Obtener puntos de carga
            charging_points = db.get_all_charging_points()
            
            # Obtener sesiones activas
            active_sessions_raw = db.get_active_sessions()
            active_sessions = []
            
            for session in active_sessions_raw:
                # Calcular energía y costo simulado basado en tiempo
                start_time = datetime.fromtimestamp(session['start_time'])
                elapsed_hours = (datetime.now() - start_time).total_seconds() / 3600
                energy = elapsed_hours * 7.4  # Simular 7.4 kW
                
                # Obtener tarifa del CP
                cp = db.get_charging_point_by_id(session['cp_id'])
                tariff = cp.get('tariff_per_kwh', 0.30) if cp else 0.30
                cost = energy * tariff
                
                active_sessions.append({
                    'session_id': session['id'],
                    'username': session['username'],
                    'cp_id': session['cp_id'],
                    'energy': round(energy, 2),
                    'cost': round(cost, 2),
                    'start_time': session['start_time']
                })
            
            # Calcular estadísticas
            today = datetime.now().date()
            today_sessions = db.get_sessions_by_date(today)
            today_revenue = sum(s['total_cost'] for s in today_sessions if s['total_cost'])
            
            # Contar usuarios activos (drivers)
            driver_users = [u for u in users if u['role'] == 'driver']
            
            stats = {
                'total_users': len(driver_users),
                'total_cps': len(charging_points),
                'active_sessions': len(active_sessions),
                'today_revenue': round(today_revenue, 2)
            }
            
            return {
                'users': users,
                'charging_points': charging_points,
                'active_sessions': active_sessions,
                'stats': stats
            }
            
        except Exception as e:
            print(f"[CENTRAL] ❌ Error getting dashboard data: {e}")
            return {
                'users': [],
                'charging_points': [],
                'active_sessions': [],
                'stats': {
                    'total_users': 0,
                    'total_cps': 0,
                    'active_sessions': 0,
                    'today_revenue': 0
                }
            }

    def publish_event(self, event_type, data):
        """Publica un evento en Kafka"""
        if self.producer:
            try:
                event = {
                    'message_id': generate_message_id(),
                    'event_type': event_type,
                    'data': data,
                    'timestamp': current_timestamp()
                }
                self.producer.send(KAFKA_TOPIC_PRODUCE, event)
                self.producer.flush()
            except Exception as e:
                print(f"[CENTRAL] ⚠️  Failed to publish event: {e}")

# Instancia global del central
central_instance = EV_CentralWS(kafka_broker=KAFKA_BROKER)

def get_local_ip():
    """Obtiene la IP local del sistema"""
    import socket
    try:
        # Crear un socket UDP (no se conecta realmente)
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
    print(f"[WS] 🔌 New admin client connected. Total clients: {len(shared_state.connected_clients)}")
    
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'get_dashboard_data':
                # Enviar datos del dashboard
                dashboard_data = central_instance.get_dashboard_data()
                await websocket.send(json.dumps({
                    'type': 'dashboard_data',
                    'data': dashboard_data
                }))
                    
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"[WS] ❌ Error handling websocket message: {e}")
    finally:
        shared_state.connected_clients.remove(websocket)
        print(f"[WS] ❌ Admin client disconnected. Total clients: {len(shared_state.connected_clients)}")

async def websocket_handler_http(request):
    """Manejador de WebSocket para aiohttp"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    client_id = id(ws)
    shared_state.connected_clients.add(ws)
    print(f"[WS] 🔌 New admin client connected. Total clients: {len(shared_state.connected_clients)}")
    
    try:
        # Enviar datos iniciales
        dashboard_data = central_instance.get_dashboard_data()
        await ws.send_str(json.dumps({
            'type': 'initial_data',
            'data': dashboard_data
        }))
        
        # Escuchar mensajes del cliente
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get('type')
                    
                    if msg_type == 'get_dashboard_data':
                        dashboard_data = central_instance.get_dashboard_data()
                        await ws.send_str(json.dumps({
                            'type': 'dashboard_data',
                            'data': dashboard_data
                        }))
                except json.JSONDecodeError:
                    print(f"[WS] ⚠️  Invalid JSON from {client_id}")
            elif msg.type == web.WSMsgType.ERROR:
                print(f"[WS] ⚠️  WebSocket error: {ws.exception()}")
                
    except Exception as e:
        print(f"[WS] ❌ Error with client {client_id}: {e}")
    finally:
        shared_state.connected_clients.discard(ws)
        print(f"[WS] ❌ Admin client disconnected. Total clients: {len(shared_state.connected_clients)}")
    
    return ws

async def serve_dashboard(request):
    """Sirve el archivo admin_dashboard.html"""
    dashboard_path = Path(__file__).parent / 'admin_dashboard.html'
    try:
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return web.Response(text=html_content, content_type='text/html')
    except FileNotFoundError:
        return web.Response(text="Admin dashboard not found", status=404)

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
    """Broadcast actualizaciones periódicas a todos los clientes"""
    while True:
        await asyncio.sleep(5)  # Cada 5 segundos
        
        if shared_state.connected_clients:
            dashboard_data = central_instance.get_dashboard_data()
            message = json.dumps({
                'type': 'dashboard_data',
                'data': dashboard_data
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

async def kafka_listener():
    """Escucha eventos de Kafka y los broadcast a los clientes WebSocket"""
    loop = asyncio.get_event_loop()
    
    def consume_kafka():
        """Función bloqueante que consume de Kafka"""
        try:
            consumer = KafkaConsumer(
                *KAFKA_TOPICS_CONSUME,
                bootstrap_servers=KAFKA_BROKER,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                group_id='ev_central_ws_group'
            )
            
            print(f"[KAFKA] 📡 Consumer started, listening to {KAFKA_TOPICS_CONSUME}")
            
            for message in consumer:
                event = message.value
                # Programar el broadcast en el event loop
                asyncio.run_coroutine_threadsafe(
                    broadcast_kafka_event(event),
                    loop
                )
                
        except Exception as e:
            print(f"[KAFKA] ⚠️  Consumer error: {e}")
    
    # Ejecutar el consumidor de Kafka en un thread separado
    kafka_thread = threading.Thread(target=consume_kafka, daemon=True)
    kafka_thread.start()

async def broadcast_kafka_event(event):
    """Broadcast un evento de Kafka a todos los clientes WebSocket"""
    if not shared_state.connected_clients:
        return
    
    # Determinar el tipo de evento y formatearlo para el dashboard
    action = event.get('action', '')
    
    if action == 'charging_started':
        message = json.dumps({
            'type': 'session_started',
            'username': event.get('username'),
            'cp_id': event.get('cp_id')
        })
    elif action == 'charging_stopped':
        message = json.dumps({
            'type': 'session_ended',
            'username': event.get('username'),
            'energy': event.get('energy_kwh'),
            'cost': event.get('cost')
        })
    elif action == 'cp_status_change':
        message = json.dumps({
            'type': 'cp_status_change',
            'cp_id': event.get('cp_id'),
            'status': event.get('status')
        })
    elif action == 'cp_error_simulated':
        message = json.dumps({
            'type': 'cp_error',
            'cp_id': event.get('cp_id'),
            'error_type': event.get('error_type'),
            'status': event.get('new_status'),
            'message': f"⚠️ Error simulado en {event.get('cp_id')}: {event.get('error_type')}"
        })
    elif action == 'cp_error_fixed':
        message = json.dumps({
            'type': 'cp_fixed',
            'cp_id': event.get('cp_id'),
            'status': event.get('new_status'),
            'message': f"✅ {event.get('cp_id')} reparado y disponible"
        })
    else:
        message = json.dumps({
            'type': 'system_event',
            'message': f"Event: {action}"
        })
    
    # Broadcast a todos los clientes
    disconnected_clients = set()
    for client in shared_state.connected_clients:
        try:
            await client.send(message)
        except:
            disconnected_clients.add(client)
    
    # Remover clientes desconectados
    for client in disconnected_clients:
        shared_state.connected_clients.discard(client)
    
    # Si es un evento de cambio de estado de CP, enviar datos completos actualizados
    if action in ['cp_error_simulated', 'cp_error_fixed', 'cp_status_change']:
        await broadcast_dashboard_data()

async def broadcast_dashboard_data():
    """Broadcast datos actualizados del dashboard a todos los clientes"""
    if not shared_state.connected_clients:
        return
    
    dashboard_data = central_instance.get_dashboard_data()
    message = json.dumps({
        'type': 'dashboard_data',
        'data': dashboard_data
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
    print(" " * 22 + "🏢 EV CENTRAL - Admin WebSocket Server")
    print("=" * 80)
    print(f"  🌐 Local Access:     http://localhost:{SERVER_PORT}")
    print(f"  🌍 Network Access:   http://{local_ip}:{SERVER_PORT}")
    print(f"  🔌 WebSocket:        ws://{local_ip}:{SERVER_PORT}/ws")
    print(f"  💾 Database:         ev_charging.db")
    print(f"  📡 Kafka Broker:     {KAFKA_BROKER}")
    print(f"  📨 Consuming:        {', '.join(KAFKA_TOPICS_CONSUME)}")
    print(f"  📤 Publishing:       {KAFKA_TOPIC_PRODUCE}")
    print("=" * 80)
    print(f"\n  ℹ️  Access from other PCs: http://{local_ip}:{SERVER_PORT}")
    print(f"  ⚠️  Make sure firewall allows port {SERVER_PORT}")
    print("=" * 80 + "\n")
    
    if not WS_AVAILABLE:
        print("❌ ERROR: WebSocket dependencies not installed")
        print("Run: pip install websockets aiohttp")
        return
    
    # Verificar base de datos
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
        
        print(f"[HTTP] 🌐 Server started on http://0.0.0.0:{SERVER_PORT}")
        print(f"[WS] 🔌 WebSocket endpoint at ws://0.0.0.0:{SERVER_PORT}/ws")
        
        # Iniciar broadcast de actualizaciones
        broadcast_task = asyncio.create_task(broadcast_updates())
        
        # Iniciar listener de Kafka
        kafka_task = asyncio.create_task(kafka_listener())
        
        print("\n✅ All services started successfully!")
        print(f"🌐 Open http://localhost:{SERVER_PORT} in your browser\n")
        
        # Mantener el servidor corriendo
        await asyncio.gather(broadcast_task, kafka_task)
        
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[CENTRAL] 🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
