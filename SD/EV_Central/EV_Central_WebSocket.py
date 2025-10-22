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
from network_config import CENTRAL_CONFIG, KAFKA_BROKER as KAFKA_BROKER_DEFAULT, KAFKA_TOPICS
from event_utils import generate_message_id, current_timestamp
import database as db

# Configuración desde network_config o variables de entorno (Docker)
KAFKA_BROKER = os.environ.get('KAFKA_BROKER', KAFKA_BROKER_DEFAULT)
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

    def _normalize_status(self, status: str) -> str:
        s = (status or '').lower()
        if s == 'unavailable':
            return 'offline'
        if s == 'error':
            return 'fault'
        if s in ('maintenance', 'out_of_order'):
            return 'out_of_service'
        return status

    def _standardize_cp(self, cp_row: dict) -> dict:
        """Transforma filas de BD español a claves que espera UI."""
        return {
            'cp_id': cp_row.get('cp_id'),
            'location': cp_row.get('location') or cp_row.get('localizacion') or cp_row.get('Location') or cp_row.get('LOCALIZACION') or '',
            'status': self._normalize_status(cp_row.get('status')),
            'max_power_kw': cp_row.get('max_power_kw'),
            'tariff_per_kwh': cp_row.get('tariff_per_kwh'),
            'active': cp_row.get('active', 1),
            'power_output': cp_row.get('max_power_kw')
        }

    def _standardize_user(self, u: dict) -> dict:
        """Transforma filas de usuarios español a claves UI."""
        return {
            'id': u.get('id'),
            'username': u.get('nombre'),
            'email': u.get('email'),
            'role': u.get('role'),
            'balance': u.get('balance', 0.0),
            'is_active': bool(u.get('active', 1))
        }

    def _standardize_session(self, s: dict) -> dict:
        """Transforma filas de sesiones español a claves UI."""
        return {
            'id': s.get('id'),
            'session_id': s.get('id'),
            'username': s.get('username'),
            'cp_id': s.get('cp_id'),
            'energy': s.get('energy', 0),
            'cost': s.get('cost', 0),
            'start_time': s.get('start_time')
        }

    def get_dashboard_data(self):
        """Obtiene todos los datos para el dashboard administrativo"""
        try:
            # Obtener usuarios
            users = []
            try:
                users_raw = db.get_all_users() if hasattr(db, 'get_all_users') else []
                users = [self._standardize_user(u) for u in users_raw]
            except Exception:
                users = []
            
            # Obtener puntos de carga y estandarizar campos
            cps_raw = db.get_all_charging_points() if hasattr(db, 'get_all_charging_points') else []
            charging_points = [self._standardize_cp(cp) for cp in cps_raw]
            
            # Sesiones activas
            active_sessions_raw = []
            try:
                conn = db.get_connection()
                cur = conn.cursor()
                cur.execute("""
                    SELECT s.id, s.cp_id, s.start_time, u.nombre as username
                    FROM charging_sesiones s
                    JOIN usuarios u ON s.user_id = u.id
                    WHERE s.estado = 'active'
                    ORDER BY s.start_time DESC
                """)
                active_sessions_raw = [dict(r) for r in cur.fetchall()]
                conn.close()
            except Exception:
                active_sessions_raw = []

            active_sessions = []
            for session in active_sessions_raw:
                # Calcular energía y costo simulado basado en tiempo
                start_time = datetime.fromtimestamp(session['start_time'])
                elapsed_hours = (datetime.now() - start_time).total_seconds() / 3600
                energy = elapsed_hours * 7.4  # Simular 7.4 kW
                
                # Obtener tarifa del CP
                cp_row = db.get_charging_point_by_id(session['cp_id']) if hasattr(db, 'get_charging_point_by_id') else None
                tariff = cp_row.get('tariff_per_kwh', 0.30) if cp_row else 0.30
                cost = energy * tariff
                
                std_session = self._standardize_session(session)
                std_session['energy'] = round(energy, 2)
                std_session['cost'] = round(cost, 2)
                active_sessions.append(std_session)
            
            # Calcular estadísticas
            today = datetime.now().date()
            try:
                if hasattr(db, 'get_sessions_by_date'):
                    today_sessions = db.get_sessions_by_date(today)
                elif hasattr(db, 'get_sesiones_by_date'):
                    today_sessions = db.get_sesiones_by_date(today)
                else:
                    today_sessions = []
            except Exception:
                today_sessions = []
            # Sumatorio robusto del ingreso de hoy (acepta claves en EN/ES)
            def _get_cost_val(s):
                return s.get('total_cost') or s.get('total_coste') or s.get('coste') or s.get('cost') or 0
            today_revenue = sum(_get_cost_val(s) for s in today_sessions if _get_cost_val(s))
            
            # Contar usuarios activos (drivers)
            driver_users = [u for u in users if u.get('role') == 'driver']
            
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
                    
                    elif msg_type == 'get_all_cps':
                        # Obtener todos los puntos de carga
                        cps = [central_instance._standardize_cp(cp) for cp in (db.get_all_charging_points() if hasattr(db, 'get_all_charging_points') else [])]
                        await ws.send_str(json.dumps({
                            'type': 'all_cps',
                            'charging_points': cps
                        }))
                    
                    elif msg_type == 'simulate_error':
                        # Simular error en un punto de carga
                        cp_id = data.get('cp_id')
                        error_type = data.get('error_type')
                        
                        # Mapear tipo de error a estado
                        status_map = {
                            'fault': 'fault',
                            'out_of_service': 'out_of_service',
                            'offline': 'offline'
                        }
                        new_status = status_map.get(error_type, 'fault')
                        
                        # Actualizar estado en BD
                        db.update_charging_point_status(cp_id, new_status)
                        
                        # Enviar confirmación
                        await ws.send_str(json.dumps({
                            'type': 'error_simulated',
                            'message': f'Error "{error_type}" simulado en {cp_id}'
                        }))
                        
                        # Broadcast a todos los clientes
                        cps = [central_instance._standardize_cp(cp) for cp in (db.get_all_charging_points() if hasattr(db, 'get_all_charging_points') else [])]
                        for client in shared_state.connected_clients:
                            if client != ws:
                                try:
                                    await client.send_str(json.dumps({
                                        'type': 'all_cps',
                                        'charging_points': cps
                                    }))
                                except:
                                    pass
                    
                    elif msg_type == 'fix_error':
                        # Corregir error en un punto de carga
                        cp_id = data.get('cp_id')
                        
                        # Cambiar estado a available
                        db.update_charging_point_status(cp_id, 'available')
                        
                        # Enviar confirmación
                        await ws.send_str(json.dumps({
                            'type': 'error_fixed',
                            'message': f'Error corregido en {cp_id}'
                        }))
                        
                        # Broadcast a todos los clientes
                        cps = [central_instance._standardize_cp(cp) for cp in (db.get_all_charging_points() if hasattr(db, 'get_all_charging_points') else [])]
                        for client in shared_state.connected_clients:
                            if client != ws:
                                try:
                                    await client.send_str(json.dumps({
                                        'type': 'all_cps',
                                        'charging_points': cps
                                    }))
                                except:
                                    pass
                    
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
                print(f"[KAFKA] 📨 Received event: {event.get('event_type', 'UNKNOWN')} from topic: {message.topic}")
                # Persistir inmediatamente registros de CP para mayor fiabilidad del Test A
                try:
                    et = event.get('event_type', '')
                    action = event.get('action', '')
                    cp_id = event.get('cp_id') or event.get('engine_id')
                    if cp_id and (et == 'CP_REGISTRATION' or action == 'connect'):
                        data = event.get('data', {}) if isinstance(event.get('data'), dict) else {}
                        localizacion = data.get('localizacion') or data.get('location') or 'Desconocido'
                        max_kw = data.get('max_kw') or data.get('max_power_kw') or 22.0
                        tarifa_kwh = data.get('tarifa_kwh') or data.get('tariff_per_kwh') or data.get('price_eur_kwh') or 0.30
                        if hasattr(db, 'register_or_update_charging_point'):
                            db.register_or_update_charging_point(cp_id, localizacion, max_kw=max_kw, tarifa_kwh=tarifa_kwh, estado='available')
                            print(f"[CENTRAL] 💾 CP registrado/actualizado (pre-broadcast): {cp_id}")
                    # Si llega cambio de estado pero el CP no existe, crearlo mínimo
                    if cp_id and action == 'cp_status_change':
                        try:
                            cp_row = db.get_charging_point_by_id(cp_id)
                            if not cp_row:
                                status = event.get('status', 'available')
                                if hasattr(db, 'register_or_update_charging_point'):
                                    db.register_or_update_charging_point(cp_id, 'Desconocido', max_kw=22.0, tarifa_kwh=0.30, estado=status)
                                    print(f"[CENTRAL] 💾 CP auto-creado por status_change: {cp_id}")
                        except Exception as ie:
                            print(f"[CENTRAL] ⚠️ Error auto-creando CP por status_change: {ie}")
                except Exception as e:
                    print(f"[CENTRAL] ⚠️ Error persistiendo registro de CP: {e}")
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
    print(f"[KAFKA] 🔄 Processing event for broadcast: {event.get('event_type', 'UNKNOWN')}, clients: {len(shared_state.connected_clients)}")
    
    # Determinar el tipo de evento y formatearlo para el dashboard
    action = event.get('action', '')
    event_type = event.get('event_type', '')
    
    # Primero: persistir cambios de estado relevantes SIEMPRE (aunque no haya clientes conectados)
    cp_id = event.get('cp_id') or event.get('engine_id')
    if cp_id:
        if action in ['connect'] or event_type in ['CP_REGISTRATION']:
            # Auto-registro/actualización del CP al conectar
            try:
                cp = db.get_charging_point_by_id(cp_id)
                data = event.get('data', {}) if isinstance(event.get('data'), dict) else {}
                localizacion = data.get('localizacion') or data.get('location') or 'Desconocido'
                max_kw = data.get('max_kw') or data.get('max_power_kw') or 22.0
                tarifa_kwh = data.get('tarifa_kwh') or data.get('tariff_per_kwh') or data.get('price_eur_kwh') or 0.30
                estado = 'available'
                print(f"[CENTRAL] 🆕 Auto-reg CP on connect: cp_id={cp_id}, loc={localizacion}, max_kw={max_kw}, tarifa={tarifa_kwh}")
                # Registrar o actualizar
                if hasattr(db, 'register_or_update_charging_point'):
                    db.register_or_update_charging_point(cp_id, localizacion, max_kw=max_kw, tarifa_kwh=tarifa_kwh, estado=estado)
                else:
                    # Fallback: intentar solo actualizar estado
                    db.update_charging_point_status(cp_id, estado)
                # Confirmar existencia
                cp_after = db.get_charging_point_by_id(cp_id)
                if cp_after:
                    print(f"[CENTRAL] ✅ CP registrado/actualizado: {cp_after['cp_id']} en {cp_after.get('location','')} estado={cp_after.get('status','')}" )
                else:
                    print(f"[CENTRAL] ⚠️ No se pudo verificar CP {cp_id} tras auto-registro")
            except Exception as e:
                print(f"[CENTRAL] ⚠️ Error auto-registrando CP {cp_id}: {e}")
        elif action in ['charging_started']:
            # Marcar CP como en carga
            db.update_charging_point_status(cp_id, 'charging')
        elif action in ['charging_stopped']:
            # Marcar CP disponible
            db.update_charging_point_status(cp_id, 'available')
        elif action in ['cp_status_change']:
            status = event.get('status')
            if status:
                # Asegurar CP existe antes de actualizar
                try:
                    if not db.get_charging_point_by_id(cp_id) and hasattr(db, 'register_or_update_charging_point'):
                        db.register_or_update_charging_point(cp_id, 'Desconocido', max_kw=22.0, tarifa_kwh=0.30, estado=status)
                        print(f"[CENTRAL] 🆕 CP auto-creado en cp_status_change: {cp_id}")
                except Exception as e:
                    print(f"[CENTRAL] ⚠️ Error asegurando CP en cp_status_change: {e}")
                db.update_charging_point_status(cp_id, status)
        elif action in ['cp_error_simulated', 'cp_error_fixed']:
            new_status = event.get('new_status') or event.get('status')
            if new_status:
                db.update_charging_point_status(cp_id, new_status)

    # Si no hay clientes conectados, no hace falta construir ni enviar mensajes
    if not shared_state.connected_clients:
        print(f"[KAFKA] ⚠️  No clients connected, skipping broadcast")
        return

    # Crear mensaje según el tipo de acción
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
        # Para cualquier otro evento, enviar como evento genérico del sistema
        # Esto captura TODOS los eventos de Kafka para mostrar en el stream
        event_desc = f"{event_type or 'EVENT'}"
        if 'username' in event:
            event_desc += f" - Usuario: {event['username']}"
        if 'cp_id' in event:
            event_desc += f" - CP: {event['cp_id']}"
        if 'data' in event and isinstance(event['data'], dict):
            event_desc += f" - {event['data']}"
            
        message = json.dumps({
            'type': 'kafka_event',
            'event_type': event_type,
            'message': event_desc,
            'raw_event': event
        })
        print(f"[KAFKA] 📤 Broadcasting generic event: {event_desc}")
    
    # Broadcast a todos los clientes (compat websockets y aiohttp)
    disconnected_clients = set()
    for client in shared_state.connected_clients:
        try:
            if hasattr(client, 'send_str'):
                await client.send_str(message)
            else:
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
    else:
        # Requisito: al iniciar Central TODO debe estar apagado
        try:
            # 1) Terminar cualquier sesión activa que haya quedado de ejecuciones anteriores
            if hasattr(db, 'terminate_all_active_sessions'):
                sess, cps = db.terminate_all_active_sessions(mark_cp_offline=True)
                print(f"[CENTRAL] � Inicio: sesiones activas terminadas: {sess}, CPs marcados offline: {cps}")
            # 2) Marcar TODOS los CPs como offline por defecto
            updated = db.set_all_cps_status_offline() if hasattr(db, 'set_all_cps_status_offline') else 0
            print(f"[CENTRAL] � CPs marcados como 'offline' al inicio: {updated}")
        except Exception as e:
            print(f"[CENTRAL] ⚠️ No se pudo limpiar estado al inicio: {e}")
    
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
        # Al apagar CENTRAL, terminar todas las sesiones activas y marcar CPs offline
        try:
            if hasattr(db, 'terminate_all_active_sessions'):
                sess, cps = db.terminate_all_active_sessions(mark_cp_offline=True)
                print(f"\n[CENTRAL] 🔌 Shutdown cleanup -> sessions terminated: {sess}, CPs set offline: {cps}")
        except Exception as e:
            print(f"\n[CENTRAL] ⚠️ Shutdown cleanup error: {e}")
        print("\n[CENTRAL] 🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
