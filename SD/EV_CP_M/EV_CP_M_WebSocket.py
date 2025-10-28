import sys
import os
import asyncio
import json
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
import random

# WebSocket y HTTP server
try:
    import websockets
    from aiohttp import web
    WS_AVAILABLE = True
except ImportError:
    print("[MONITOR] Warning: websockets or aiohttp not installed. Run: pip install websockets aiohttp")
    WS_AVAILABLE = False

# Kafka imports
from kafka import KafkaProducer, KafkaConsumer

# Añadir el directorio padre al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network_config import MONITOR_CONFIG, KAFKA_BROKER as KAFKA_BROKER_DEFAULT, KAFKA_TOPICS
from event_utils import generate_message_id, current_timestamp
import database as db

# Configuración desde network_config o variables de entorno (Docker)
KAFKA_BROKER = os.environ.get('KAFKA_BROKER', KAFKA_BROKER_DEFAULT)
KAFKA_TOPICS_CONSUME = [KAFKA_TOPICS['cp_events'], KAFKA_TOPICS['central_events']]
KAFKA_TOPIC_PRODUCE = KAFKA_TOPICS['monitor_events']
SERVER_PORT = MONITOR_CONFIG['ws_port']

# Estado global compartido
class SharedState:
    def __init__(self):
        self.connected_clients = set()
        self.cp_metrics = {}  # Métricas simuladas por CP
        self.alerts = []
        self.lock = threading.Lock()

shared_state = SharedState()

class EV_MonitorWS:
    """Versión del Monitor con soporte WebSocket para la interfaz web"""
    
    def __init__(self, kafka_broker='localhost:9092'):
        self.kafka_broker = kafka_broker
        self.producer = None
        self.initialize_kafka()
        self.initialize_metrics()

    def ensure_producer(self):
        """Asegura que el producer de Kafka esté disponible."""
        if self.producer is None:
            try:
                self.initialize_kafka()
            except Exception:
                return False
        return self.producer is not None

    def initialize_kafka(self):
        """Inicializa el productor de Kafka"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_broker,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            print(f"[MONITOR] ✅ Kafka producer initialized")
        except Exception as e:
            print(f"[MONITOR] ⚠️  Warning: Kafka not available: {e}")

    def publish_cp_event(self, event_type: str, data: dict):
        """Publica un evento del CP (cp-events) para que lo consuma la Central."""
        if not self.ensure_producer():
            print("[MONITOR] ❌ No Kafka producer available to publish cp-event")
            return False
        try:
            event = {
                'message_id': generate_message_id(),
                'event_type': event_type,
                **(data or {}),
                'timestamp': current_timestamp()
            }
            # Enviar al topic de CPs (no al de monitor)
            self.producer.send(KAFKA_TOPICS['cp_events'], event)
            self.producer.flush()
            print(f"[MONITOR] 📤 Published CP event: {event_type} -> cp-events: {data}")
            return True
        except Exception as e:
            print(f"[MONITOR] ⚠️  Failed to publish cp-event: {e}")
            return False

    def initialize_metrics(self):
        """Inicializa métricas simuladas para cada CP"""
        cps = db.get_all_charging_points()
        for cp in cps:
            shared_state.cp_metrics[cp['cp_id']] = {
                'temperature': 25.0,
                'efficiency': 100.0,
                'uptime_start': time.time(),
                'sessions_today': 0,
                'current_power': 0.0
            }

    def get_monitor_data(self):
        """Obtiene todos los datos para el dashboard de monitoreo"""
        try:
            # Obtener puntos de carga
            charging_points_raw = db.get_all_charging_points()
            charging_points = []
            
            for cp in charging_points_raw:
                # Mapear nombres de columnas de BD -> modelo del dashboard
                status = cp.get('estado', 'offline')
                location = cp.get('localizacion', '')
                max_power = cp.get('max_kw', 22.0)
                tariff = cp.get('tarifa_kwh', 0.30)

                # Obtener métricas simuladas
                metrics = shared_state.cp_metrics.get(cp['cp_id'], {})

                # Calcular uptime
                uptime_seconds = time.time() - metrics.get('uptime_start', time.time())
                hours = int(uptime_seconds // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                uptime = f"{hours}h {minutes}m"

                # Determinar potencia actual basada en estado
                current_power = 0.0
                if str(status).lower() == 'charging':
                    current_power = float(max_power) * random.uniform(0.85, 0.95)

                charging_points.append({
                    'cp_id': cp['cp_id'],
                    'location': location,
                    'power_output': max_power,
                    'tariff': tariff,
                    'status': status,
                    'temperature': metrics.get('temperature', 25.0),
                    'efficiency': metrics.get('efficiency', 100.0),
                    'uptime': uptime,
                    'sessions_today': metrics.get('sessions_today', 0),
                    'current_power': round(current_power, 1)
                })
            
            # Obtener alertas recientes
            alerts = shared_state.alerts[-10:]  # Últimas 10 alertas
            
            # Generar estadísticas de uso (últimas 24h)
            usage_stats = self.get_usage_stats()
            
            return {
                'charging_points': charging_points,
                'alerts': alerts,
                'usage_stats': usage_stats
            }
            
        except Exception as e:
            print(f"[MONITOR] ❌ Error getting monitor data: {e}")
            return {
                'charging_points': [],
                'alerts': [],
                'usage_stats': []
            }

    def get_usage_stats(self):
        """Genera estadísticas de uso de los últimos días"""
        # Simular datos de uso para el gráfico
        stats = []
        labels = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
        
        for label in labels:
            # Generar valor aleatorio entre 5 y 20 sesiones
            value = random.randint(5, 20)
            stats.append({
                'label': label,
                'value': value
            })
        
        return stats

    def add_alert(self, level, message):
        """Añade una alerta al sistema"""
        alert = {
            'level': level,  # 'critical', 'warning', 'info', 'success'
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        with shared_state.lock:
            shared_state.alerts.append(alert)
            # Mantener solo las últimas 50 alertas
            if len(shared_state.alerts) > 50:
                shared_state.alerts = shared_state.alerts[-50:]
        
        return alert

    def simulate_metrics_update(self):
        """Simula actualización de métricas de los CPs"""
        with shared_state.lock:
            for cp_id, metrics in shared_state.cp_metrics.items():
                # Simular variación de temperatura (23-28°C)
                metrics['temperature'] += random.uniform(-0.5, 0.5)
                metrics['temperature'] = max(23, min(28, metrics['temperature']))
                
                # Simular eficiencia (95-100%)
                metrics['efficiency'] += random.uniform(-1, 1)
                metrics['efficiency'] = max(95, min(100, metrics['efficiency']))

# Instancia global del monitor
monitor_instance = EV_MonitorWS(kafka_broker=KAFKA_BROKER)

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
    print(f"[WS] 🔌 New monitor client connected. Total clients: {len(shared_state.connected_clients)}")
    
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'get_monitor_data':
                # Enviar datos del monitor
                monitor_data = monitor_instance.get_monitor_data()
                await websocket.send(json.dumps({
                    'type': 'monitor_data',
                    'data': monitor_data
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
                    
                    if msg_type == 'get_monitor_data':
                        # Enviar datos del monitor
                        monitor_data = monitor_instance.get_monitor_data()
                        await ws.send_str(json.dumps({
                            'type': 'monitor_data',
                            'data': monitor_data
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
    """Sirve el archivo monitor_dashboard.html"""
    dashboard_path = Path(__file__).parent / 'monitor_dashboard.html'
    try:
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return web.Response(text=html_content, content_type='text/html')
    except FileNotFoundError:
        return web.Response(text="Monitor dashboard not found", status=404)

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
        await asyncio.sleep(1)  # Cada 1 segundo para telemetría
        
        # Simular actualización de métricas
        monitor_instance.simulate_metrics_update()
        
        # Publicar telemetría de CPs en carga hacia CENTRAL
        try:
            cps = db.get_all_charging_points()
            for cp in cps:
                status = (cp.get('estado') or cp.get('status') or '').lower()
                if status == 'charging':
                    cp_id = cp['cp_id']
                    max_kw = float(cp.get('max_kw') or cp.get('power_output') or 22.0)
                    # Calcular potencia actual (suave/aleatoria alrededor del 90%)
                    metrics = shared_state.cp_metrics.setdefault(cp_id, {
                        'temperature': 25.0,
                        'efficiency': 100.0,
                        'uptime_start': time.time(),
                        'sessions_today': 0,
                        'current_power': 0.0
                    })
                    # Suavizado de potencia
                    import random as _rnd
                    current_power = max_kw * _rnd.uniform(0.85, 0.95)
                    metrics['current_power'] = round(current_power, 2)

                    # Enviar evento de telemetría al topic cp-events
                    monitor_instance.publish_cp_event('CP_TELEMETRY', {
                        'action': 'cp_telemetry',
                        'cp_id': cp_id,
                        'power_kw': round(current_power, 2)
                    })
        except Exception as e:
            print(f"[MONITOR] ⚠️  Error publishing telemetry: {e}")
        
        if shared_state.connected_clients:
            monitor_data = monitor_instance.get_monitor_data()
            message = json.dumps({
                'type': 'monitor_data',
                'data': monitor_data
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
                group_id='ev_monitor_ws_group'
            )
            
            print(f"[KAFKA] 📡 Consumer started, listening to {KAFKA_TOPICS_CONSUME}")
            
            for message in consumer:
                event = message.value
                # Programar el procesamiento en el event loop
                asyncio.run_coroutine_threadsafe(
                    process_kafka_event(event),
                    loop
                )
                
        except Exception as e:
            print(f"[KAFKA] ⚠️  Consumer error: {e}")
    
    # Ejecutar el consumidor de Kafka en un thread separado
    kafka_thread = threading.Thread(target=consume_kafka, daemon=True)
    kafka_thread.start()

async def process_kafka_event(event):
    """Procesa eventos de Kafka y genera alertas"""
    action = event.get('action', '')
    event_type = event.get('event_type', '')
    
    if action == 'charging_started':
        cp_id = event.get('cp_id')
        username = event.get('username')
        alert = monitor_instance.add_alert(
            'info',
            f"✅ Carga iniciada en {cp_id} por {username}"
        )
        await broadcast_alert(alert)
        
    elif action == 'charging_stopped':
        cp_id = event.get('cp_id')
        username = event.get('username')
        energy = event.get('energy_kwh', 0)
        alert = monitor_instance.add_alert(
            'success',
            f"⛔ Carga completada en {cp_id}: {energy:.2f} kWh"
        )
        await broadcast_alert(alert)
        
    elif action == 'fault_detected':
        cp_id = event.get('cp_id')
        alert = monitor_instance.add_alert(
            'critical',
            f"🔴 Fallo detectado en {cp_id}"
        )
        await broadcast_alert(alert)
        
    elif action == 'cp_offline':
        cp_id = event.get('cp_id')
        alert = monitor_instance.add_alert(
            'warning',
            f"⚠️ {cp_id} fuera de línea"
        )
        await broadcast_alert(alert)
        
    elif action == 'cp_error_simulated':
        cp_id = event.get('cp_id')
        error_type = event.get('error_type', 'error')
        alert = monitor_instance.add_alert(
            'critical',
            f"🚨 Admin simuló {error_type} en {cp_id}"
        )
        await broadcast_alert(alert)
        # Actualizar dashboard inmediatamente
        await broadcast_monitor_data()
        
    elif action == 'cp_error_fixed':
        cp_id = event.get('cp_id')
        alert = monitor_instance.add_alert(
            'success',
            f"✅ Admin reparó {cp_id}, ahora disponible"
        )
        await broadcast_alert(alert)
        # Actualizar dashboard inmediatamente
        await broadcast_monitor_data()
    
    # Auto-ACK a peticiones de autorización del Central
    elif event_type == 'CP_AUTH_REQUEST':
        cp_id = event.get('cp_id')
        correlation_id = event.get('correlation_id')
        username = event.get('username')
        client_id = event.get('client_id')
        # Publicar ACK en cp-events para que lo consuma el Central
        published = monitor_instance.publish_cp_event('CP_AUTH_ACK', {
            'cp_id': cp_id,
            'correlation_id': correlation_id,
            'username': username,
            'client_id': client_id,
            'action': 'cp_auth_ack',
            'message': f'ACK de autorización en {cp_id} para {username}'
        })
        level = 'info' if published else 'warning'
        msg = f"🔐 ACK de autorización enviado por {cp_id} para usuario {username}" if published else f"⚠️ No se pudo enviar ACK de autorización para {cp_id}"
        alert = monitor_instance.add_alert(level, msg)
        await broadcast_alert(alert)

async def broadcast_alert(alert):
    """Broadcast una alerta a todos los clientes WebSocket"""
    if not shared_state.connected_clients:
        return
    
    message = json.dumps({
        'type': 'alert',
        'alert': alert
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

async def broadcast_monitor_data():
    """Broadcast datos actualizados del monitor a todos los clientes"""
    if not shared_state.connected_clients:
        return
    
    monitor_data = monitor_instance.get_monitor_data()
    message = json.dumps({
        'type': 'monitor_data',
        'data': monitor_data
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

async def check_cp_health():
    """Monitorea la salud de los CPs y genera alertas"""
    while True:
        await asyncio.sleep(30)  # Cada 30 segundos
        
        try:
            cps = db.get_all_charging_points()
            
            for cp in cps:
                # Detectar CPs offline (sin actividad reciente)
                if cp['status'] == 'available':
                    # Simular detección de fallos aleatorios (muy baja probabilidad)
                    if random.random() < 0.01:  # 1% de probabilidad
                        alert = monitor_instance.add_alert(
                            'warning',
                            f"⚠️ {cp['cp_id']} reporta baja eficiencia"
                        )
                        await broadcast_alert(alert)
                
        except Exception as e:
            print(f"[MONITOR] ❌ Error checking CP health: {e}")

async def main():
    """Función principal que inicia todos los servicios"""
    local_ip = get_local_ip()
    
    print("\n" + "=" * 80)
    print(" " * 18 + "📊 EV CHARGING POINT - Monitor WebSocket Server")
    print("=" * 80)
    print(f"  🌐 Local Access:     http://localhost:{SERVER_PORT}")
    print(f"  🌍 Network Access:   http://{local_ip}:{SERVER_PORT}")
    print(f"  🔌 WebSocket:        ws://{local_ip}:{SERVER_PORT}/ws")
    print(f"  💾 Database:         ev_charging.db")
    print(f"  📡 Kafka Broker:     {KAFKA_BROKER}")
    print(f"  📨 Consuming:        {', '.join(KAFKA_TOPICS_CONSUME)}")
    print(f"  📤 Publishing:       {KAFKA_TOPIC_PRODUCE}")
    print(f"  🏢 Central Server:   {MONITOR_CONFIG['central_ip']}:{MONITOR_CONFIG['central_port']}")
    print("=" * 80)
    print(f"\n  ℹ️  Access from other PCs: http://{local_ip}:{SERVER_PORT}")
    print(f"  ⚠️  Make sure firewall allows port {SERVER_PORT}")
    print(f"  ⚠️  Kafka broker must be running at: {KAFKA_BROKER}")
    print("=" * 80 + "\n")
    
    if not WS_AVAILABLE:
        print("❌ ERROR: WebSocket dependencies not installed")
        print("Run: pip install websockets aiohttp")
        return
    
    # Verificar base de datos
    db_path = Path(__file__).parent.parent / 'ev_charging.db'
    if not db_path.exists():
        print("⚠️  Database not found at /app/ev_charging.db. Attempting auto-initialize...")
        try:
            # Intentar crear e inicializar la base de datos con datos de prueba
            db.init_database()
            db.seed_test_data()
            if db_path.exists():
                print(f"[DB] ✅ Database created at {db_path}")
            else:
                print("[DB] ❌ Failed to create database file. Please ensure the volume is writable or create ev_charging.db on host.")
                # Continuar sin DB para levantar el dashboard (solo mostrará vacío)
        except Exception as e:
            print(f"[DB] ❌ Error initializing database automatically: {e}")
            # Continuar sin DB para levantar el dashboard (solo mostrará vacío)
    
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
        print("\n\n[MONITOR] 🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
