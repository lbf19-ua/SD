import sys
import os
import asyncio
import json
import threading
import time
import argparse
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

# ============================================================================
# ARQUITECTURA CORRECTA: 1 Monitor por 1 Engine (relación 1:1)
# ============================================================================
# Estas variables se setean desde argumentos de línea de comandos
MONITORED_CP_ID = None  # ID del CP que este Monitor supervisa (ej: CP_001)
ENGINE_HOST = 'localhost'  # Host del Engine
ENGINE_PORT = 5100  # Puerto TCP del Engine
SERVER_PORT = 5500  # Puerto del dashboard de este Monitor

# Estado global compartido
class SharedState:
    def __init__(self):
        self.connected_clients = set()
        self.cp_metrics = {}  # Métricas del CP monitoreado
        self.alerts = []
        self.health_status = {  # Estado del health check del Engine
            'consecutive_failures': 0,
            'last_check': None,
            'last_status': 'UNKNOWN'
        }
        self.tcp_monitor_task = None  # Task de monitoreo TCP
        self.lock = threading.Lock()

shared_state = SharedState()

class EV_MonitorWS:
    """
    Monitor dedicado a supervisar UN ÚNICO Engine.
    
    ARQUITECTURA CORRECTA:
    - 1 Monitor ↔ 1 Engine (relación 1:1)
    - Cada CP tiene su propio par Engine+Monitor
    - El Monitor NO supervisa múltiples CPs
    """
    
    def __init__(self, cp_id, engine_host='localhost', engine_port=5100, kafka_broker='localhost:9092'):
        self.cp_id = cp_id
        self.engine_host = engine_host
        self.engine_port = engine_port
        self.kafka_broker = kafka_broker
        self.producer = None
        
        print(f"\n{'='*80}")
        print(f"  🏥 EV MONITOR - Supervising {self.cp_id}")
        print(f"{'='*80}")
        print(f"  Monitored CP:    {self.cp_id}")
        print(f"  Engine Host:     {self.engine_host}")
        print(f"  Engine Port:     {self.engine_port}")
        print(f"  Dashboard Port:  {SERVER_PORT}")
        print(f"{'='*80}\n")
        
        self.initialize_kafka()
        self.authenticate_with_central()
        self.initialize_metrics()

    def initialize_kafka(self):
        """Inicializa el productor de Kafka"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_broker,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            print(f"[MONITOR-{self.cp_id}] ✅ Kafka producer initialized")
        except Exception as e:
            print(f"[MONITOR-{self.cp_id}] ⚠️  Warning: Kafka not available: {e}")

    def authenticate_with_central(self):
        """
        Se conecta a EV_Central para autenticarse y validar que el Monitor
        está operativo y preparado para prestar servicios.
        
        Requisito del PDF: Al arrancar, el Monitor debe conectarse a Central
        para autenticarse y validar que está operativo.
        """
        print(f"[MONITOR-{self.cp_id}] 🔐 Authenticating with Central...")
        
        try:
            # Enviar mensaje de autenticación a Central vía Kafka
            auth_event = {
                'message_id': generate_message_id(),
                'event_type': 'MONITOR_AUTH',
                'action': 'authenticate',
                'cp_id': self.cp_id,
                'monitor_id': f'MONITOR-{self.cp_id}',
                'engine_host': self.engine_host,
                'engine_port': self.engine_port,
                'status': 'READY',
                'timestamp': current_timestamp()
            }
            
            if self.producer:
                self.producer.send(KAFKA_TOPIC_PRODUCE, auth_event)
                self.producer.flush()
                print(f"[MONITOR-{self.cp_id}] ✅ Authentication sent to Central")
                print(f"[MONITOR-{self.cp_id}] ✅ Monitor validated and ready to monitor {self.cp_id}")
            else:
                print(f"[MONITOR-{self.cp_id}] ⚠️  Cannot authenticate: Kafka not available")
        except Exception as e:
            print(f"[MONITOR-{self.cp_id}] ❌ Authentication failed: {e}")

    def initialize_metrics(self):
        """Inicializa métricas simuladas para el CP monitoreado"""
        shared_state.cp_metrics[self.cp_id] = {
            'temperature': 25.0,
            'efficiency': 100.0,
            'uptime_start': time.time(),
            'sessions_today': 0,
            'current_power': 0.0
        }
        print(f"[MONITOR-{self.cp_id}] 📊 Metrics initialized for {self.cp_id}")

    def get_monitor_data(self):
        """Obtiene datos del CP monitoreado para el dashboard"""
        try:
            # ========================================================================
            # SOLO obtener datos del CP que este Monitor supervisa
            # ========================================================================
            cp = db.get_charging_point_by_id(self.cp_id)
            if not cp:
                return {
                    'charging_point': None,
                    'alerts': shared_state.alerts[-50:],
                    'health_status': shared_state.health_status
                }
            
            # Obtener métricas simuladas
            metrics = shared_state.cp_metrics.get(self.cp_id, {})
            
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
            
            # Construir datos del CP monitoreado
            charging_point = {
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
            }
            
            # Obtener alertas recientes
            alerts = shared_state.alerts[-50:]  # Últimas 50 alertas
            
            return {
                'charging_point': charging_point,
                'alerts': alerts,
                'health_status': shared_state.health_status
            }
            
        except Exception as e:
            print(f"[MONITOR-{self.cp_id}] ❌ Error getting monitor data: {e}")
            return {
                'charging_point': None,
                'alerts': [],
                'health_status': shared_state.health_status
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

# Instancia global del monitor (se inicializa en main después de parsear argumentos)
monitor_instance = None

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

async def tcp_health_check():
    """
    ============================================================================
    MONITOREO TCP DEL ENGINE (1:1)
    ============================================================================
    Monitoreo TCP del Engine según especificación del PDF.
    Envía "STATUS?" cada segundo y detecta fallos.
    
    ARQUITECTURA CORRECTA:
    - Este Monitor supervisa UN SOLO Engine
    - Usa monitor_instance.cp_id, .engine_host, .engine_port
    - Reporta solo fallos de SU Engine asignado
    
    Según PDF página 3-4:
    - Conexión TCP con el Engine
    - Envío de mensajes cada segundo
    - Detección de respuestas KO
    - Reporte a Central tras múltiples fallos
    ============================================================================
    """
    consecutive_failures = 0
    
    # Inicializar tracking
    shared_state.health_status = {
        'consecutive_failures': 0,
        'last_check': time.time(),
        'last_status': 'UNKNOWN'
    }
    
    print(f"[MONITOR-{monitor_instance.cp_id}] 🏥 Starting TCP health monitoring")
    print(f"[MONITOR-{monitor_instance.cp_id}]    Engine: {monitor_instance.engine_host}:{monitor_instance.engine_port}")
    print(f"[MONITOR-{monitor_instance.cp_id}]    Frequency: Every 1 second")
    
    while True:
        try:
            await asyncio.sleep(1)  # ✅ CADA 1 SEGUNDO (según PDF)
            
            try:
                # ✅ Conectar al Engine vía TCP
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(monitor_instance.engine_host, monitor_instance.engine_port),
                    timeout=2.0
                )
                
                # ✅ Enviar "STATUS?"
                writer.write(b"STATUS?\n")
                await writer.drain()
                
                # ✅ Recibir respuesta
                data = await asyncio.wait_for(
                    reader.read(100),
                    timeout=1.0
                )
                response = data.decode().strip()
                
                # Procesar respuesta
                if response == "OK":
                    # ✅ Engine responde OK
                    if consecutive_failures > 0:
                        print(f"[MONITOR-{monitor_instance.cp_id}] ✅ Recovered (was {consecutive_failures} failures)")
                        alert = monitor_instance.add_alert(
                            'success',
                            f"✅ {monitor_instance.cp_id} recuperado tras {consecutive_failures} fallos"
                        )
                        await broadcast_alert(alert)
                    
                    consecutive_failures = 0
                    
                    shared_state.health_status = {
                        'consecutive_failures': 0,
                        'last_check': time.time(),
                        'last_status': 'OK'
                    }
                
                elif response == "KO":
                    # ❌ Engine responde KO
                    consecutive_failures += 1
                    print(f"[MONITOR-{monitor_instance.cp_id}] ⚠️ Health check KO (failure {consecutive_failures}/3)")
                    
                    shared_state.health_status = {
                        'consecutive_failures': consecutive_failures,
                        'last_check': time.time(),
                        'last_status': 'KO'
                    }
                    
                    # ✅ Si 3+ fallos consecutivos, reportar a Central
                    if consecutive_failures >= 3:
                        print(f"[MONITOR-{monitor_instance.cp_id}] 🚨 3+ consecutive failures, reporting to Central")
                        
                        # Añadir alerta crítica
                        alert = monitor_instance.add_alert(
                            'critical',
                            f"🔴 {monitor_instance.cp_id} reporta 3+ fallos consecutivos (ENGINE_FAILURE)"
                        )
                        await broadcast_alert(alert)
                        
                        # Reportar a Central vía Kafka
                        if monitor_instance.producer:
                            event = {
                                'message_id': generate_message_id(),
                                'event_type': 'ENGINE_FAILURE',
                                'action': 'report_engine_failure',
                                'cp_id': monitor_instance.cp_id,
                                'failure_type': 'ko',
                                'consecutive_failures': consecutive_failures,
                                'timestamp': current_timestamp(),
                                'monitor_id': f'MONITOR-{monitor_instance.cp_id}'
                            }
                            monitor_instance.producer.send(KAFKA_TOPIC_PRODUCE, event)
                            monitor_instance.producer.flush()
                            print(f"[MONITOR-{monitor_instance.cp_id}] 📤 ENGINE_FAILURE reported to Central")
                        
                        # Reset contador después de reportar
                        consecutive_failures = 0
                
                writer.close()
                await writer.wait_closed()
                
            except asyncio.TimeoutError:
                # Timeout - considerar como fallo
                consecutive_failures += 1
                print(f"[MONITOR-{monitor_instance.cp_id}] ⚠️ Timeout (failure {consecutive_failures}/3)")
                
                shared_state.health_status = {
                    'consecutive_failures': consecutive_failures,
                    'last_check': time.time(),
                    'last_status': 'TIMEOUT'
                }
                
                if consecutive_failures >= 3:
                    print(f"[MONITOR-{monitor_instance.cp_id}] 🚨 Connection timeouts, reporting to Central")
                    
                    alert = monitor_instance.add_alert(
                        'critical',
                        f"🔴 {monitor_instance.cp_id} no responde (3+ timeouts)"
                    )
                    await broadcast_alert(alert)
                    
                    if monitor_instance.producer:
                        event = {
                            'message_id': generate_message_id(),
                            'event_type': 'ENGINE_FAILURE',
                            'action': 'report_engine_failure',
                            'cp_id': monitor_instance.cp_id,
                            'failure_type': 'timeout',
                            'consecutive_failures': consecutive_failures,
                            'timestamp': current_timestamp(),
                            'monitor_id': f'MONITOR-{monitor_instance.cp_id}'
                        }
                        monitor_instance.producer.send(KAFKA_TOPIC_PRODUCE, event)
                        monitor_instance.producer.flush()
                    
                    consecutive_failures = 0
            
            except (ConnectionRefusedError, OSError) as e:
                # Engine no está corriendo
                consecutive_failures += 1
                print(f"[MONITOR-{monitor_instance.cp_id}] ❌ Cannot connect to Engine (failure {consecutive_failures}/3)")
                
                shared_state.health_status = {
                    'consecutive_failures': consecutive_failures,
                    'last_check': time.time(),
                    'last_status': 'CONNECTION_ERROR'
                }
                
                if consecutive_failures >= 3:
                    print(f"[MONITOR-{monitor_instance.cp_id}] 🚨 Engine offline, reporting to Central")
                    
                    alert = monitor_instance.add_alert(
                        'critical',
                        f"🔴 {monitor_instance.cp_id} - Engine offline"
                    )
                    await broadcast_alert(alert)
                    
                    if monitor_instance.producer:
                        event = {
                            'message_id': generate_message_id(),
                            'event_type': 'ENGINE_OFFLINE',
                            'action': 'report_engine_offline',
                            'cp_id': monitor_instance.cp_id,
                            'consecutive_failures': consecutive_failures,
                            'timestamp': current_timestamp(),
                            'monitor_id': f'MONITOR-{monitor_instance.cp_id}'
                        }
                        monitor_instance.producer.send(KAFKA_TOPIC_PRODUCE, event)
                        monitor_instance.producer.flush()
                    
                    consecutive_failures = 0
                    
                    # Esperar más tiempo si no podemos conectar
                    await asyncio.sleep(5)
                    
        except asyncio.CancelledError:
            print(f"[MONITOR-{monitor_instance.cp_id}] 🛑 TCP health monitoring stopped")
            break
        except Exception as e:
            print(f"[MONITOR-{monitor_instance.cp_id}] ❌ Error in TCP health check: {e}")
            await asyncio.sleep(1)


async def main():
    """
    ============================================================================
    ARQUITECTURA CORRECTA: 1 Monitor por 1 Engine (1:1)
    ============================================================================
    Esta función principal inicia los servicios para supervisar UN ÚNICO Engine.
    ============================================================================
    """
    local_ip = get_local_ip()
    
    if not WS_AVAILABLE:
        print("❌ ERROR: WebSocket dependencies not installed")
        print("Run: pip install websockets aiohttp")
        return
    
    # Verificar base de datos (opcional, solo warning si no existe)
    db_path = Path('/app/ev_charging.db') if Path('/app/ev_charging.db').exists() else Path(__file__).parent.parent / 'ev_charging.db'
    if not db_path.exists():
        print("⚠️  Database not found. Monitor will start anyway (read-only mode)")
    
    try:
        # Crear aplicación web que maneje tanto HTTP como WebSocket
        app = web.Application()
        app.router.add_get('/', serve_dashboard)
        app.router.add_get('/ws', websocket_handler_http)
        
        # Iniciar servidor HTTP/WebSocket
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', SERVER_PORT)
        await site.start()
        
        print(f"[HTTP] Dashboard server started on http://0.0.0.0:{SERVER_PORT}")
        print(f"[WS] WebSocket endpoint at ws://0.0.0.0:{SERVER_PORT}/ws")
        print(f"\n✅ Access dashboard: http://localhost:{SERVER_PORT}")
        print(f"✅ Access from network: http://{local_ip}:{SERVER_PORT}\n")
        
        # ========================================================================
        # ARQUITECTURA CORRECTA: Iniciar TCP health check para EL Engine asignado
        # ========================================================================
        print(f"[MONITOR-{monitor_instance.cp_id}] 🏥 Starting TCP health monitoring...")
        health_check_task = asyncio.create_task(tcp_health_check())
        
        # Iniciar broadcast de actualizaciones
        broadcast_task = asyncio.create_task(broadcast_updates())
        
        print(f"\n✅ All services started successfully!")
        print(f"🏥 TCP monitoring active for {monitor_instance.cp_id}")
        print(f"🌐 Engine at {monitor_instance.engine_host}:{monitor_instance.engine_port}\n")
        
        # Mantener el servidor corriendo
        await asyncio.gather(broadcast_task, health_check_task)
        
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")

if __name__ == "__main__":
    # ========================================================================
    # ARGUMENTOS DE LÍNEA DE COMANDOS
    # ========================================================================
    parser = argparse.ArgumentParser(
        description='EV Charging Point Monitor - Supervises ONE Engine (1:1)'
    )
    parser.add_argument(
        '--cp-id',
        required=True,
        help='ID del CP a monitorear (ej: CP_001)'
    )
    parser.add_argument(
        '--engine-host',
        default='localhost',
        help='Host del Engine (default: localhost)'
    )
    parser.add_argument(
        '--engine-port',
        type=int,
        required=True,
        help='Puerto TCP del Engine (ej: 5100)'
    )
    parser.add_argument(
        '--monitor-port',
        type=int,
        default=5500,
        help='Puerto para dashboard de este Monitor (default: 5500)'
    )
    parser.add_argument(
        '--kafka-broker',
        default=os.environ.get('KAFKA_BROKER', KAFKA_BROKER_DEFAULT),
        help='Kafka broker address (default: from config)'
    )
    
    args = parser.parse_args()
    
    # Actualizar variables globales (no necesita 'global' en el scope del módulo)
    MONITORED_CP_ID = args.cp_id
    ENGINE_HOST = args.engine_host
    ENGINE_PORT = args.engine_port
    SERVER_PORT = args.monitor_port
    
    # ========================================================================
    # CREAR INSTANCIA DEL MONITOR (1:1 con Engine)
    # ========================================================================
    monitor_instance = EV_MonitorWS(
        cp_id=args.cp_id,
        engine_host=args.engine_host,
        engine_port=args.engine_port,
        kafka_broker=args.kafka_broker
    )
    
    # Iniciar servidor
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\n[MONITOR-{args.cp_id}] 🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
