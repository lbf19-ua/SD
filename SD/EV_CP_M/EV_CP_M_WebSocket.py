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
from network_config import MONITOR_CONFIG
from event_utils import generate_message_id, current_timestamp
import database as db

# Configuración
KAFKA_BROKER = 'localhost:9092'
KAFKA_TOPICS_CONSUME = ['cp-events', 'central-events']
KAFKA_TOPIC_PRODUCE = 'monitor-events'
SERVER_PORT = 8003
SERVER_PORT = 8003

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
                # Obtener métricas simuladas
                metrics = shared_state.cp_metrics.get(cp['cp_id'], {})
                
                # Calcular uptime
                uptime_seconds = time.time() - metrics.get('uptime_start', time.time())
                hours = int(uptime_seconds // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                uptime = f"{hours}h {minutes}m"
                
                # Determinar potencia actual basada en estado
                current_power = 0.0
                max_power = cp.get('max_power_kw', 22.0)
                if cp['status'] == 'charging':
                    current_power = max_power * random.uniform(0.85, 0.95)
                
                charging_points.append({
                    'cp_id': cp['cp_id'],
                    'location': cp['location'],
                    'power_output': max_power,
                    'tariff': cp.get('tariff_per_kwh', 0.30),
                    'status': cp['status'],
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
        await asyncio.sleep(3)  # Cada 3 segundos
        
        # Simular actualización de métricas
        monitor_instance.simulate_metrics_update()
        
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
    print("\n" + "=" * 70)
    print(" " * 16 + "📊 EV CHARGING POINT - Monitor WebSocket Server")
    print("=" * 70)
    print(f"  📱 Dashboard URL:  http://localhost:{SERVER_PORT}")
    print(f"  🔌 WebSocket URL:  ws://localhost:{SERVER_PORT}/ws")
    print(f"  💾 Database:       ev_charging.db")
    print(f"  📡 Kafka Broker:   {KAFKA_BROKER}")
    print("=" * 70 + "\n")
    
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
