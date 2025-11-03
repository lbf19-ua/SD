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
# ARQUITECTURA: El Monitor NO accede directamente a la BD
# Toda la información del CP se obtiene de Central vía Kafka/eventos

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
        self.cp_info = {}  # Información del CP recibida de Central vía Kafka (no de BD)
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
        self._authenticated = False  # Flag para evitar re-autenticación
        
        print(f"\n{'='*80}")
        print(f"  EV MONITOR - Supervising {self.cp_id}")
        print(f"{'='*80}")
        print(f"  Monitored CP:    {self.cp_id}")
        print(f"  Engine Host:     {self.engine_host}")
        print(f"  Engine Port:     {self.engine_port}")
        print(f"  Dashboard Port:  {SERVER_PORT}")
        print(f"{'='*80}\n")
        
        # Inicializar Kafka - si falla, se reintentará en authenticate_with_central
        # No fallar si Kafka no está disponible inicialmente (para Docker)
        if not self.initialize_kafka():
            print(f"[MONITOR-{self.cp_id}] Kafka no disponible inicialmente, se reintentará durante autenticación")
        
        # Autenticación se reintentará si Kafka no está disponible
        self.authenticate_with_central()  # Solo se ejecuta una vez si tiene éxito
        self.initialize_metrics()

    def initialize_kafka(self, max_retries=10):
        """Inicializa el productor de Kafka con reintentos"""
        print(f"[MONITOR-{self.cp_id}] Connecting to Kafka at {self.kafka_broker}...")
        for attempt in range(max_retries):
            try:
                # Producer sin api_version explícito (auto-detección)
                self.producer = KafkaProducer(
                    bootstrap_servers=self.kafka_broker,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    request_timeout_ms=30000,
                    retries=3,
                    acks='all'
                )
                # Intentar enviar un mensaje de prueba para verificar la conexión
                # Test producer connection - NO enviar mensaje de test al topic para evitar eventos UNKNOWN en Central
                # En su lugar, solo verificamos que el producer esté configurado correctamente
                # El flush() verificará que el producer funciona sin necesidad de enviar un mensaje
                # Si hay un error, se lanzará una excepción en el siguiente send real
                print(f"[MONITOR-{self.cp_id}] Kafka producer initialized and connected")
                return True
            except Exception as e:
                print(f"[MONITOR-{self.cp_id}]  Attempt {attempt+1}/{max_retries} - Kafka connection failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    print(f"[MONITOR-{self.cp_id}] Failed to connect to Kafka after {max_retries} attempts")
                    print(f"[MONITOR-{self.cp_id}] Tip: Verificar que Kafka está corriendo y accesible en {self.kafka_broker}")
                    self.producer = None
                    return False

    def authenticate_with_central(self):
        """
        Se conecta a EV_Central para autenticarse y validar que el Monitor
        está operativo y preparado para prestar servicios.
        
        Requisito del PDF: Al arrancar, el Monitor debe conectarse a Central
        para autenticarse y validar que está operativo.
        
        Solo se autentica UNA VEZ al iniciar.
        """
        # PROTECCIÓN: Solo autenticarse una vez
        if hasattr(self, '_authenticated') and self._authenticated:
            print(f"[MONITOR-{self.cp_id}] Already authenticated, skipping")
            return
        
        print(f"[MONITOR-{self.cp_id}] Authenticating with Central...")
        
        # Esperar a que Kafka esté disponible - reintentar indefinidamente si falla (para Docker)
        # Esto evita que el contenedor se reinicie constantemente
        if not self.producer:
            print(f"[MONITOR-{self.cp_id}]  Kafka producer not initialized, waiting for Kafka...")
            while not self.initialize_kafka(max_retries=5):
                print(f"[MONITOR-{self.cp_id}] No se pudo conectar a Kafka, reintentando en 10 segundos...")
                print(f"[MONITOR-{self.cp_id}]    Verificar que Kafka está corriendo en {self.kafka_broker}")
                time.sleep(10)  # Esperar 10 segundos antes de reintentar
            print(f"[MONITOR-{self.cp_id}] Kafka conectado, procediendo con autenticación")
        
        try:
            # Marcar como autenticado ANTES de enviar (para evitar re-envío si falla el envío)
            self._authenticated = True
            
            # Enviar mensaje de autenticación a Central vía Kafka (solo una vez)
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
            
            print(f"[MONITOR-{self.cp_id}] Sending authentication event to topic '{KAFKA_TOPIC_PRODUCE}'...")
            future = self.producer.send(KAFKA_TOPIC_PRODUCE, auth_event)
            # Esperar confirmación del envío
            record_metadata = future.get(timeout=10)
            self.producer.flush(timeout=5)
            print(f"[MONITOR-{self.cp_id}] Authentication sent to Central (topic: {record_metadata.topic}, partition: {record_metadata.partition})")
            print(f"[MONITOR-{self.cp_id}] Monitor validated and ready to monitor {self.cp_id}")
        except Exception as e:
            print(f"[MONITOR-{self.cp_id}] Authentication failed: {e}")
            import traceback
            traceback.print_exc()
            # Si falla, permitir reintentar
            self._authenticated = False

    def initialize_metrics(self):
        """Inicializa métricas simuladas para el CP monitoreado"""
        shared_state.cp_metrics[self.cp_id] = {
            'temperature': 25.0,
            'efficiency': 100.0,
            'uptime_start': time.time(),
            'sessions_today': 0,
            'current_power': 0.0
        }
        print(f"[MONITOR-{self.cp_id}] Metrics initialized for {self.cp_id}")

    def get_monitor_data(self):
        """
        Obtiene datos del CP monitoreado para el dashboard
        
        ARQUITECTURA: El Monitor NO accede directamente a la BD
        Toda la información del CP se obtiene de Central vía Kafka/eventos
        y se almacena en shared_state.cp_info
        """
        try:
            # ========================================================================
            # Obtener información del CP desde estado local (recibida de Central)
            # NO acceder a la BD directamente
            # ========================================================================
            with shared_state.lock:
                cp = shared_state.cp_info.get(self.cp_id, {})
            
            # Si no hay información del CP, usar valores por defecto
            if not cp:
                # Información por defecto hasta que Central envíe datos reales
                cp = {
                    'cp_id': self.cp_id,
                    'location': 'Unknown',
                    'max_power_kw': 22.0,
                    'tariff_per_kwh': 0.30,
                    'status': 'offline',
                    'estado': 'offline'
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
            max_power = cp.get('max_power_kw') or cp.get('max_kw', 22.0)
            # Manejar tanto 'status' como 'estado'
            # Normalizar estado para asegurar que sea un estado válido del CP
            raw_status = cp.get('status') or cp.get('estado', 'offline')
            valid_statuses = ['available', 'charging', 'offline', 'fault', 'out_of_service']
            if raw_status:
                raw_status_lower = raw_status.lower().strip()
                if raw_status_lower in valid_statuses:
                    cp_status = raw_status_lower
                else:
                    # Estado inválido, usar 'offline' por defecto
                    print(f"[MONITOR-{self.cp_id}] Estado inválido en get_monitor_data: '{raw_status}', usando 'offline'")
                    cp_status = 'offline'
            else:
                cp_status = 'offline'
            
            if cp_status == 'charging':
                current_power = max_power * random.uniform(0.85, 0.95)
            
            # Extraer datos del cp (que viene de shared_state.cp_info)
            location = cp.get('location') or cp.get('localizacion') or 'Unknown'
            if not location or location.strip() == '':
                location = 'Unknown'
            
            tariff = cp.get('tariff_per_kwh') or cp.get('tarifa_kwh') or 0.30
            
            # Construir datos del CP monitoreado para el frontend
            charging_point = {
                'cp_id': cp.get('cp_id', self.cp_id),
                'location': location,
                'power_output': max_power,
                'tariff': tariff,
                'status': cp_status,
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
            print(f"[MONITOR-{self.cp_id}] Error getting monitor data: {e}")
            import traceback
            traceback.print_exc()
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
    print(f"[WS] New monitor client connected. Total clients: {len(shared_state.connected_clients)}")
    
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
    print(f"[HTTP] Server started on http://0.0.0.0:{SERVER_PORT}")

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
        max_retries = 10
        # Usar kafka_broker de la instancia del Monitor si está disponible, sino usar la variable global
        kafka_broker_to_use = monitor_instance.kafka_broker if monitor_instance else KAFKA_BROKER
        
        for attempt in range(max_retries):
            try:
                print(f"[KAFKA] Connecting consumer to Kafka at {kafka_broker_to_use}...")
                print(f"[KAFKA] Monitor instance: {monitor_instance.cp_id if monitor_instance else 'None'}")
                print(f"[KAFKA] Using broker: {kafka_broker_to_use}")
                # Usar cp_id de monitor_instance si está disponible, sino usar MONITORED_CP_ID global
                cp_id_for_group = monitor_instance.cp_id if monitor_instance else MONITORED_CP_ID or 'default'
                # IMPORTANTE: Usar group_id único y auto_offset_reset='latest' para evitar leer mensajes antiguos
                import time as time_module
                unique_group_id = f'ev_monitor_ws_group_{cp_id_for_group}_{int(time_module.time())}'
                # Consumer sin api_version explícito (auto-detección)
                consumer = KafkaConsumer(
                    *KAFKA_TOPICS_CONSUME,
                    bootstrap_servers=kafka_broker_to_use,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='latest',  # Solo leer mensajes nuevos después de conectarse
                    group_id=unique_group_id,  # Group ID único por inicio
                    request_timeout_ms=30000,
                    session_timeout_ms=10000,
                    consumer_timeout_ms=5000
                )
                
                print(f"[KAFKA] Consumer connected, listening to {KAFKA_TOPICS_CONSUME}")
                print(f"[KAFKA] Consumer configured to ONLY read NEW messages (latest offset)")
                
                # CRÍTICO: Usar poll() en lugar de 'for message in consumer:' para mejor control
                # 'for message in consumer:' puede leer offsets antiguos si el group_id no es único
                while True:
                    try:
                        # Poll con timeout para procesar mensajes nuevos
                        msg_pack = consumer.poll(timeout_ms=2000, max_records=50)
                        
                        if msg_pack:
                            # Procesar mensajes recibidos
                            for topic_partition, messages in msg_pack.items():
                                for message in messages:
                                    event = message.value
                                    # Programar el procesamiento en el event loop
                                    asyncio.run_coroutine_threadsafe(
                                        process_kafka_event(event),
                                        loop
                                    )
                    except Exception as poll_error:
                        print(f"[KAFKA] Error en poll: {poll_error}")
                        import traceback
                        traceback.print_exc()
                        time.sleep(1)
                        continue
                    
            except Exception as e:
                import traceback
                print(f"[KAFKA]  Attempt {attempt+1}/{max_retries} - Consumer error: {e}")
                print(f"[KAFKA] Error details: {traceback.format_exc()}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    print(f"[KAFKA] Failed to connect consumer after {max_retries} attempts")
                    print(f"[KAFKA] Verificar:")
                    print(f"[KAFKA]    1. Kafka está corriendo en {kafka_broker_to_use}")
                    print(f"[KAFKA]    2. Desde PC3, probar conectividad: telnet <IP_PC2> 9092")
                    print(f"[KAFKA]    3. Firewall permite tráfico en puerto 9092 de PC2")
                    print(f"[KAFKA]    4. Variable KAFKA_BROKER en .env de PC3: {kafka_broker_to_use}")
                    print(f"[KAFKA]    5. PC2_IP en .env de PC2 debe ser la IP real de PC2")
                    break
    
    # Ejecutar el consumidor de Kafka en un thread separado
    kafka_thread = threading.Thread(target=consume_kafka, daemon=True)
    kafka_thread.start()

async def process_kafka_event(event):
    """
    Procesa eventos de Kafka y genera alertas
    
    ARQUITECTURA: El Monitor recibe información del CP desde Central vía Kafka
    y la almacena en shared_state.cp_info (NO accede a BD directamente)
    
    IMPORTANTE: Cada Monitor SOLO procesa eventos de SU CP asignado (1:1)
    
    CRÍTICO: Filtrar INMEDIATAMENTE eventos de otros CPs ANTES de cualquier procesamiento o log
    """
    # CRÍTICO: Verificar monitor_instance primero
    if not monitor_instance:
        # Si no hay instancia del monitor, ignorar todos los eventos
        return
    
    # CRÍTICO: Extraer cp_id INMEDIATAMENTE para filtrar eventos de otros CPs
    # El Engine y Central pueden enviar eventos con cp_id o engine_id, verificar ambos
    # También verificar dentro de data si está ahí
    cp_id = event.get('cp_id') or event.get('engine_id')
    
    # Si no está en el nivel raíz, buscar en data
    if not cp_id:
        cp_data = event.get('data', {}) if isinstance(event.get('data'), dict) else {}
        cp_id = cp_data.get('cp_id') or cp_data.get('engine_id')
    
    event_type = event.get('event_type', '')
    action = event.get('action', '')
    
    # FILTRADO TEMPRANO: Ignorar eventos de otros CPs ANTES de cualquier otro procesamiento
    # Esto evita procesar eventos que no corresponden a este Monitor
    if cp_id:
        # Normalizar cp_id (asegurar que es string y está en mayúsculas/estilo correcto)
        cp_id_str = str(cp_id).strip()
        monitor_cp_id_str = str(monitor_instance.cp_id).strip()
        
        # Si el evento tiene cp_id, verificar inmediatamente si corresponde a este Monitor
        if cp_id_str != monitor_cp_id_str:
            # Evento de otro CP - ignorar completamente sin procesar ni loguear
            # Solo loguear si es CP_INFO para debug (reducir ruido en logs)
            if event_type == 'CP_INFO' and action == 'cp_info_update':
                # Log ocasionalmente para debug (cada 10 eventos para no saturar)
                import random
                if random.random() < 0.1:  # 10% de probabilidad de loguear
                    print(f"[MONITOR-{monitor_instance.cp_id}] CP_INFO de otro CP ignorado: cp_id={cp_id_str} (este Monitor supervisa {monitor_cp_id_str})")
            return
    
    # Si llegamos aquí, el evento es de nuestro CP O no tiene cp_id
    # Para eventos sin cp_id, solo procesar si son relevantes (MONITOR_AUTH, etc.)
    if not cp_id:
        if event_type == 'MONITOR_AUTH':
            # Evento de autenticación, ignorar (ya procesado en otro lugar)
            return
        else:
            # Evento sin cp_id que no es MONITOR_AUTH, ignorar
            return
    
    # A partir de aquí, solo procesamos eventos de nuestro CP (cp_id == monitor_instance.cp_id)
    # Log solo eventos relevantes para este Monitor
    if event_type in ['CP_INFO', 'CP_REGISTRATION'] or 'cp_info' in action:
        print(f"[MONITOR-{monitor_instance.cp_id}] Evento recibido: type={event_type}, action={action}, cp_id={cp_id}")
    
    # IGNORAR eventos MONITOR_AUTH (no contienen información del CP)
    if event_type == 'MONITOR_AUTH':
        # Este evento es solo para autenticación, Central enviará CP_INFO después
        return
    
    # IGNORAR CP_REGISTRATION directos del Engine - Solo procesar CP_INFO de Central
    # CP_REGISTRATION es un evento que el Engine envía a Central, no al Monitor
    # Central procesa CP_REGISTRATION y luego envía CP_INFO al Monitor
    # Si procesamos CP_REGISTRATION aquí, causamos bucles de actualizaciones
    if event_type == 'CP_REGISTRATION':
        print(f"[MONITOR-{monitor_instance.cp_id}] Ignorando CP_REGISTRATION directo - Central enviará CP_INFO después")
        return
    
    # VERIFICACIÓN FINAL: Asegurar que el cp_id coincide con nuestro CP
    # Aunque ya filtramos arriba, esta es una verificación de seguridad adicional
    if cp_id != monitor_instance.cp_id:
        # No debería llegar aquí si el filtrado está funcionando correctamente
        # Pero si llega, ignorarlo inmediatamente
        return
    
    # A partir de aquí, solo procesamos eventos del CP de este Monitor (cp_id == monitor_instance.cp_id)
    # Actualizar información del CP recibida de Central
    if cp_id == monitor_instance.cp_id:
        # Este evento es para el CP que este Monitor supervisa
        with shared_state.lock:
            if cp_id not in shared_state.cp_info:
                shared_state.cp_info[cp_id] = {}
            
            # SOLO procesar CP_INFO de Central (no CP_REGISTRATION directos)
            # Central es la única fuente de verdad para la información del CP
            # Verificar tanto event_type como action para asegurar que capturamos todos los casos
            is_cp_info_event = (event_type == 'CP_INFO') or (action == 'cp_info_update')
            
            if is_cp_info_event:
                # Registro o actualización del CP desde Central (único con acceso a BD)
                cp_data = event.get('data', {}) if isinstance(event.get('data'), dict) else {}
                
                # Extraer datos del evento CP_INFO
                # Los datos están en event.data según la estructura que envía Central
                # Pero también pueden estar en el nivel raíz como fallback
                
                # Extraer ubicación: primero del data, luego del nivel raíz del evento
                cp_location = (cp_data.get('location') or cp_data.get('localizacion') or 
                             event.get('location') or event.get('localizacion') or '')
                # Normalizar location - eliminar espacios y verificar que no esté vacío
                if cp_location:
                    cp_location = str(cp_location).strip()
                if not cp_location or cp_location == '':
                    # Si aún no hay location, mantener la anterior si existe, sino 'Unknown'
                    existing_location = shared_state.cp_info.get(cp_id, {}).get('location') or shared_state.cp_info.get(cp_id, {}).get('localizacion')
                    cp_location = existing_location if existing_location and existing_location != 'Unknown' else 'Unknown'
                    if cp_location == 'Unknown':
                        print(f"[MONITOR-{cp_id}] No se pudo extraer location del CP_INFO, usando 'Unknown'")
                
                # Extraer estado: primero del data, luego del nivel raíz del evento
                cp_status = (cp_data.get('status') or cp_data.get('estado') or 
                           event.get('status') or event.get('estado') or 'offline')
                
                # Normalizar estado (filtrar estados inválidos)
                valid_statuses = ['available', 'charging', 'offline', 'fault', 'out_of_service']
                if cp_status:
                    cp_status_lower = cp_status.lower().strip()
                    if cp_status_lower in valid_statuses:
                        cp_status = cp_status_lower
                    else:
                        # Estado inválido: NO usar 'available' por defecto, mantener 'offline' o el último estado conocido
                        print(f"[MONITOR-{cp_id}] Estado inválido recibido: '{cp_status}', manteniendo estado actual o usando 'offline'")
                        # Si ya hay un estado guardado, mantenerlo; si no, usar 'offline'
                        existing_status = shared_state.cp_info.get(cp_id, {}).get('status') or shared_state.cp_info.get(cp_id, {}).get('estado')
                        cp_status = existing_status if existing_status and existing_status.lower() in valid_statuses else 'offline'
                else:
                    cp_status = 'offline'
                
                # Extraer max_power: primero del data, luego del nivel raíz del evento
                max_power = (cp_data.get('max_power_kw') or cp_data.get('max_kw') or 
                           event.get('max_power_kw') or event.get('max_kw') or 22.0)
                # Asegurar que es numérico
                try:
                    max_power = float(max_power) if max_power else 22.0
                    if max_power <= 0:
                        max_power = 22.0
                except (ValueError, TypeError):
                    max_power = 22.0
                
                # Extraer tariff: primero del data, luego del nivel raíz del evento
                tariff = (cp_data.get('tariff_per_kwh') or cp_data.get('tarifa_kwh') or 
                         event.get('tariff_per_kwh') or event.get('tarifa_kwh') or 0.30)
                # Asegurar que es numérico
                try:
                    tariff = float(tariff) if tariff else 0.30
                    if tariff <= 0:
                        tariff = 0.30
                except (ValueError, TypeError):
                    tariff = 0.30
                
                # CRÍTICO: Verificar si el estado realmente cambió antes de actualizar
                # Esto previene bucles infinitos de actualizaciones innecesarias
                # PERO: Si es la primera vez o los datos están vacíos/incorrectos, siempre actualizar
                is_empty = len(shared_state.cp_info[cp_id]) == 0
                current_stored_status = shared_state.cp_info[cp_id].get('status') or shared_state.cp_info[cp_id].get('estado')
                current_stored_location = shared_state.cp_info[cp_id].get('location') or shared_state.cp_info[cp_id].get('localizacion')
                current_stored_max_power = shared_state.cp_info[cp_id].get('max_power_kw') or shared_state.cp_info[cp_id].get('max_kw')
                current_stored_tariff = shared_state.cp_info[cp_id].get('tariff_per_kwh') or shared_state.cp_info[cp_id].get('tarifa_kwh')
                
                # Si es la primera vez o location es 'Unknown', siempre actualizar
                is_initial_update = is_empty or not current_stored_location or current_stored_location == 'Unknown' or current_stored_location == ''
                
                # Verificar si realmente hay cambios
                status_changed = current_stored_status != cp_status
                location_changed = current_stored_location != cp_location
                max_power_changed = abs((current_stored_max_power or 0) - max_power) > 0.01
                tariff_changed = abs((current_stored_tariff or 0) - tariff) > 0.01
                
                # Si es actualización inicial o hay cambios reales, procesar
                if not is_initial_update and not (status_changed or location_changed or max_power_changed or tariff_changed):
                    # No hay cambios reales y no es inicial, ignorar este evento para evitar bucles
                    print(f"[MONITOR-{cp_id}] CP_INFO sin cambios (status={cp_status}, location={cp_location}), omitiendo actualización para evitar bucle")
                    return
                
                print(f"[MONITOR-{cp_id}] Procesando CP_INFO: status={cp_status} (cambió: {status_changed}), location={cp_location}, max_power={max_power}, tariff={tariff}")
                print(f"[MONITOR-{cp_id}] Datos extraídos del evento - cp_data.location: {cp_data.get('location')}, cp_data.localizacion: {cp_data.get('localizacion')}, event.location: {event.get('location')}, event.localizacion: {event.get('localizacion')}")
                print(f"[MONITOR-{cp_id}] Procesando CP_INFO: status={cp_status} (cambió: {status_changed}), location='{cp_location}' (cambió: {location_changed}), max_power={max_power}, tariff={tariff}")
                print(f"[MONITOR-{cp_id}] Datos extraídos del evento - cp_data.location: '{cp_data.get('location')}', cp_data.localizacion: '{cp_data.get('localizacion')}', event.location: '{event.get('location')}', event.localizacion: '{event.get('localizacion')}'")
                # DEBUG: Mostrar todos los campos del evento para diagnosticar problemas
                if cp_location == 'Unknown' or not cp_location:
                    print(f"[MONITOR-{cp_id}] DEBUG: cp_location es '{cp_location}', verificando evento completo:")
                    print(f"[MONITOR-{cp_id}] DEBUG: event.data keys: {list(cp_data.keys()) if isinstance(cp_data, dict) else 'NOT A DICT'}")
                    print(f"[MONITOR-{cp_id}] DEBUG: event root keys: {list(event.keys())[:10]}...")  # Primeros 10 campos
                
                # Guardar en shared_state.cp_info solo si hay cambios
                shared_state.cp_info[cp_id].update({
                    'cp_id': cp_id,
                    'location': cp_location,
                    'localizacion': cp_location,
                    'max_power_kw': max_power,
                    'max_kw': max_power,
                    'tariff_per_kwh': tariff,
                    'tarifa_kwh': tariff,
                    'status': cp_status,
                    'estado': cp_status
                })
                print(f"[MONITOR-{cp_id}] CP_INFO actualizado en shared_state - location: '{cp_location}', status: {cp_status}")
                # DEBUG: Si location es 'Unknown' o status es 'offline', verificar qué pasó
                if cp_location == 'Unknown' or cp_location == '':
                    print(f"[MONITOR-{cp_id}] ADVERTENCIA: Location sigue siendo 'Unknown' después de actualizar CP_INFO")
                if cp_status == 'offline':
                    print(f"[MONITOR-{cp_id}] ADVERTENCIA: Status es 'offline' - el Engine debería estar 'available' cuando está corriendo")
                # No es necesario broadcast inmediato - el broadcast periódico lo hará cada 3 segundos
                # await broadcast_monitor_data()  # Comentado para evitar saturación
            elif ('status' in event or 'estado' in event) and event_type != 'MONITOR_AUTH' and event_type != 'CP_REGISTRATION':
                # Actualizar estado del CP (solo si no es MONITOR_AUTH o CP_REGISTRATION)
                # CP_REGISTRATION ya se maneja arriba y se ignora para evitar bucles
                new_status = event.get('status') or event.get('estado')
                
                # FILTRAR estados inválidos (solo aceptar estados válidos del CP)
                valid_statuses = ['available', 'charging', 'offline', 'fault', 'out_of_service']
                if new_status and new_status.lower() not in valid_statuses:
                    # Ignorar estados inválidos, mantener el actual
                    return
                
                # CRÍTICO: Verificar si el estado realmente cambió antes de actualizar
                current_stored_status = shared_state.cp_info[cp_id].get('status') or shared_state.cp_info[cp_id].get('estado')
                if current_stored_status == new_status:
                    # Estado no cambió, ignorar para evitar bucles
                    print(f"[MONITOR-{cp_id}] Estado {new_status} ya está sincronizado, omitiendo actualización para evitar bucle")
                    return
                
                if new_status:
                    shared_state.cp_info[cp_id]['status'] = new_status
                    shared_state.cp_info[cp_id]['estado'] = new_status
                    print(f"[MONITOR-{cp_id}] Estado actualizado desde Central: {current_stored_status} → {new_status}")
                    # El broadcast periódico actualizará el dashboard automáticamente
    
    # VERIFICACIÓN ADICIONAL: Asegurar que cp_id coincide antes de procesar eventos de carga/errores
    # Aunque ya filtramos arriba, esta es una verificación de seguridad final
    if not cp_id:
        # Evento sin cp_id, no procesar eventos de carga/errores
        return
    
    # Normalizar cp_id para comparación
    cp_id_str = str(cp_id).strip()
    monitor_cp_id_str = str(monitor_instance.cp_id).strip()
    
    if cp_id_str != monitor_cp_id_str:
        # Evento para otro CP, no procesar
        return
    
    # Procesar eventos de carga y errores para el CP de este Monitor
    if action == 'charging_started':
        username = event.get('username')
        alert = monitor_instance.add_alert(
            'info',
            f"Carga iniciada en {cp_id} por {username}"
        )
        await broadcast_alert(alert)
        # Actualizar estado a 'charging'
        with shared_state.lock:
            if cp_id in shared_state.cp_info:
                shared_state.cp_info[cp_id]['status'] = 'charging'
                shared_state.cp_info[cp_id]['estado'] = 'charging'
        
    elif action == 'charging_stopped':
        username = event.get('username')
        energy = event.get('energy_kwh', 0)
        alert = monitor_instance.add_alert(
            'success',
            f"Carga completada en {cp_id}: {energy:.2f} kWh"
        )
        await broadcast_alert(alert)
        # Actualizar estado a 'available'
        with shared_state.lock:
            if cp_id in shared_state.cp_info:
                shared_state.cp_info[cp_id]['status'] = 'available'
                shared_state.cp_info[cp_id]['estado'] = 'available'
        
    elif action == 'fault_detected':
        alert = monitor_instance.add_alert(
            'critical',
            f"Fallo detectado en {cp_id}"
        )
        await broadcast_alert(alert)
        # Actualizar estado a 'fault'
        with shared_state.lock:
            if cp_id in shared_state.cp_info:
                shared_state.cp_info[cp_id]['status'] = 'fault'
                shared_state.cp_info[cp_id]['estado'] = 'fault'
        
    elif action == 'cp_offline':
        alert = monitor_instance.add_alert(
            'warning',
            f"{cp_id} fuera de línea"
        )
        await broadcast_alert(alert)
        # Actualizar estado a 'offline'
        with shared_state.lock:
            if cp_id in shared_state.cp_info:
                shared_state.cp_info[cp_id]['status'] = 'offline'
                shared_state.cp_info[cp_id]['estado'] = 'offline'
        
    elif action == 'cp_error_simulated':
        error_type = event.get('error_type', 'error')
        alert = monitor_instance.add_alert(
            'critical',
            f"Admin simuló {error_type} en {cp_id}"
        )
        await broadcast_alert(alert)
        # Actualizar estado según tipo de error
        with shared_state.lock:
            if cp_id in shared_state.cp_info:
                if error_type == 'fault':
                    shared_state.cp_info[cp_id]['status'] = 'fault'
                elif error_type == 'out_of_service':
                    shared_state.cp_info[cp_id]['status'] = 'out_of_service'
                shared_state.cp_info[cp_id]['estado'] = shared_state.cp_info[cp_id]['status']
        # El broadcast periódico actualizará el dashboard automáticamente
        
    elif action == 'cp_error_fixed' or action == 'resume':
        alert = monitor_instance.add_alert(
            'success',
            f"Admin reparó {cp_id}, ahora disponible"
        )
        await broadcast_alert(alert)
        # Actualizar estado a 'available'
        with shared_state.lock:
            if cp_id in shared_state.cp_info:
                shared_state.cp_info[cp_id]['status'] = 'available'
                shared_state.cp_info[cp_id]['estado'] = 'available'
        # El broadcast periódico actualizará el dashboard automáticamente

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
    last_reported_failure = None  # Timestamp del último fallo reportado
    startup_grace_period = 30  # Periodo de gracia al inicio (30 segundos) para dar tiempo al Engine
    monitor_start_time = time.time()
    
    # Inicializar tracking
    shared_state.health_status = {
        'consecutive_failures': 0,
        'last_check': time.time(),
        'last_status': 'UNKNOWN'
    }
    
    print(f"[MONITOR-{monitor_instance.cp_id}] Starting TCP health monitoring")
    print(f"[MONITOR-{monitor_instance.cp_id}]    Engine: {monitor_instance.engine_host}:{monitor_instance.engine_port}")
    print(f"[MONITOR-{monitor_instance.cp_id}]    Frequency: Every 1 second")
    
    # IMPORTANTE: Esperar al inicio para que el Engine esté completamente listo
    # El Engine necesita tiempo para iniciar Kafka, registrarse y abrir el servidor TCP
    initial_wait_time = 15  # Aumentado a 15 segundos para dar más tiempo al Engine
    print(f"[MONITOR-{monitor_instance.cp_id}] Waiting {initial_wait_time}s for Engine to be ready...")
    
    # Intentar verificar que el Engine está disponible antes de empezar
    print(f"[MONITOR-{monitor_instance.cp_id}] Verifying Engine connectivity to {monitor_instance.engine_host}:{monitor_instance.engine_port}...")
    await asyncio.sleep(initial_wait_time)
    
    # Intentar una conexión de prueba antes de empezar health checks continuos
    try:
        test_reader, test_writer = await asyncio.wait_for(
            asyncio.open_connection(monitor_instance.engine_host, monitor_instance.engine_port),
            timeout=2.0
        )
        test_writer.write(b"STATUS?\n")
        await test_writer.drain()
        test_response = await asyncio.wait_for(test_reader.readuntil(b'\n'), timeout=2.0)
        test_writer.close()
        await test_writer.wait_closed()
        print(f"[MONITOR-{monitor_instance.cp_id}] Engine connectivity verified! Response: {test_response.decode().strip()}")
    except Exception as test_error:
        print(f"[MONITOR-{monitor_instance.cp_id}]  Warning: Could not verify Engine connectivity: {test_error}")
        print(f"[MONITOR-{monitor_instance.cp_id}]  Will continue health checks anyway (Engine may still be starting)...")
    
    print(f"[MONITOR-{monitor_instance.cp_id}] Starting continuous health checks")
    
    while True:
        try:
            await asyncio.sleep(1)  # CADA 1 SEGUNDO (según PDF)
            
            try:
                # Conectar al Engine vía TCP
                # Reducir logs excesivos - solo imprimir cada 10 intentos o si hay error
                # Aumentar timeout para dar más tiempo a la conexión
                # print(f"[MONITOR-{monitor_instance.cp_id}] Attempting to connect to {monitor_instance.engine_host}:{monitor_instance.engine_port}")
                try:
                    # Intentar conectar al Engine
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(monitor_instance.engine_host, monitor_instance.engine_port),
                        timeout=5.0  # Aumentado a 5 segundos para dar más tiempo
                    )
                    # Solo imprimir cada 10 conexiones exitosas para reducir ruido
                    # print(f"[MONITOR-{monitor_instance.cp_id}] Connected to Engine")
                except asyncio.TimeoutError:
                    # Timeout en la conexión - esto SÍ es un timeout real
                    consecutive_failures += 1
                    # Solo imprimir cada 3 fallos para reducir ruido
                    if consecutive_failures % 3 == 0 or consecutive_failures <= 3:
                        print(f"[MONITOR-{monitor_instance.cp_id}] Connection timeout (failure {consecutive_failures}/3)")
                    shared_state.health_status = {
                        'consecutive_failures': consecutive_failures,
                        'last_check': time.time(),
                        'last_status': 'TIMEOUT'
                    }
                    
                    # Si hay 3+ fallos consecutivos, reportar a Central
                    if consecutive_failures >= 3:
                        # PROTECCIÓN: No reportar fallos durante el período de gracia inicial (Engine puede estar iniciando)
                        time_since_start = time.time() - monitor_start_time
                        if time_since_start < startup_grace_period:
                            print(f"[MONITOR-{monitor_instance.cp_id}] Monitor inició hace {time_since_start:.1f}s, esperando a que Engine esté disponible (grace period: {startup_grace_period}s)")
                            consecutive_failures = 0  # Reset durante grace period
                            await asyncio.sleep(1)
                            continue
                        
                        # PROTECCIÓN: No reportar el mismo fallo repetidamente (evitar bucle)
                        current_time = time.time()
                        if last_reported_failure and (current_time - last_reported_failure) < 60:  # No reportar más de una vez por minuto
                            print(f"[MONITOR-{monitor_instance.cp_id}] Fallo ya reportado recientemente, esperando antes de reportar de nuevo")
                            consecutive_failures = 0  # Reset para evitar spam
                            await asyncio.sleep(5)  # Esperar más tiempo antes de reintentar
                            continue
                        
                        print(f"[MONITOR-{monitor_instance.cp_id}] Connection timeouts, reporting to Central")
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
                            last_reported_failure = current_time  # Marcar que se reportó
                            consecutive_failures = 0
                        await asyncio.sleep(5)  # Esperar más tiempo antes de reintentar
                    
                    # Continuar al siguiente intento
                    continue
                
                # Enviar "STATUS?"
                # Reducir logs - no imprimir cada STATUS? enviado
                writer.write(b"STATUS?\n")
                await writer.drain()
                
                # Recibir respuesta - leer hasta encontrar newline o timeout
                try:
                    # Timeout razonable para respuesta TCP
                    data = await asyncio.wait_for(
                        reader.readuntil(b'\n'),  # Leer hasta encontrar newline
                        timeout=2.0  # Timeout de 2 segundos es suficiente
                    )
                    response = data.decode().strip()
                    # Solo imprimir si hay problema, no cada respuesta OK
                    if response != "OK":
                        print(f"[MONITOR-{monitor_instance.cp_id}] Received: {response}")
                except asyncio.IncompleteReadError as e:
                    # Si hay datos parciales, leerlos
                    partial = e.partial
                    if partial:
                        response = partial.decode().strip()
                        print(f"[MONITOR-{monitor_instance.cp_id}] Received (partial): {response}")
                    else:
                        # Intentar leer más datos
                        try:
                            data = await asyncio.wait_for(
                                reader.read(100),
                                timeout=1.0
                            )
                            response = data.decode().strip()
                            print(f"[MONITOR-{monitor_instance.cp_id}] Received (after partial): {response}")
                        except Exception as e2:
                            print(f"[MONITOR-{monitor_instance.cp_id}] Error reading after partial: {e2}")
                            raise asyncio.TimeoutError("Failed to read response")
                except Exception as e:
                    error_msg = str(e) if e else type(e).__name__
                    error_type = type(e).__name__
                    print(f"[MONITOR-{monitor_instance.cp_id}] Error reading response: {error_msg} (type: {error_type})")
                    
                    # Intentar recuperar datos parciales antes de contar como timeout
                    partial_data = None
                    try:
                        # Si es IncompleteReadError, tiene atributo partial
                        if hasattr(e, 'partial'):
                            partial_data = e.partial
                        elif isinstance(e, (ConnectionResetError, OSError, BrokenPipeError)):
                            # Conexión cerrada - podría haber datos en el buffer
                            # Intentar leer cualquier dato pendiente
                            try:
                                # Intentar leer con timeout corto
                                partial_data = await asyncio.wait_for(
                                    reader.read(100),
                                    timeout=0.1
                                )
                            except:
                                pass
                    except:
                        pass
                    
                    # Si tenemos datos parciales que parecen válidos, usarlos
                    if partial_data:
                        try:
                            response = partial_data.decode().strip()
                            print(f"[MONITOR-{monitor_instance.cp_id}] Received (partial/error): '{response}'")
                            # Si la respuesta parcial es "OK" o "KO", es válida
                            if response in ['OK', 'KO']:
                                # Continuar procesando con esta respuesta
                                # NO lanzar TimeoutError - es un error de lectura pero tenemos la respuesta
                                print(f"[MONITOR-{monitor_instance.cp_id}] Recovered partial response: {response}")
                                # Continuar con el procesamiento normal de la respuesta
                            else:
                                # Datos parciales no válidos - timeout real
                                raise asyncio.TimeoutError(f"Failed to read response: {error_msg}")
                        except Exception as decode_error:
                            print(f"[MONITOR-{monitor_instance.cp_id}] Error decoding partial data: {decode_error}")
                            raise asyncio.TimeoutError(f"Failed to read response: {error_msg}")
                    else:
                        # No hay datos parciales - timeout real
                        raise asyncio.TimeoutError(f"Failed to read response: {error_msg}")
                
                # Procesar respuesta
                if response == "OK":
                    # Engine responde OK
                    if consecutive_failures > 0:
                        print(f"[MONITOR-{monitor_instance.cp_id}] Recovered (was {consecutive_failures} failures)")
                        alert = monitor_instance.add_alert(
                            'success',
                            f"{monitor_instance.cp_id} recuperado tras {consecutive_failures} fallos"
                        )
                        await broadcast_alert(alert)
                        # Reset el timestamp del último fallo reportado cuando se recupera
                        last_reported_failure = None
                    
                    consecutive_failures = 0
                    
                    shared_state.health_status = {
                        'consecutive_failures': 0,
                        'last_check': time.time(),
                        'last_status': 'OK'
                    }
                
                elif response == "KO":
                    # Engine responde KO
                    consecutive_failures += 1
                    print(f"[MONITOR-{monitor_instance.cp_id}] Health check KO (failure {consecutive_failures}/3)")
                    
                    shared_state.health_status = {
                        'consecutive_failures': consecutive_failures,
                        'last_check': time.time(),
                        'last_status': 'KO'
                    }
                    
                    # Si 3+ fallos consecutivos, reportar a Central
                    if consecutive_failures >= 3:
                        # PROTECCIÓN: No reportar el mismo fallo repetidamente (evitar bucle)
                        current_time = time.time()
                        if last_reported_failure and (current_time - last_reported_failure) < 60:  # No reportar más de una vez por minuto
                            print(f"[MONITOR-{monitor_instance.cp_id}] Fallo ya reportado recientemente, esperando antes de reportar de nuevo")
                            consecutive_failures = 0  # Reset para evitar spam
                            await asyncio.sleep(2)
                            continue
                        
                        print(f"[MONITOR-{monitor_instance.cp_id}] 3+ consecutive failures, reporting to Central")
                        
                        # Añadir alerta crítica
                        alert = monitor_instance.add_alert(
                            'critical',
                            f"{monitor_instance.cp_id} reporta 3+ fallos consecutivos (ENGINE_FAILURE)"
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
                            print(f"[MONITOR-{monitor_instance.cp_id}] ENGINE_FAILURE reported to Central")
                            last_reported_failure = current_time  # Marcar que se reportó
                        
                        # Reset contador después de reportar
                        consecutive_failures = 0
                
                # Cerrar conexión de forma segura
                try:
                    writer.close()
                    await asyncio.wait_for(writer.wait_closed(), timeout=0.5)
                except Exception as close_error:
                    # Ignorar errores de cierre - el Engine ya puede haber cerrado la conexión
                    pass
                
            except asyncio.TimeoutError:
                # Timeout durante lectura de respuesta - considerar como fallo
                consecutive_failures += 1
                # Solo imprimir cada 3 fallos para reducir ruido
                if consecutive_failures % 3 == 0 or consecutive_failures <= 3:
                    print(f"[MONITOR-{monitor_instance.cp_id}] Timeout reading response (failure {consecutive_failures}/3)")
                
                shared_state.health_status = {
                    'consecutive_failures': consecutive_failures,
                    'last_check': time.time(),
                    'last_status': 'TIMEOUT'
                }
                
                if consecutive_failures >= 3:
                    # PROTECCIÓN: No reportar fallos durante el período de gracia inicial
                    time_since_start = time.time() - monitor_start_time
                    if time_since_start < startup_grace_period:
                        print(f"[MONITOR-{monitor_instance.cp_id}] Monitor inició hace {time_since_start:.1f}s, esperando a que Engine esté disponible (grace period: {startup_grace_period}s)")
                        consecutive_failures = 0  # Reset durante grace period
                        await asyncio.sleep(2)
                        continue
                    
                    # PROTECCIÓN: No reportar el mismo fallo repetidamente (evitar bucle)
                    current_time = time.time()
                    if last_reported_failure and (current_time - last_reported_failure) < 60:  # No reportar más de una vez por minuto
                        print(f"[MONITOR-{monitor_instance.cp_id}] Fallo ya reportado recientemente, esperando antes de reportar de nuevo")
                        consecutive_failures = 0  # Reset para evitar spam
                        await asyncio.sleep(5)
                        continue
                    
                    print(f"[MONITOR-{monitor_instance.cp_id}] Connection timeouts, reporting to Central")
                    
                    alert = monitor_instance.add_alert(
                        'critical',
                        f"{monitor_instance.cp_id} no responde (3+ timeouts)"
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
                        last_reported_failure = current_time  # Marcar que se reportó
                    
                    consecutive_failures = 0
            
            except (ConnectionRefusedError, OSError) as e:
                # Engine no está corriendo
                consecutive_failures += 1
                # Solo imprimir cada 3 fallos para reducir ruido
                if consecutive_failures % 3 == 0 or consecutive_failures <= 3:
                    print(f"[MONITOR-{monitor_instance.cp_id}] Cannot connect to Engine (failure {consecutive_failures}/3)")
                
                shared_state.health_status = {
                    'consecutive_failures': consecutive_failures,
                    'last_check': time.time(),
                    'last_status': 'CONNECTION_ERROR'
                }
                
                if consecutive_failures >= 3:
                    # PROTECCIÓN: No reportar fallos durante el período de gracia inicial (Engine puede estar iniciando)
                    time_since_start = time.time() - monitor_start_time
                    if time_since_start < startup_grace_period:
                        print(f"[MONITOR-{monitor_instance.cp_id}] Monitor inició hace {time_since_start:.1f}s, esperando a que Engine esté disponible (grace period: {startup_grace_period}s)")
                        consecutive_failures = 0  # Reset durante grace period
                        await asyncio.sleep(2)
                        continue
                    
                    # PROTECCIÓN: No reportar el mismo fallo repetidamente (evitar bucle)
                    current_time = time.time()
                    if last_reported_failure and (current_time - last_reported_failure) < 60:  # No reportar más de una vez por minuto
                        print(f"[MONITOR-{monitor_instance.cp_id}] Engine offline ya reportado recientemente, esperando antes de reportar de nuevo")
                        consecutive_failures = 0  # Reset para evitar spam
                        await asyncio.sleep(5)
                        continue
                    
                    print(f"[MONITOR-{monitor_instance.cp_id}] Engine offline, reporting to Central")
                    
                    alert = monitor_instance.add_alert(
                        'critical',
                        f"{monitor_instance.cp_id} - Engine offline"
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
                        last_reported_failure = current_time  # Marcar que se reportó
                    
                    consecutive_failures = 0
                    
                    # Esperar más tiempo si no podemos conectar
                    await asyncio.sleep(5)
                    
        except asyncio.CancelledError:
            print(f"[MONITOR-{monitor_instance.cp_id}] TCP health monitoring stopped")
            break
        except Exception as e:
            print(f"[MONITOR-{monitor_instance.cp_id}] Error in TCP health check: {e}")
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
        print("ERROR: WebSocket dependencies not installed")
        print("Run: pip install websockets aiohttp")
        return
    
    # Verificar base de datos (opcional, solo warning si no existe)
    db_path = Path('/app/ev_charging.db') if Path('/app/ev_charging.db').exists() else Path(__file__).parent.parent / 'ev_charging.db'
    if not db_path.exists():
        print(" Database not found. Monitor will start anyway (read-only mode)")
    
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
        print(f"\nAccess dashboard: http://localhost:{SERVER_PORT}")
        print(f"Access from network: http://{local_ip}:{SERVER_PORT}\n")
        
        # ========================================================================
        # ARQUITECTURA CORRECTA: Iniciar TCP health check para EL Engine asignado
        # ========================================================================
        print(f"[MONITOR-{monitor_instance.cp_id}] Starting TCP health monitoring...")
        health_check_task = asyncio.create_task(tcp_health_check())
        
        # Iniciar broadcast de actualizaciones
        broadcast_task = asyncio.create_task(broadcast_updates())
        
        # Iniciar listener de Kafka para recibir actualizaciones en tiempo real
        kafka_task = asyncio.create_task(kafka_listener())
        
        print(f"\nAll services started successfully!")
        print(f"TCP monitoring active for {monitor_instance.cp_id}")
        print(f"Engine at {monitor_instance.engine_host}:{monitor_instance.engine_port}")
        print(f"📡 Kafka listener active for real-time updates\n")
        
        # Mantener el servidor corriendo
        await asyncio.gather(broadcast_task, health_check_task, kafka_task)
        
    except Exception as e:
        print(f"\nError starting server: {e}")

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
        print(f"\n\n[MONITOR-{args.cp_id}] Server stopped by user")
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
