import sys
import os
import asyncio
import json
import threading
import time
import argparse
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

# Control fino de verbosidad en consola (no afecta al stream WebSocket)
# Establecer CENTRAL_VERBOSE=1 para ver todos los logs detallados
# Establecer CENTRAL_CPINFO_LOGS=1 para ver los prints de CP_INFO
CENTRAL_VERBOSE = os.environ.get('CENTRAL_VERBOSE', '0') == '1'
CENTRAL_CPINFO_LOGS = os.environ.get('CENTRAL_CPINFO_LOGS', '0') == '1'

# Configuración desde network_config o variables de entorno (Docker)
# Estos valores se sobrescribirán en main() si se pasan argumentos de línea de comandos
KAFKA_BROKER = os.environ.get('KAFKA_BROKER', KAFKA_BROKER_DEFAULT)
KAFKA_TOPICS_CONSUME = [KAFKA_TOPICS['driver_events'], KAFKA_TOPICS['cp_events'], KAFKA_TOPICS['monitor_events']]
KAFKA_TOPIC_PRODUCE = KAFKA_TOPICS['central_events']
SERVER_PORT = int(os.environ.get('CENTRAL_PORT', CENTRAL_CONFIG['ws_port']))

# Estado global compartido
class SharedState:
    def __init__(self):
        self.connected_clients = set()
        self.lock = threading.Lock()
        self.central_start_time = time.time()  # Timestamp de inicio de Central
        self.processed_event_ids = set()  # IDs de eventos ya procesados (para deduplicación)
        self.processed_lock = threading.Lock()  # Lock para processed_event_ids
        self.connected_drivers = set()  # Usernames de drivers conectados
        self.driver_connection_times = {}  # {username: timestamp} para tracking de conexiones
        # Seguimiento de latidos del Monitor por CP
        self.last_monitor_seen = {}  # {cp_id: timestamp}
        self.monitor_timeout_seconds = 5.0  # Timeout de 5 segundos para detectar Monitor caído
        # Sesiones cerradas recientemente para ignorar charging_progress tardíos
        # {session_id: timestamp_cierre}
        self.recently_closed_sessions = {}
        # TTL para ignorar eventos tardíos (segundos)
        self.closed_session_ttl = 600.0  # aumentado desde 10s para suprimir progresos tardíos tras kill
        # Último timestamp de charging_progress por CP para detectar inactividad del Engine
        self.last_progress_per_cp = {}  # {cp_id: timestamp}
        # Umbral de inactividad del Engine (segundos) durante 'charging' antes de cerrar sesión
        try:
            self.engine_inactivity_threshold = float(os.environ.get('ENGINE_INACTIVITY_THRESHOLD', '8.0'))
        except Exception:
            self.engine_inactivity_threshold = 8.0
        # Sesiones ya notificadas como interrumpidas (para no spamear CHARGING_INTERRUPTED)
        self.interrupted_notified_sessions = set()  # {session_id}
        # Marca temporal de fallos de Engine reportados/observados por CP
        self.engine_failure_seen_at = {}  # {cp_id: timestamp}
    

shared_state = SharedState()

class EV_CentralWS:
    """Versión de EV_Central con soporte WebSocket para la interfaz web"""
    
    def __init__(self, kafka_broker='localhost:9092'):
        self.kafka_broker = kafka_broker
        self.producer = None
        self.consumer = None
        self.initialize_kafka()

    def initialize_kafka(self, max_retries=10):
        """Inicializa el productor de Kafka con reintentos"""
        # Permitir configuración por variables de entorno (para despliegues lentos)
        try:
            max_retries = int(os.environ.get('CENTRAL_KAFKA_MAX_RETRIES', max_retries))
        except Exception:
            pass
        base_delay = float(os.environ.get('CENTRAL_KAFKA_RETRY_BASE_DELAY', '1.0'))
        max_delay = float(os.environ.get('CENTRAL_KAFKA_RETRY_MAX_DELAY', '10.0'))
        for attempt in range(max_retries):
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=self.kafka_broker,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
                print(f"[CENTRAL] Kafka producer initialized (bootstrap={self.kafka_broker})")
                return
            except Exception as e:
                print(f"[CENTRAL]  Attempt {attempt+1}/{max_retries} - Kafka not available at {self.kafka_broker}: {e}")
                if attempt < max_retries - 1:
                    # Backoff exponencial con límite
                    delay = min(max_delay, base_delay * (2 ** attempt))
                    time.sleep(delay)
                    continue
                else:
                    print(f"[CENTRAL] Failed to connect to Kafka after {max_retries} attempts (bootstrap={self.kafka_broker})")
    def ensure_producer(self):
        """Asegura que el producer esté disponible, reintentando si es necesario"""
        if self.producer is None:
            print(f"[CENTRAL] Producer not initialized, attempting reconnection...")
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=self.kafka_broker,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
                print(f"[CENTRAL] Kafka producer reconnected successfully")
                return True
            except Exception as e:
                print(f"[CENTRAL] Producer reconnection failed: {e}")
                return False
        return True

    def publish_event(self, event_type, data):
        if not self.ensure_producer():
            return
        
        try:
            event = {
                'message_id': generate_message_id(),
                'event_type': event_type,
                'timestamp': current_timestamp(),
                'source': 'CENTRAL',  # Marcar origen para evitar loops
                **data
            }
            
            # VERIFICACIÓN: Para eventos CP_INFO, asegurar que cp_id está presente
            if event_type == 'CP_INFO':
                cp_id_in_data = data.get('cp_id')
                if not cp_id_in_data:
                    print(f"[CENTRAL] ERROR: CP_INFO event missing cp_id in data! event_type={event_type}, data keys={list(data.keys())}")
                    # Intentar obtener cp_id de data.data si existe
                    nested_data = data.get('data', {})
                    if isinstance(nested_data, dict):
                        cp_id_nested = nested_data.get('cp_id')
                        if cp_id_nested:
                            event['cp_id'] = cp_id_nested
                            event['engine_id'] = cp_id_nested
                            print(f"[CENTRAL]  Fixed: Added cp_id={cp_id_nested} from nested data")
                        else:
                            print(f"[CENTRAL] ERROR: Cannot publish CP_INFO without cp_id!")
                            return
                else:
                    # Verificar que cp_id también está en el nivel raíz del event
                    if 'cp_id' not in event or event['cp_id'] != cp_id_in_data:
                        event['cp_id'] = cp_id_in_data
                        if 'engine_id' not in event:
                            event['engine_id'] = cp_id_in_data
            
            # Enviar al topic central_events para que Monitor lo reciba
            self.producer.send(KAFKA_TOPIC_PRODUCE, event)
            self.producer.flush()
            
            # Log más detallado para CP_INFO
            if event_type == 'CP_INFO':
                if CENTRAL_CPINFO_LOGS or CENTRAL_VERBOSE:
                    cp_id_log = event.get('cp_id', 'UNKNOWN')
                    print(f"[CENTRAL] CP_INFO publicado a {KAFKA_TOPIC_PRODUCE} - cp_id={cp_id_log}")
            else:
                print(f"[CENTRAL] Evento {event_type} publicado a {KAFKA_TOPIC_PRODUCE}")
        except Exception as e:
            print(f"[CENTRAL] Error publicando evento {event_type}: {e}")
            import traceback
            traceback.print_exc()

    def publish_cp_info_to_monitor_with_data(self, cp_id, location, status, max_power_kw=22.0, tariff_per_kwh=0.30, force=False):
        """
        Publica CP_INFO al Monitor usando datos directamente proporcionados en lugar de leer de BD.
        Útil para el registro inicial donde puede haber race condition si leemos de BD inmediatamente.
        
        Args:
            cp_id: ID del CP
            location: Ubicación del CP
            status: Estado del CP
            max_power_kw: Potencia máxima
            tariff_per_kwh: Tarifa
            force: Si es True, fuerza el envío incluso si hay throttling
        """
        if not self.ensure_producer():
            return
        
        try:
            # CRÍTICO: Asegurar que cp_id está presente y es correcto
            if not cp_id or not isinstance(cp_id, str):
                print(f"[CENTRAL] ERROR: Invalid cp_id when publishing CP_INFO: {cp_id}")
                return
            
            # Normalizar location
            if location:
                location = str(location).strip()
            if not location or location == '':
                location = 'Unknown'
            
            # Normalizar status
            status = self._normalize_status(status)
            if not status or status.strip() == '':
                status = 'offline'
            
            # Asegurar que son números
            try:
                max_power_kw = float(max_power_kw) if max_power_kw else 22.0
                tariff_per_kwh = float(tariff_per_kwh) if tariff_per_kwh else 0.30
            except (ValueError, TypeError):
                max_power_kw = 22.0
                tariff_per_kwh = 0.30
            
            # Publicar evento CP_INFO al Monitor con los datos proporcionados
            event_data = {
                'action': 'cp_info_update',
                'cp_id': cp_id,
                'engine_id': cp_id,
                'data': {
                    'cp_id': cp_id,
                    'engine_id': cp_id,
                    'location': location,
                    'localizacion': location,
                    'max_power_kw': float(max_power_kw),
                    'max_kw': float(max_power_kw),
                    'tariff_per_kwh': float(tariff_per_kwh),
                    'tarifa_kwh': float(tariff_per_kwh),
                    'status': status,
                    'estado': status
                },
                # También incluir en el nivel raíz como fallback
                'status': status,
                'estado': status,
                'location': location,
                'localizacion': location,
                'max_power_kw': float(max_power_kw),
                'max_kw': float(max_power_kw),
                'tariff_per_kwh': float(tariff_per_kwh),
                'tarifa_kwh': float(tariff_per_kwh)
            }
            
            self.publish_event('CP_INFO', event_data)
            if CENTRAL_CPINFO_LOGS or CENTRAL_VERBOSE:
                print(f"[CENTRAL]  CP_INFO enviado al Monitor (directo) - CP: {cp_id}, Location: '{location}', Status: {status}, Max Power: {max_power_kw} kW, Tariff: €{tariff_per_kwh}/kWh")
        except Exception as e:
            print(f"[CENTRAL] Error publicando info del CP {cp_id} al Monitor: {e}")
            import traceback
            traceback.print_exc()
    
    def publish_cp_info_to_monitor(self, cp_id, force=False):
        if not hasattr(self, '_last_cp_info_publish'):
            self._last_cp_info_publish = {}
        
        if not force:
            current_time = time.time()
            last_publish = self._last_cp_info_publish.get(cp_id, 0)
            time_since_last = current_time - last_publish
            
            if time_since_last < 3.0:  # Mínimo 3 segundos entre publicaciones del mismo CP
                if CENTRAL_VERBOSE:
                    print(f"[CENTRAL] Throttling: CP_INFO para {cp_id} ya se publicó hace {time_since_last:.2f}s, omitiendo para evitar bucle")
                return
            
            self._last_cp_info_publish[cp_id] = current_time
        
        # PROTECCIÓN ADICIONAL: Verificar que el CP existe en BD antes de publicar
        try:
            cp_check = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
            if not cp_check:
                print(f"[CENTRAL] CP {cp_id} no existe en BD, omitiendo CP_INFO")
                return
        except Exception as e:
            print(f"[CENTRAL] Error verificando CP {cp_id} antes de publicar CP_INFO: {e}")
            return
        
        try:
            # Obtener CP desde BD (la función se llama get_charging_point, no get_charging_point_by_id)
            cp_row = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
            if not cp_row:
                print(f"[CENTRAL] CP {cp_id} no encontrado en BD")
                return
            
            # Obtener información completa del CP desde BD (ya estandarizado)
            cp_info = self._standardize_cp(cp_row)
            
            # Extraer datos del cp_info ya estandarizado con fallbacks
            location = cp_info.get('location') or cp_info.get('localizacion') or ''
            # Normalizar location - eliminar espacios y verificar que no esté vacío
            if location:
                location = str(location).strip()
            if not location or location == '':
                # Si no hay location en cp_info, intentar obtenerla directamente de los datos originales de BD
                location = cp_row.get('localizacion') or cp_row.get('location') or ''
                if location:
                    location = str(location).strip()
                # Si aún está vacío, usar 'Unknown' como último recurso
                if not location or location == '':
                    location = 'Unknown'
                    print(f"[CENTRAL] CP {cp_id} no tiene location en BD, usando 'Unknown'")
                else:
                    print(f"[CENTRAL] CP {cp_id} location obtenida directamente de BD: '{location}'")
            
            status = cp_info.get('status') or cp_info.get('estado') or 'offline'
            status = self._normalize_status(status)
            if not status or status.strip() == '':
                status = 'offline'
            
            max_power = cp_info.get('max_power_kw') or cp_info.get('max_kw') or 22.0
            if not max_power or max_power == 0:
                max_power = 22.0
            
            tariff = cp_info.get('tariff_per_kwh') or cp_info.get('tarifa_kwh') or 0.30
            if not tariff or tariff == 0:
                tariff = 0.30
            
            # CRÍTICO: Asegurar que cp_id está presente y es correcto
            if not cp_id or not isinstance(cp_id, str):
                print(f"[CENTRAL] ERROR: Invalid cp_id when publishing CP_INFO: {cp_id}")
                return
            
            # Publicar evento CP_INFO al Monitor con TODA la información necesaria
            # Incluir tanto en 'data' como en el nivel raíz para asegurar que el Monitor lo reciba
            # IMPORTANTE: cp_id debe estar en el nivel raíz para que el Monitor pueda filtrar correctamente
            event_data = {
                'action': 'cp_info_update',
                'cp_id': cp_id,  # CRÍTICO: Debe estar en nivel raíz para filtrado temprano
                'engine_id': cp_id,  # También incluir engine_id como fallback
                'data': {
                    'cp_id': cp_id,
                    'engine_id': cp_id,
                    'location': location,
                    'localizacion': location,
                    'max_power_kw': float(max_power),
                    'max_kw': float(max_power),
                    'tariff_per_kwh': float(tariff),
                    'tarifa_kwh': float(tariff),
                    'status': status,
                    'estado': status
                },
                # También incluir en el nivel raíz como fallback
                'status': status,
                'estado': status,
                'location': location,
                'localizacion': location,
                'max_power_kw': float(max_power),
                'max_kw': float(max_power),
                'tariff_per_kwh': float(tariff),
                'tarifa_kwh': float(tariff)
            }
            
            # VERIFICACIÓN FINAL: Asegurar que cp_id está presente antes de enviar
            if 'cp_id' not in event_data or event_data['cp_id'] != cp_id:
                print(f"[CENTRAL] ERROR: cp_id mismatch in event_data! cp_id={cp_id}, event_data['cp_id']={event_data.get('cp_id')}")
                event_data['cp_id'] = cp_id
                event_data['engine_id'] = cp_id
            
            self.publish_event('CP_INFO', event_data)
            if CENTRAL_CPINFO_LOGS or CENTRAL_VERBOSE:
                print(f"[CENTRAL]  CP_INFO enviado al Monitor - CP: {cp_id}, Location: '{location}', Status: {status}, Max Power: {max_power} kW, Tariff: €{tariff}/kWh")
            # DEBUG: Verificar que location no esté vacío
            if (CENTRAL_VERBOSE or CENTRAL_CPINFO_LOGS) and (not location or location == '' or location == 'Unknown'):
                print(f"[CENTRAL] ADVERTENCIA: CP_INFO enviado con location vacío o 'Unknown' para CP {cp_id}!")
                print(f"[CENTRAL] DEBUG: cp_row['localizacion'] = '{cp_row.get('localizacion')}', cp_row['location'] = '{cp_row.get('location')}'")
                print(f"[CENTRAL] DEBUG: cp_info['location'] = '{cp_info.get('location')}', cp_info['localizacion'] = '{cp_info.get('localizacion')}'")
        except Exception as e:
            print(f"[CENTRAL] Error publicando info del CP {cp_id} al Monitor: {e}")
            import traceback
            traceback.print_exc()

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
        # Extraer ubicación con múltiples variantes posibles
        # La BD usa 'localizacion' (español), convertir a 'location' (inglés)
        location = cp_row.get('localizacion') or cp_row.get('location') or ''
        # IMPORTANTE: Si location está vacío pero la BD tiene 'Desconocido', mantenerlo
        # No convertir a cadena vacía porque se perdería la información
        if location:
            location = str(location).strip()
        # Si está vacío o es None, mantener cadena vacía (se manejará en publish_cp_info_to_monitor)
        if not location:
            location = ''
        
        # Extraer estado y normalizarlo
        # La BD usa 'estado' (español), convertir a 'status' (inglés)
        raw_status = cp_row.get('estado') or cp_row.get('status') or 'offline'
        status = self._normalize_status(raw_status)
        
        # Extraer potencia máxima
        # La BD usa 'max_kw', convertir a 'max_power_kw'
        max_power = cp_row.get('max_kw') or cp_row.get('max_power_kw')
        if not max_power:
            return False
        
        # Extraer tarifa
        # La BD usa 'tarifa_kwh', convertir a 'tariff_per_kwh'
        tariff = cp_row.get('tarifa_kwh') or cp_row.get('tariff_per_kwh')
        if not tariff:
            tariff = 0.30
        
        return {
            'cp_id': cp_row.get('cp_id'),
            'location': location,
            'localizacion': location,  # Mantener también en español para compatibilidad
            'status': status,
            'estado': status,  # Mantener también en español para compatibilidad
            'max_power_kw': max_power,
            'max_kw': max_power,  # Mantener también en español para compatibilidad
            'tariff_per_kwh': tariff,
            'tarifa_kwh': tariff,  # Mantener también en español para compatibilidad
            'active': cp_row.get('active', 1),
            'power_output': max_power
        }

    def _standardize_user(self, u: dict, has_active_session: bool = False) -> dict:
        """Transforma filas de usuarios español a claves UI."""
        return {
            'id': u.get('id'),
            'username': u.get('nombre'),
            'email': u.get('email'),
            'role': u.get('role'),
            'balance': u.get('balance', 0.0),
            'is_active': has_active_session  # Usuario activo si tiene sesión activa
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
            # Obtener usuarios con estado basado en sesiones activas
            users = []
            try:
                users_raw = db.get_all_users() if hasattr(db, 'get_all_users') else []
                
                # Obtener lista de user_ids con sesiones activas
                conn = db.get_connection()
                cur = conn.cursor()
                cur.execute("""
                    SELECT DISTINCT user_id FROM charging_sesiones WHERE estado = 'active'
                """)
                active_user_ids = {row[0] for row in cur.fetchall()}
                conn.close()
                
                # Combinar usuarios con sesiones activas Y usuarios conectados (sin sesión activa)
                # Un usuario está "activo" si tiene sesión activa O está conectado al sistema
                with shared_state.lock:
                    connected_usernames = shared_state.connected_drivers.copy()
                
                # Debug: mostrar qué usuarios están conectados
                if connected_usernames:
                    print(f"[CENTRAL] DEBUG: Usuarios conectados detectados: {connected_usernames}")
                
                # Obtener user_ids de usuarios conectados
                connected_user_ids = set()
                for u in users_raw:
                    nombre = u.get('nombre') or u.get('username')
                    if nombre in connected_usernames:
                        user_id = u.get('id')
                        connected_user_ids.add(user_id)
                        print(f"[CENTRAL] Usuario {nombre} (id: {user_id}) marcado como conectado")
                
                # Un usuario está activo si tiene sesión activa O está conectado
                active_user_ids = active_user_ids.union(connected_user_ids)
                
                # Debug: mostrar user_ids finales
                if connected_user_ids:
                    print(f"[CENTRAL] DEBUG: User IDs conectados: {connected_user_ids}, User IDs activos totales: {active_user_ids}")
                
                # Mapear usuarios con su estado de sesión activa o conexión
                users = [self._standardize_user(u, u.get('id') in active_user_ids) for u in users_raw]
            except Exception as e:
                print(f"[CENTRAL] Error obteniendo usuarios: {e}")
                users = []
            
            # Obtener puntos de carga y estandarizar campos
            cps_raw = db.get_all_charging_points() if hasattr(db, 'get_all_charging_points') else []
            charging_points = [self._standardize_cp(cp) for cp in cps_raw]
            
            # Sesiones activas
            active_sessions_raw = []
            try:
                conn = db.get_connection()
                cur = conn.cursor()
                # Obtener también energia_kwh si está disponible
                cur.execute("""
                    SELECT s.id, s.cp_id, s.start_time, s.energia_kwh, u.nombre as username
                    FROM charging_sesiones s
                    JOIN usuarios u ON s.user_id = u.id
                    WHERE s.estado = 'active'
                    ORDER BY s.start_time DESC
                """)
                active_sessions_raw = [dict(r) for r in cur.fetchall()]
                conn.close()
                
                # Throttling para mensajes DEBUG: solo imprimir cada 30 segundos
                if not hasattr(shared_state, '_last_dashboard_debug'):
                    shared_state._last_dashboard_debug = 0
                
                current_time = time.time()
                time_since_last_debug = current_time - shared_state._last_dashboard_debug
                
                if time_since_last_debug >= 30.0:  # Solo imprimir cada 30 segundos
                    if CENTRAL_VERBOSE:
                        print(f"[CENTRAL] DEBUG: Sesiones activas encontradas en BD: {len(active_sessions_raw)}")
                        for sess in active_sessions_raw:
                            print(f"[CENTRAL] DEBUG: Sesión activa - Usuario: {sess.get('username')}, CP: {sess.get('cp_id')}, Energía: {sess.get('energia_kwh')}")
                    shared_state._last_dashboard_debug = current_time
            except Exception as e:
                print(f"[CENTRAL] Error obteniendo sesiones activas: {e}")
                import traceback
                traceback.print_exc()
                active_sessions_raw = []

            active_sessions = []
            for session in active_sessions_raw:
                # Usar energía real si está disponible, sino calcular basado en tiempo
                energia_real = session.get('energia_kwh') or 0.0
                
                if energia_real > 0:
                    # Usar energía real del CP_E
                    energy = energia_real
                else:
                    # Calcular energía estimada basado en tiempo transcurrido
                    start_time = datetime.fromtimestamp(session['start_time'])
                    elapsed_hours = (datetime.now() - start_time).total_seconds() / 3600
                    energy = elapsed_hours * 7.4  # Simular 7.4 kW promedio
                
                # Obtener tarifa del CP
                cp_row = db.get_charging_point_by_id(session['cp_id']) if hasattr(db, 'get_charging_point_by_id') else None
                tariff = cp_row.get('tariff_per_kwh') or cp_row.get('tarifa_kwh') or 0.30 if cp_row else 0.30
                cost = energy * tariff
                
                std_session = self._standardize_session(session)
                std_session['energy'] = round(energy, 2)
                std_session['cost'] = round(cost, 2)
                active_sessions.append(std_session)
                
                # Throttling para mensajes DEBUG: solo imprimir cada 30 segundos
                # Este mensaje solo se imprime si el anterior también se imprimió (mismo throttling)
                if not hasattr(shared_state, '_last_dashboard_debug'):
                    shared_state._last_dashboard_debug = 0
                
                current_time = time.time()
                time_since_last_debug = current_time - shared_state._last_dashboard_debug
                
                if time_since_last_debug >= 30.0:  # Solo imprimir cada 30 segundos
                    if CENTRAL_VERBOSE:
                        print(f"[CENTRAL] DEBUG: Sesión procesada - Usuario: {std_session.get('username')}, CP: {std_session.get('cp_id')}, Energía: {std_session.get('energy')} kWh")
            
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
            
            result = {
                'users': users,
                'charging_points': charging_points,
                'active_sessions': active_sessions,
                'stats': stats
            }
            
            # Throttling para el mensaje DEBUG: solo imprimir cada 30 segundos
            if not hasattr(shared_state, '_last_dashboard_debug'):
                shared_state._last_dashboard_debug = 0
            
            current_time = time.time()
            time_since_last_debug = current_time - shared_state._last_dashboard_debug
            
            if time_since_last_debug >= 30.0:  # Solo imprimir cada 30 segundos
                if CENTRAL_VERBOSE:
                    print(f"[CENTRAL] DEBUG: Dashboard data - Sesiones activas: {len(active_sessions)}, Stats: {stats}")
                shared_state._last_dashboard_debug = current_time
            
            return result
            
        except Exception as e:
            print(f"[CENTRAL] Error getting dashboard data: {e}")
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
        if self.ensure_producer():
            try:
                event = {
                    'message_id': generate_message_id(),
                    'event_type': event_type,
                    **data,
                    'timestamp': current_timestamp()
                }
                self.producer.send('central-events', event)
                self.producer.flush()
                if CENTRAL_VERBOSE or event_type not in ('CP_INFO', 'charging_progress', 'MONITOR_HEARTBEAT'):
                    print(f"[CENTRAL] Published event: {event_type} to central-events: {data}")
            except Exception as e:
                print(f"[CENTRAL]  Failed to publish event: {e}")

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
        print(f"[WS] Error handling websocket message: {e}")
    finally:
        shared_state.connected_clients.remove(websocket)
        print(f"[WS] Admin client disconnected. Total clients: {len(shared_state.connected_clients)}")

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
                        
                        # FINALIZAR SESIÓN ACTIVA si existe en este CP
                        try:
                            # Buscar sesión activa en este CP
                            sesiones_activas = db.get_sesiones_actividad()
                            for sesion in sesiones_activas:
                                if sesion.get('cp_id') == cp_id:
                                    session_id = sesion.get('id')
                                    print(f"[CENTRAL] Finalizando sesión {session_id} por error en {cp_id}")
                                    # Finalizar con 0 kWh (error interrumpió la carga)
                                    result = db.end_charging_sesion(session_id, 0.0)
                                    if result:
                                        print(f"[CENTRAL] Sesión {session_id} finalizada por error")
                                    break
                        except Exception as e:
                            print(f"[CENTRAL] Error finalizando sesión en CP con error: {e}")
                        
                        # Actualizar estado en BD
                        db.update_charging_point_status(cp_id, new_status)
                        
                        # PUBLICAR EVENTO EN KAFKA para notificar al Driver
                        central_instance.publish_event('CP_ERROR_SIMULATED', {
                            'cp_id': cp_id,
                            'error_type': error_type,
                            'new_status': new_status,
                            'message': f'Error "{error_type}" simulado en {cp_id}'
                        })
                        print(f"[CENTRAL] Publicado CP_ERROR_SIMULATED en Kafka para {cp_id}")
                        
                        #  PUBLICAR INFORMACIÓN DEL CP AL MONITOR
                        central_instance.publish_cp_info_to_monitor(cp_id)
                        
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
                        
                        # Cambiar estado a available SOLO si es CP_001..CP_004
                        allowed_cps = {'CP_001','CP_002','CP_003','CP_004'}
                        if cp_id in allowed_cps:
                            db.update_charging_point_status(cp_id, 'available')
                        else:
                            # Para otros, mantener/desviar a offline
                            db.update_charging_point_status(cp_id, 'offline')
                        
                        # PUBLICAR EVENTO EN KAFKA para notificar al Driver
                        central_instance.publish_event('CP_ERROR_FIXED', {
                            'cp_id': cp_id,
                            'new_status': 'available' if cp_id in {'CP_001','CP_002','CP_003','CP_004'} else 'offline',
                            'message': f'Error corregido en {cp_id} (disponible solo si CP_001..CP_004)'
                        })
                        print(f"[CENTRAL] Publicado CP_ERROR_FIXED en Kafka para {cp_id}")
                        
                        #  PUBLICAR INFORMACIÓN DEL CP AL MONITOR
                        central_instance.publish_cp_info_to_monitor(cp_id)
                        
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
                    
                    elif msg_type == 'stop_cp':
                        # ============================================================================
                        # REQUISITO 13a) PARAR CP - Fuera de servicio
                        # ============================================================================
                        cp_id = data.get('cp_id')
                        stop_all = data.get('stop_all', False)
                        
                        if stop_all:
                            # Parar TODOS los CPs
                            print(f"[CENTRAL] Parando TODOS los CPs...")
                            all_cps = db.get_all_charging_points() if hasattr(db, 'get_all_charging_points') else []
                            
                            for cp in all_cps:
                                cp_id_item = cp.get('cp_id') or cp.get('id')
                                if cp_id_item:
                                    # Finalizar sesión activa si existe
                                    cp_status = cp.get('status') or cp.get('estado')
                                    if cp_status == 'charging':
                                        try:
                                            sesiones = db.get_active_sessions() if hasattr(db, 'get_active_sessions') else []
                                            for session in sesiones:
                                                if session.get('cp_id') == cp_id_item:
                                                    session_id = session.get('id')
                                                    db.end_charging_sesion(session_id, 0.0)  # 0 kWh por interrupción
                                                    print(f"[CENTRAL] Sesión {session_id} terminada por parada de {cp_id_item}")
                                                    break
                                        except Exception as e:
                                            print(f"[CENTRAL] Error terminando sesión en {cp_id_item}: {e}")
                                    
                                    # Cambiar a out_of_service
                                    db.update_charging_point_status(cp_id_item, 'out_of_service')
                                    
                                    # Publicar comando vía Kafka al CP_E
                                    central_instance.publish_event('CP_STOP', {
                                        'cp_id': cp_id_item,
                                        'action': 'stop',
                                        'new_status': 'out_of_service',
                                        'reason': 'Stopped by admin'
                                    })
                                    
                                    #  PUBLICAR INFORMACIÓN DEL CP AL MONITOR
                                    central_instance.publish_cp_info_to_monitor(cp_id_item)
                            
                            await ws.send_str(json.dumps({
                                'type': 'stop_cp_success',
                                'message': f'Todos los CPs detenidos'
                            }))
                        elif cp_id:
                            # Parar CP específico
                            print(f"[CENTRAL] Parando CP {cp_id}...")
                            
                            # Finalizar sesión activa si existe
                            try:
                                sesiones = db.get_active_sessions() if hasattr(db, 'get_active_sessions') else []
                                for session in sesiones:
                                    if session.get('cp_id') == cp_id:
                                        session_id = session.get('id')
                                        db.end_charging_sesion(session_id, 0.0)  # 0 kWh por interrupción
                                        print(f"[CENTRAL] Sesión {session_id} terminada por parada de {cp_id}")
                                        break
                            except Exception as e:
                                print(f"[CENTRAL] Error terminando sesión en {cp_id}: {e}")
                            
                            # Cambiar estado a out_of_service
                            db.update_charging_point_status(cp_id, 'out_of_service')
                            
                            # Publicar comando vía Kafka al CP_E
                            central_instance.publish_event('CP_STOP', {
                                'cp_id': cp_id,
                                'action': 'stop',
                                'new_status': 'out_of_service',
                                'reason': 'Stopped by admin'
                            })
                            print(f"[CENTRAL] Publicado CP_STOP en Kafka para {cp_id}")
                            
                            #  PUBLICAR INFORMACIÓN DEL CP AL MONITOR
                            central_instance.publish_cp_info_to_monitor(cp_id)
                            
                            await ws.send_str(json.dumps({
                                'type': 'stop_cp_success',
                                'message': f'CP {cp_id} detenido'
                            }))
                        
                        # Broadcast a todos
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
                    
                    elif msg_type == 'resume_cp':
                        # ============================================================================
                        # REQUISITO 13b) REANUDAR CP - Volver a activado
                        # ============================================================================
                        cp_id = data.get('cp_id')
                        resume_all = data.get('resume_all', False)
                        
                        if resume_all:
                            # Reanudar TODOS los CPs
                            print(f"[CENTRAL] Reanudando TODOS los CPs...")
                            all_cps = db.get_all_charging_points() if hasattr(db, 'get_all_charging_points') else []
                            
                            for cp in all_cps:
                                cp_id_item = cp.get('cp_id') or cp.get('id')
                                if cp_id_item:
                                    # Cambiar a available
                                    if cp_id_item in {'CP_001','CP_002','CP_003','CP_004'}:
                                        db.update_charging_point_status(cp_id_item, 'available')
                                    else:
                                        db.update_charging_point_status(cp_id_item, 'offline')
                                    
                                    # Publicar comando vía Kafka al CP_E
                                    central_instance.publish_event('CP_RESUME', {
                                        'cp_id': cp_id_item,
                                        'action': 'resume',
                                        'new_status': 'available',
                                        'reason': 'Resumed by admin'
                                    })
                                    
                                    #  PUBLICAR INFORMACIÓN DEL CP AL MONITOR
                                    central_instance.publish_cp_info_to_monitor(cp_id_item)
                            
                            await ws.send_str(json.dumps({
                                'type': 'resume_cp_success',
                                'message': f'Todos los CPs reanudados'
                            }))
                        elif cp_id:
                            # Reanudar CP específico
                            print(f"[CENTRAL] Reanudando CP {cp_id}...")
                            
                            # Cambiar estado a available SOLO para CP_001..CP_004
                            if cp_id in {'CP_001','CP_002','CP_003','CP_004'}:
                                db.update_charging_point_status(cp_id, 'available')
                            else:
                                db.update_charging_point_status(cp_id, 'offline')
                            
                            # Publicar comando vía Kafka al CP_E
                            central_instance.publish_event('CP_RESUME', {
                                'cp_id': cp_id,
                                'action': 'resume',
                                'new_status': 'available',
                                'reason': 'Resumed by admin'
                            })
                            print(f"[CENTRAL] Publicado CP_RESUME en Kafka para {cp_id}")
                            
                            #  PUBLICAR INFORMACIÓN DEL CP AL MONITOR
                            central_instance.publish_cp_info_to_monitor(cp_id)
                            
                            await ws.send_str(json.dumps({
                                'type': 'resume_cp_success',
                                'message': f'CP {cp_id} reanudado (disponible solo si CP_001..CP_004)'
                            }))
                        
                        # Broadcast a todos
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
                    
                    elif msg_type == 'register_cp':
                        # ============================================================================
                        # REQUISITO a) Recibir peticiones de REGISTRO y ALTA de nuevo punto de recarga
                        # ============================================================================
                        # Este handler procesa peticiones de registro manual desde el dashboard
                        # administrativo. La Central SIEMPRE está escuchando mensajes WebSocket.
                        # ----------------------------------------------------------------------------
                        
                        cp_data = data.get('cp_data', {})
                        cp_id = cp_data.get('cp_id')
                        location = cp_data.get('location')
                        max_power_kw = float(cp_data.get('max_power_kw', 22.0))
                        tariff_per_kwh = float(cp_data.get('tariff_per_kwh', 0.30))
                        
                        # Validar datos requeridos
                        if not cp_id or not location:
                            await ws.send_str(json.dumps({
                                'type': 'register_cp_error',
                                'message': 'CP ID y localización son obligatorios'
                            }))
                            continue
                        
                        # Verificar si el CP ya existe (evitar duplicados)
                        existing_cp = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
                        if existing_cp:
                            await ws.send_str(json.dumps({
                                'type': 'register_cp_error',
                                'message': f'El punto de carga {cp_id} ya existe'
                            }))
                            continue
                        
                        # Registrar el nuevo punto de carga en la base de datos
                        try:
                            if hasattr(db, 'register_or_update_charging_point'):
                                db.register_or_update_charging_point(
                                    cp_id=cp_id,
                                    localizacion=location,
                                    max_kw=max_power_kw,
                                    tarifa_kwh=tariff_per_kwh,
                                    estado='offline'  # Estado inicial offline hasta que se conecte
                                )
                                print(f"[CENTRAL] Nuevo punto de carga registrado: {cp_id} en {location}")
                                
                                #  PUBLICAR INFORMACIÓN DEL CP AL MONITOR
                                central_instance.publish_cp_info_to_monitor(cp_id)
                                
                                # Enviar confirmación al cliente que solicitó el registro
                                await ws.send_str(json.dumps({
                                    'type': 'register_cp_success',
                                    'message': f'Punto de carga {cp_id} registrado exitosamente'
                                }))
                                
                                # Broadcast datos actualizados a TODOS los clientes conectados
                                cps = [central_instance._standardize_cp(cp) for cp in (db.get_all_charging_points() if hasattr(db, 'get_all_charging_points') else [])]
                                dashboard_data = central_instance.get_dashboard_data()
                                for client in shared_state.connected_clients:
                                    try:
                                        await client.send_str(json.dumps({
                                            'type': 'dashboard_data',
                                            'data': dashboard_data
                                        }))
                                    except:
                                        pass
                            else:
                                await ws.send_str(json.dumps({
                                    'type': 'register_cp_error',
                                    'message': 'Función de registro no disponible'
                                }))
                        except Exception as e:
                            print(f"[CENTRAL] Error registrando CP {cp_id}: {e}")
                            await ws.send_str(json.dumps({
                                'type': 'register_cp_error',
                                'message': f'Error al registrar el punto de carga: {str(e)}'
                            }))
                    
                except json.JSONDecodeError:
                    print(f"[WS]  Invalid JSON from {client_id}")
            elif msg.type == web.WSMsgType.ERROR:
                print(f"[WS]  WebSocket error: {ws.exception()}")
                
    except Exception as e:
        print(f"[WS] Error with client {client_id}: {e}")
    finally:
        shared_state.connected_clients.discard(ws)
        print(f"[WS] Admin client disconnected. Total clients: {len(shared_state.connected_clients)}")
    
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
    print(f"[HTTP] Server started on http://0.0.0.0:{SERVER_PORT}")


async def monitor_timeout_checker():
    """
    Detecta Monitores caídos verificando timeouts de heartbeats.
    
    Si un Monitor no envía heartbeat en más de 5 segundos, se marca el CP
    como "Desconectado" y se finalizan sesiones activas.
    """
    print("[CENTRAL] Monitor timeout checker iniciado")
    
    while True:
        await asyncio.sleep(2)  # Verificar cada 2 segundos
        
        current_time = time.time()
        timed_out_cps = []
        
        # Verificar cada CP que ha enviado heartbeat
        for cp_id, last_seen in list(shared_state.last_monitor_seen.items()):
            time_since_heartbeat = current_time - last_seen
            
            if time_since_heartbeat > shared_state.monitor_timeout_seconds:
                timed_out_cps.append((cp_id, time_since_heartbeat))
        
        # Procesar CPs con timeout
        for cp_id, elapsed in timed_out_cps:
            try:
                # Verificar estado actual en BD
                cp = db.get_charging_point(cp_id)
                if not cp:
                    continue
                
                current_status = cp.get('estado') or cp.get('status')
                
                # Solo procesar si no está ya marcado como offline/desconectado
                if current_status not in ['offline', 'desconectado']:
                    print(f"[CENTRAL] Monitor de {cp_id} no responde ({elapsed:.1f}s sin heartbeat) → Marcando CP offline")
                    
                    # Marcar CP como desconectado
                    db.update_charging_point_status(cp_id, 'offline')
                    
                    # Finalizar sesión activa si existe
                    conn = db.get_connection()
                    cur = conn.cursor()
                    cur.execute(
                        """
                        SELECT s.id, s.user_id, s.energia_kwh, s.start_time, u.nombre as username
                        FROM charging_sesiones s
                        JOIN usuarios u ON s.user_id = u.id
                        WHERE s.cp_id = ? AND s.estado = 'active'
                        ORDER BY s.start_time DESC
                        LIMIT 1
                        """,
                        (cp_id,),
                    )
                    active_session = cur.fetchone()
                    if active_session:
                        session_dict = dict(active_session)
                        session_id = session_dict['id']
                        username = session_dict['username']
                        energia = session_dict.get('energia_kwh', 0.0) or 0.0
                        start_time = session_dict.get('start_time')  # epoch seconds

                        # Finalizar sesión cobrando lo consumido y mantener CP en offline
                        result = db.end_charging_sesion(session_id, energia, cp_status_after='offline')
                        cost = result.get('coste', 0.0) if result else 0.0
                        # Calcular duración real de la sesión (antes mostraba 0 en tickets forzados)
                        duration_sec = 0
                        if start_time:
                            try:
                                duration_sec = int(time.time() - float(start_time))
                            except Exception:
                                duration_sec = 0
                        print(f"[CENTRAL] Sesión {session_id} finalizada por timeout de Monitor - Usuario: {username}, Energía: {energia:.2f} kWh, Coste: €{cost:.2f}, Duración: {duration_sec}s")

                        # Publicar evento explícito de parada para que cualquier UI detenga contadores locales
                        try:
                            central_instance.publish_event('charging_stopped', {
                                'action': 'charging_stopped',
                                'cp_id': cp_id,
                                'username': username,
                                'energy_kwh': energia,
                                'cost': cost,
                                'forced': True,
                                'reason': 'monitor_timeout'
                            })
                        except Exception as e:
                            print(f"[CENTRAL] Error publicando charging_stopped forzado tras timeout monitor: {e}")

                        # Notificar ticket final
                        central_instance.publish_event('CHARGING_TICKET', {
                            'username': username,
                            'cp_id': cp_id,
                            'energy_kwh': energia,
                            'cost': cost,
                            'duration_sec': duration_sec,
                            'reason': 'monitor_timeout',
                            'message': f'El Monitor del CP dejó de responder (sin heartbeat por {elapsed:.1f}s)'
                        })
                        try:
                            shared_state.recently_closed_sessions[session_id] = time.time()
                        except Exception:
                            pass
                        # Forzar refresh estado en panel Monitor/Driver
                        try:
                            central_instance.publish_cp_info_to_monitor(cp_id, force=True)
                        except Exception:
                            pass
                    
                    conn.close()
                    
                    # Remover de tracking (se volverá a agregar si Monitor se recupera)
                    del shared_state.last_monitor_seen[cp_id]
                    
            except Exception as e:
                print(f"[CENTRAL] Error procesando timeout de Monitor para {cp_id}: {e}")
                import traceback
                traceback.print_exc()

async def engine_inactivity_checker():
    """Detecta inactividad del Engine: CP en 'charging' sin charging_progress reciente."""
    print("[CENTRAL] Engine inactivity checker iniciado")
    while True:
        await asyncio.sleep(3)
        now = time.time()
        try:
            cps = db.get_all_charging_points() if hasattr(db, 'get_all_charging_points') else []
            for cp in cps:
                cp_id = cp.get('cp_id') or cp.get('id')
                estado = cp.get('estado') or cp.get('status')
                if estado != 'charging':
                    continue
                last_prog = shared_state.last_progress_per_cp.get(cp_id, 0)
                if last_prog == 0:
                    continue
                silence = now - last_prog
                if silence >= shared_state.engine_inactivity_threshold:
                    # Si el Monitor sigue vivo para este CP, NO cerrar sesión: marcar 'fault' y notificar interrupción
                    last_hb = shared_state.last_monitor_seen.get(cp_id, 0)
                    # Usar una ventana de gracia amplia para considerar vivo al Monitor
                    hb_grace = max(shared_state.monitor_timeout_seconds * 3.0, 15.0)
                    monitor_alive = (last_hb > 0) and ((now - last_hb) <= hb_grace)
                    if monitor_alive:
                        try:
                            # Obtener sesión activa
                            conn_e = db.get_connection()
                            cur_e = conn_e.cursor()
                            cur_e.execute("""
                                SELECT s.id, s.user_id, s.energia_kwh, s.start_time, u.nombre as username
                                FROM charging_sesiones s
                                JOIN usuarios u ON s.user_id = u.id
                                WHERE s.cp_id = ? AND s.estado = 'active'
                                ORDER BY s.start_time DESC
                                LIMIT 1
                            """, (cp_id,))
                            row_e = cur_e.fetchone()
                            conn_e.close()
                            if row_e:
                                session_id_e = row_e['id']
                                if session_id_e not in shared_state.interrupted_notified_sessions:
                                    energia_e = (row_e['energia_kwh'] or 0.0)
                                    username_e = row_e.get('username') or ''
                                    # Marcar CP como 'fault' si no lo está
                                    try:
                                        cp_row_cur = db.get_charging_point(cp_id)
                                        prev = (cp_row_cur.get('estado') or cp_row_cur.get('status')) if cp_row_cur else None
                                        if prev != 'fault':
                                            db.update_charging_point_status(cp_id, 'fault')
                                            central_instance.publish_cp_info_to_monitor(cp_id, force=True)
                                    except Exception:
                                        pass
                                    # Notificar interrupción (sin cerrar sesión)
                                    central_instance.publish_event('CHARGING_INTERRUPTED', {
                                        'cp_id': cp_id,
                                        'session_id': session_id_e,
                                        'username': username_e,
                                        'partial_energy_kwh': energia_e,
                                        'reason': 'engine_inactivity_with_monitor',
                                        'message': f'Sin progreso {silence:.1f}s con Monitor activo. Sesión interrumpida, esperando recuperación.'
                                    })
                                    shared_state.interrupted_notified_sessions.add(session_id_e)
                                    print(f"[CENTRAL] Inactividad con Monitor vivo en {cp_id}: marcado 'fault' y notificado CHARGING_INTERRUPTED (sesión {session_id_e})")
                            # Evitar reprocesar inmediatamente este CP
                            shared_state.last_progress_per_cp[cp_id] = 0
                            continue
                        except Exception as e:
                            print(f"[CENTRAL] Error gestionando inactividad con Monitor vivo en {cp_id}: {e}")
                    # Si el Monitor NO está vivo (o no hay heartbeat reciente), cerrar sesión y marcar offline
                    print(f"[CENTRAL] Inactividad Engine detectada en {cp_id} sin Monitor activo ({silence:.1f}s) → marcar fault e interrumpir (no ticket inmediato)")
                    try:
                        # Marcar fault en lugar de offline para mantener semántica de avería
                        db.update_charging_point_status(cp_id, 'fault')
                        central_instance.publish_cp_info_to_monitor(cp_id, force=True)
                        conn_e = db.get_connection()
                        cur_e = conn_e.cursor()
                        cur_e.execute("""
                            SELECT s.id, s.user_id, s.energia_kwh, s.start_time, u.nombre as username
                            FROM charging_sesiones s
                            JOIN usuarios u ON s.user_id = u.id
                            WHERE s.cp_id = ? AND s.estado = 'active'
                            ORDER BY s.start_time DESC
                            LIMIT 1
                        """, (cp_id,))
                        row_e = cur_e.fetchone()
                        conn_e.close()
                        if row_e:
                            session_id_e = row_e['id']
                            energia_e = (row_e['energia_kwh'] or 0.0)
                            username_e = row_e.get('username') or ''
                            if session_id_e not in shared_state.interrupted_notified_sessions:
                                central_instance.publish_event('CHARGING_INTERRUPTED', {
                                    'cp_id': cp_id,
                                    'session_id': session_id_e,
                                    'username': username_e,
                                    'partial_energy_kwh': energia_e,
                                    'reason': 'engine_inactivity_no_monitor',
                                    'message': f'El Engine dejó de enviar progreso ({silence:.1f}s) y no hay Monitor activo. Sesión en pausa.'
                                })
                                shared_state.interrupted_notified_sessions.add(session_id_e)
                            # Registrar evento explícito de error
                            central_instance.publish_event('CP_ENGINE_ERROR', {
                                'cp_id': cp_id,
                                'session_id': session_id_e,
                                'username': username_e,
                                'partial_energy_kwh': energia_e,
                                'message': 'Engine inactivo sin monitor. Estado marcado como averiado. Sin ticket todavía.'
                            })
                        shared_state.last_progress_per_cp[cp_id] = 0
                    except Exception as e:
                        print(f"[CENTRAL] Error manejando inactividad Engine (sin monitor) en {cp_id}: {e}")
        except Exception as e:
            print(f"[CENTRAL] Error en engine_inactivity_checker: {e}")
            import traceback
            traceback.print_exc()

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
    """
    Escucha eventos de Kafka y los broadcast a los clientes WebSocket.
    
    ============================================================================
    CENTRAL SIEMPRE A LA ESPERA (Requisitos a y b)
    ============================================================================
    Esta función implementa un consumer de Kafka que corre en un thread daemon,
    escuchando PERMANENTEMENTE los topics:
    - 'driver-events': Peticiones de conductores (REQUISITO b: autorización de suministro)
    - 'cp-events': Eventos de Charging Points (REQUISITO a: registro de CPs)
    
    El bucle es INFINITO y procesa eventos en tiempo real 24/7.
    ============================================================================
    """
    loop = asyncio.get_event_loop()
    
    def consume_kafka():
        """Función bloqueante que consume de Kafka"""
        # Esperar a que Kafka esté listo
        import time
        # Permitir configurar número de reintentos/retardo vía entorno
        try:
            max_retries = int(os.environ.get('CENTRAL_KAFKA_MAX_RETRIES', '30'))
        except Exception:
            max_retries = 30
        base_delay = float(os.environ.get('CENTRAL_KAFKA_RETRY_BASE_DELAY', '1.0'))
        max_delay = float(os.environ.get('CENTRAL_KAFKA_RETRY_MAX_DELAY', '10.0'))
        retry_count = 0
        consumer = None
        
        while retry_count < max_retries:
            try:
                print(f"[KAFKA] Attempt {retry_count + 1}/{max_retries} to connect to Kafka at {KAFKA_BROKER}")
                
                # CRÍTICO: Usar group_id único en cada inicio para evitar leer mensajes antiguos
                # Esto asegura que Central solo procese mensajes nuevos después de conectarse
                unique_group_id = f'ev_central_ws_group_{int(time.time())}'
                print(f"[KAFKA] Using unique group_id: {unique_group_id} (ignores old messages)")
                
                consumer = KafkaConsumer(
                    *KAFKA_TOPICS_CONSUME,
                    bootstrap_servers=KAFKA_BROKER,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='latest',  # CRÍTICO: Solo mensajes nuevos (después de conectarse)
                    group_id=unique_group_id,  # CRÍTICO: Group ID único por inicio (no reutiliza offsets anteriores)
                    enable_auto_commit=True,  # Guardar progreso
                    # NO especificar api_version - dejar que detecte automáticamente la versión del broker
                    request_timeout_ms=30000,  # 30s - debe ser mayor que session_timeout_ms
                    session_timeout_ms=10000,  # 10s - timeout de sesión del grupo de consumidores
                    max_poll_records=100,  # Procesar hasta 100 mensajes por poll
                    fetch_min_bytes=1,  # Recibir mensajes aunque sean pequeños
                    fetch_max_wait_ms=500  # Esperar máximo 500ms antes de devolver mensajes disponibles
                )
                # Test connection
                consumer.topics()
                print(f"[KAFKA] Connected to Kafka successfully!")
                print(f"[KAFKA] Consumer configured to ONLY read NEW messages (latest offset)")
                
                # Exit del try correcto, break para salir del while
                break
            except Exception as offset_error:
                print(f"[KAFKA] Error connecting to Kafka: {offset_error}")
                import traceback
                traceback.print_exc()
                retry_count += 1
                if retry_count < max_retries:
                    # Backoff exponencial con límite para brokers lentos en arrancar
                    delay = min(max_delay, base_delay * (2 ** (retry_count - 1)))
                    time.sleep(delay)
                    continue
                else:
                    print(f"[KAFKA] Failed to connect after {max_retries} attempts")
                    return
            except Exception as e:
                retry_count += 1
                if consumer:
                    consumer.close()
                print(f"[KAFKA] Attempt {retry_count}/{max_retries} failed: {e}")
                if retry_count < max_retries:
                    delay = min(max_delay, base_delay * (2 ** (retry_count - 1)))
                    time.sleep(delay)
                    continue
                else:
                    print(f"[KAFKA] Failed to connect to Kafka after {max_retries} attempts")
                    return
        
        if not consumer:
            print("[KAFKA] Cannot continue without Kafka connection")
            return
        
        print(f"[KAFKA] Consumer configured and ready. Entering message loop...")
        print(f"[KAFKA] Listening to topics: {KAFKA_TOPICS_CONSUME}")
        print(f"[KAFKA] Consumer is now waiting for messages...")
        
        message_count = 0
        last_heartbeat = time.time()
        
        try:
            
            # ========================================================================
            # BUCLE INFINITO - La Central NUNCA deja de escuchar
            # ========================================================================
            while True:
                try:
                    # Poll con timeout para poder detectar si el consumer está vivo
                    # Aumentar max_records para procesar múltiples mensajes
                    msg_pack = consumer.poll(timeout_ms=2000, max_records=100)
                    
                    # Heartbeat periódico cada 30 segundos para verificar que el bucle está activo
                    current_time = time.time()
                    if current_time - last_heartbeat > 30:
                        print(f"[KAFKA] Consumer alive and waiting for messages (last message #{message_count})")
                        last_heartbeat = current_time
                    
                    # Verificar si hay mensajes
                    if not msg_pack:
                        # No hay mensajes, continuar el bucle
                        continue
                    
                    # Procesar mensajes recibidos
                    for topic_partition, messages in msg_pack.items():
                        for message in messages:
                            message_count += 1
                            try:
                                event = message.value
                                event_type = event.get('event_type', 'UNKNOWN')
                                cp_id = event.get('cp_id') or event.get('engine_id') or 'N/A'
                                message_id = event.get('message_id', 'N/A')[:8] if event.get('message_id') else 'N/A'
                                timestamp = event.get('timestamp', 'N/A')
                                source = event.get('source', 'N/A')
                                
                                # Silenciar eventos repetitivos (heartbeats, progreso) a menos que VERBOSE=1
                                if CENTRAL_VERBOSE or event_type not in ('MONITOR_HEARTBEAT', 'charging_progress', 'CP_INFO'):
                                    print(f"[KAFKA] Received event #{message_count}: {event_type} | CP: {cp_id} | msg_id: {message_id} | topic: {message.topic} | source: {source} | timestamp: {timestamp}")
                            except Exception as e:
                                print(f"[KAFKA] Error deserializing message: {e}")
                                continue
                            
                            # Procesar el evento (solo imprimir tipo para evitar duplicación)
                            event_type = event.get('event_type', 'UNKNOWN')
                            # NO volver a imprimir aquí - ya se imprimió arriba
                            
                            # IMPORTANTE: Todo el procesamiento de eventos se hace en broadcast_kafka_event()
                            # para evitar procesamiento duplicado. Este listener solo consume y pasa eventos.
                            
                            # ====================================================================
                            # MONITOR AUTH: Excepción - procesar aquí porque no debe pasar por broadcast
                            # ====================================================================
                            et = event.get('event_type', '')
                            if et == 'MONITOR_AUTH' or event.get('action', '') == 'authenticate':
                                cp_id = event.get('cp_id')
                                if cp_id:
                                    print(f"[CENTRAL] Monitor autenticado para CP {cp_id}")
                                    # NO publicar CP_INFO aquí - se enviará cuando el Engine se registre
                                    # Esto evita eventos innecesarios. El Monitor recibirá CP_INFO cuando
                                    # Central procese el CP_REGISTRATION del Engine
                                    try:
                                        cp = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
                                        if cp and cp.get('estado'):
                                            # CP ya está registrado - enviar CP_INFO solo una vez si es necesario
                                            # pero con throttling para evitar bucles (el CP_INFO ya se envió en CP_REGISTRATION)
                                            print(f"[CENTRAL] CP {cp_id} ya registrado - Monitor recibirá CP_INFO cuando Engine se registre o ya lo recibió")
                                            # NO publicar CP_INFO aquí - evitar duplicados
                                        else:
                                            print(f"[CENTRAL] CP {cp_id} aún no está registrado, Monitor recibirá CP_INFO cuando Engine se registre")
                                    except Exception as e:
                                        print(f"[CENTRAL] Error verificando CP {cp_id} para Monitor: {e}")
                            
                            # ====================================================================
                            # DRIVER_CONNECTED: Notificación de conexión de Driver
                            # ====================================================================
                            if et == 'DRIVER_CONNECTED':
                                try:
                                    username = event.get('username')
                                    user_id = event.get('user_id')
                                    print(f"[CENTRAL] DEBUG DRIVER_CONNECTED: username={username}, user_id={user_id}, event completo: {event}")
                                    if username:
                                        with shared_state.lock:
                                            shared_state.connected_drivers.add(username)
                                            shared_state.driver_connection_times[username] = time.time()
                                            print(f"[CENTRAL] Driver {username} añadido a connected_drivers. Total conectados: {len(shared_state.connected_drivers)}")
                                            print(f"[CENTRAL] DEBUG: connected_drivers ahora contiene: {shared_state.connected_drivers}")
                                    else:
                                        print(f"[CENTRAL] DRIVER_CONNECTED recibido pero username está vacío")
                                except Exception as e:
                                    print(f"[CENTRAL] Error procesando DRIVER_CONNECTED: {e}")
                                    import traceback
                                    traceback.print_exc()
                            
                            # ====================================================================
                            # DRIVER_DISCONNECTED: Notificación de desconexión de Driver
                            # ====================================================================
                            if et == 'DRIVER_DISCONNECTED':
                                try:
                                    username = event.get('username')
                                    if username:
                                        with shared_state.lock:
                                            shared_state.connected_drivers.discard(username)
                                            shared_state.driver_connection_times.pop(username, None)
                                        print(f"[CENTRAL] Driver {username} desconectado")
                                except Exception as e:
                                    print(f"[CENTRAL] Error procesando DRIVER_DISCONNECTED: {e}")

                            # ====================================================================
                            # REQUEST_ACTIVE_SESSIONS: Driver solicita snapshot tras reconexión
                            # ====================================================================
                            if et == 'REQUEST_ACTIVE_SESSIONS':
                                try:
                                    username = event.get('username')
                                    if not username:
                                        print("[CENTRAL] REQUEST_ACTIVE_SESSIONS sin username")
                                        continue
                                    user = db.get_user_by_username(username)
                                    if not user:
                                        print(f"[CENTRAL] Usuario {username} no encontrado en snapshot")
                                        continue
                                    user_id = user.get('id')
                                    # Obtener sesión activa (sin energia/coste, hacemos query extendida)
                                    conn_snap = db.get_connection()
                                    cur_snap = conn_snap.cursor()
                                    cur_snap.execute("""
                                        SELECT id, cp_id, start_time, energia_kwh, coste, estado, end_time
                                        FROM charging_sesiones
                                        WHERE user_id = ?
                                        ORDER BY start_time DESC
                                        LIMIT 5
                                    """, (user_id,))
                                    rows = cur_snap.fetchall()
                                    conn_snap.close()
                                    sessions_payload = []
                                    now_ts = time.time()
                                    for r in rows:
                                        sid = r['id']
                                        cp_id_row = r['cp_id']
                                        estado_row = r['estado']
                                        energia = r['energia_kwh'] or 0.0
                                        coste = r['coste'] or 0.0
                                        end_time = r['end_time']
                                        # Estado CP
                                        cp_row = db.get_charging_point(cp_id_row) if hasattr(db,'get_charging_point') else None
                                        cp_status_row = None
                                        if cp_row:
                                            cp_status_row = cp_row.get('estado') or cp_row.get('status')
                                        # Interrumpida por fallo Engine?
                                        fail_ts = getattr(shared_state, 'engine_failure_seen_at', {}).get(cp_id_row, 0)
                                        last_hb = shared_state.last_monitor_seen.get(cp_id_row, 0)
                                        hb_grace = max(shared_state.monitor_timeout_seconds * 3.0, 15.0)
                                        monitor_alive = last_hb > 0 and (now_ts - last_hb) <= hb_grace
                                        engine_fail_recent = fail_ts > 0 and (now_ts - fail_ts) <= 60 and monitor_alive
                                        interrupted = engine_fail_recent and estado_row == 'active' and cp_status_row == 'fault'
                                        # Clasificar tipo de snapshot
                                        if estado_row == 'active':
                                            sess_state = 'fault' if cp_status_row == 'fault' else 'active'
                                            ticket_pending = interrupted  # Mientras falla el Engine no habrá ticket final
                                            sessions_payload.append({
                                                'session_id': sid,
                                                'cp_id': cp_id_row,
                                                'session_state': sess_state,
                                                'energy_kwh': energia,
                                                'cost': coste,
                                                'interrupted': interrupted,
                                                'engine_fail_recent': engine_fail_recent,
                                                'ticket_pending': ticket_pending,
                                                'start_time': r['start_time']
                                            })
                                        elif estado_row == 'completed':
                                            # Solo incluir completadas recientes (<15 min) para resumen diferido
                                            if end_time and (now_ts - end_time) <= 900:
                                                duration_sec = end_time - r['start_time'] if end_time else 0
                                                sessions_payload.append({
                                                    'session_id': sid,
                                                    'cp_id': cp_id_row,
                                                    'session_state': 'ended',
                                                    'energy_kwh': energia,
                                                    'cost': coste,
                                                    'duration_sec': duration_sec,
                                                    'ticket_pending': False,
                                                    'start_time': r['start_time'],
                                                    'end_time': end_time
                                                })
                                    central_instance.publish_event('ACTIVE_SESSIONS_STATUS', {
                                        'event_type': 'ACTIVE_SESSIONS_STATUS',
                                        'username': username,
                                        'sessions': sessions_payload,
                                        'timestamp': time.time()
                                    })
                                    print(f"[CENTRAL] Snapshot sesiones enviado a {username}: {len(sessions_payload)} elementos")
                                except Exception as e:
                                    print(f"[CENTRAL] Error procesando REQUEST_ACTIVE_SESSIONS: {e}")
                            
                            # ====================================================================
                            # REQUISITO b) Autorización de suministros - procesar aquí (no en broadcast)
                            # ====================================================================
                            
                            # ====================================================================
                            # REQUISITO b) Autorización de suministros
                            # ====================================================================
                            # La Central procesa dos tipos de eventos para suministros:
                            # 1) Petición de autorización: validación del punto de carga
                            # 2) Inicio de carga: registro de la sesión una vez autorizada
                            # --------------------------------------------------------------------
                            if et == 'AUTHORIZATION_REQUEST':
                                try:
                                    cp_id = event.get('cp_id')
                                    client_id = event.get('client_id')
                                    username = event.get('username')
                                    
                                    print(f"[CENTRAL] DEBUG - cp_id recibido: {cp_id!r} (tipo: {type(cp_id).__name__})")
                                    
                                    if not client_id:
                                        raise ValueError("Client ID es requerido")
                                    
                                    # Broadcast: solicitud de autorización recibida
                                    try:
                                        # Mensaje visible en stream: solicitud
                                        req_cp_text = cp_id if (cp_id and cp_id not in ['None', 'null']) else 'cualquier CP disponible'
                                        asyncio.run_coroutine_threadsafe(
                                            broadcast_system_message(f"🔑 {username or 'usuario'} solicita carga en {req_cp_text}"),
                                            loop
                                        )
                                    except Exception as _:
                                        pass

                                    # Si no se especifica CP, buscar y reservar automáticamente (atómico)
                                    if not cp_id or cp_id == 'None' or cp_id == 'null':
                                        print(f"[CENTRAL] Solicitud de autorización: usuario={username}, buscando CP disponible...")
                                        
                                        # Buscar y reservar atomicamente para evitar condiciones de carrera
                                        cp_id = db.find_and_reserve_available_cp()
                                        
                                        if not cp_id:
                                            central_instance.publish_event('AUTHORIZATION_RESPONSE', {
                                                'client_id': client_id,
                                                'cp_id': None,
                                                'authorized': False,
                                                'reason': 'No hay CPs disponibles'
                                            })
                                            # Broadcast: denegada por no disponibilidad
                                            try:
                                                asyncio.run_coroutine_threadsafe(
                                                    broadcast_system_message("Autorización denegada: no hay CPs disponibles"),
                                                    loop
                                                )
                                            except Exception as _:
                                                pass
                                            continue
                                        
                                        print(f"[CENTRAL] CP {cp_id} asignado y reservado automáticamente para {username}")
                                        
                                        # Ya está reservado, enviar respuesta positiva al Driver
                                        central_instance.publish_event('AUTHORIZATION_RESPONSE', {
                                            'client_id': client_id,
                                            'cp_id': cp_id, 
                                            'authorized': True
                                        })
                                        # Broadcast: concedida
                                        try:
                                            asyncio.run_coroutine_threadsafe(
                                                broadcast_system_message(f"Autorización concedida a {username or 'usuario'} → {cp_id}"),
                                                loop
                                            )
                                        except Exception as _:
                                            pass
                                        
                                        # Obtener user_id si no está en el evento
                                        user_id = event.get('user_id')
                                        if not user_id and username:
                                            try:
                                                user = db.get_user_by_username(username)
                                                if user:
                                                    user_id = user.get('id')
                                                    print(f"[CENTRAL] DEBUG: user_id encontrado para {username}: {user_id}")
                                            except Exception as e:
                                                print(f"[CENTRAL] Error buscando user_id para {username}: {e}")
                                        
                                        # Crear sesión de carga directamente (no enviar evento a Kafka)
                                        if user_id and cp_id:
                                            try:
                                                correlation_id = event.get('correlation_id')
                                                session_id = db.create_charging_session(user_id, cp_id, correlation_id)
                                                if session_id:
                                                    print(f"[CENTRAL] Sesión {session_id} creada para usuario {username} en CP {cp_id}")
                                                else:
                                                    print(f"[CENTRAL] Error: session_id es None")
                                            except Exception as e:
                                                print(f"[CENTRAL] Error creando sesión: {e}")
                                                import traceback
                                                traceback.print_exc()
                                        
                                        # Enviar comando al CP_E para que inicie la carga físicamente
                                        # El CP_E escucha central-events y procesará este comando
                                        central_instance.publish_event('charging_started', {
                                            'action': 'charging_started',
                                            'cp_id': cp_id,
                                            'username': username,
                                            'user_id': user_id,
                                            'client_id': client_id
                                        })
                                        print(f"[CENTRAL] Comando charging_started enviado a CP_E {cp_id} (user_id={user_id})")
                                    else:
                                        # Si se especifica un CP concreto, verificar y reservar
                                        print(f"[CENTRAL] Solicitud de autorización: usuario={username}, cp={cp_id}, client={client_id}")
                                        
                                        # Verificar estado del punto de carga
                                        cp = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
                                        if not cp:
                                            central_instance.publish_event('AUTHORIZATION_RESPONSE', {
                                                'client_id': client_id,
                                                'cp_id': cp_id,
                                                'authorized': False,
                                                'reason': 'CP no encontrado'
                                            })
                                            # Broadcast: denegada por CP inexistente
                                            try:
                                                asyncio.run_coroutine_threadsafe(
                                                    broadcast_system_message(f"Autorización denegada: {cp_id} no existe"),
                                                    loop
                                                )
                                            except Exception as _:
                                                pass
                                            continue
                                            
                                        current_status = cp.get('status') or cp.get('estado')
                                        print(f"[CENTRAL] CP {cp_id} tiene estado: {current_status}")
                                        
                                        # Rechazar si NO está 'available'
                                        if current_status in ('fault', 'out_of_service', 'charging', 'reserved', 'offline'):
                                            central_instance.publish_event('AUTHORIZATION_RESPONSE', {
                                                'client_id': client_id,
                                                'cp_id': cp_id,
                                                'authorized': False,
                                                'reason': f'CP no disponible (estado: {current_status})'
                                            })
                                            # Broadcast: denegada por estado
                                            try:
                                                asyncio.run_coroutine_threadsafe(
                                                    broadcast_system_message(f"Autorización denegada: {cp_id} no disponible ({current_status})"),
                                                    loop
                                                )
                                            except Exception as _:
                                                pass
                                            continue
                                        
                                        # Intentar reservar el punto de carga específico
                                        if db.reserve_charging_point(cp_id):
                                            print(f"[CENTRAL] CP {cp_id} reservado para cliente {client_id}")
                                            central_instance.publish_event('AUTHORIZATION_RESPONSE', {
                                                'client_id': client_id,
                                                'cp_id': cp_id, 
                                                'authorized': True
                                            })
                                            # Broadcast: concedida
                                            try:
                                                asyncio.run_coroutine_threadsafe(
                                                    broadcast_system_message(f"Autorización concedida a {username or 'usuario'} → {cp_id}"),
                                                    loop
                                                )
                                            except Exception as _:
                                                pass
                                            
                                            # Obtener user_id si no está en el evento
                                            user_id = event.get('user_id')
                                            if not user_id and username:
                                                try:
                                                    user = db.get_user_by_username(username)
                                                    if user:
                                                        user_id = user.get('id')
                                                except Exception as e:
                                                    print(f"[CENTRAL] Error buscando user_id para {username}: {e}")
                                            
                                            # Crear sesión de carga directamente (no enviar evento a Kafka)
                                            if user_id and cp_id:
                                                try:
                                                    correlation_id = event.get('correlation_id')
                                                    session_id = db.create_charging_session(user_id, cp_id, correlation_id)
                                                    if session_id:
                                                        print(f"[CENTRAL] Sesión {session_id} creada para usuario {username} en CP {cp_id}")
                                                    else:
                                                        print(f"[CENTRAL] Error: session_id es None")
                                                except Exception as e:
                                                    print(f"[CENTRAL] Error creando sesión: {e}")
                                                    import traceback
                                                    traceback.print_exc()
                                            
                                            # Enviar comando al CP_E para que inicie la carga físicamente
                                            central_instance.publish_event('charging_started', {
                                                'action': 'charging_started',
                                                'cp_id': cp_id,
                                                'username': username,
                                                'user_id': user_id,
                                                'client_id': client_id
                                            })
                                            print(f"[CENTRAL] Comando charging_started enviado a CP_E {cp_id} (user_id={user_id})")
                                        else:
                                            central_instance.publish_event('AUTHORIZATION_RESPONSE', {
                                                'client_id': client_id,
                                                'cp_id': cp_id,
                                                'authorized': False,
                                                'reason': 'No se pudo reservar el CP'
                                            })
                                            # Broadcast: denegada por reserva fallida
                                            try:
                                                asyncio.run_coroutine_threadsafe(
                                                    broadcast_system_message(f"Autorización denegada: no se pudo reservar {cp_id}"),
                                                    loop
                                                )
                                            except Exception as _:
                                                pass
                                except Exception as e:
                                    print(f"[CENTRAL] Error procesando autorización: {e}")
                                    if client_id and cp_id:
                                        central_instance.publish_event('AUTHORIZATION_RESPONSE', {
                                            'client_id': client_id,
                                            'cp_id': cp_id,
                                            'authorized': False,
                                            'reason': f'Error interno: {str(e)}'
                                        })
                                        # Broadcast: denegada por error interno
                                        try:
                                            asyncio.run_coroutine_threadsafe(
                                                broadcast_system_message(f"Autorización denegada: error interno"),
                                                loop
                                            )
                                        except Exception as _:
                                            pass
                            
                            # Los eventos 'charging_started' son peticiones ya autorizadas por
                            # el Driver (que valida usuario, balance, disponibilidad).
                            # La Central actualiza el estado del CP y registra la sesión.
                            # --------------------------------------------------------------------
                            
                            # IMPORTANTE: Pasar TODOS los eventos (excepto los procesados arriba) 
                            # a broadcast_kafka_event() para procesamiento unificado
                            # Esto evita procesamiento duplicado de CP_REGISTRATION y cp_status_change
                            # DRIVER_CONNECTED y DRIVER_DISCONNECTED se procesan aquí, no en broadcast
                            if et not in ['MONITOR_AUTH', 'AUTHORIZATION_REQUEST', 'DRIVER_CONNECTED', 'DRIVER_DISCONNECTED']:
                                try:
                                    asyncio.run_coroutine_threadsafe(
                                        broadcast_kafka_event(event),
                                        loop
                                    )
                                except Exception as e:
                                    print(f"[CENTRAL] Error scheduling broadcast: {e}")
                            
                except Exception as poll_error:
                    # Errores de polling no deberían detener el bucle
                    print(f"[KAFKA] Error during poll: {poll_error}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(1)  # Esperar un poco antes de reintentar
                    continue
                
        except Exception as e:
            print(f"[KAFKA]  Consumer error during loop: {e}")
            import traceback
            traceback.print_exc()
            print(f"[KAFKA] Attempting to reconnect consumer...")
            # Cerrar consumer actual
            try:
                consumer.close()
            except:
                pass
            # Reintentar conexión
            time.sleep(5)
            # Re-ejecutar consume_kafka (recursión limitada)
            print(f"[KAFKA] Restarting consumer...")
            consume_kafka()
    
    # Ejecutar el consumidor de Kafka en un thread separado (daemon = siempre activo)
    kafka_thread = threading.Thread(target=consume_kafka, daemon=True)
    kafka_thread.start()

async def broadcast_kafka_event(event):
    """
    Broadcast un evento de Kafka a todos los clientes WebSocket.
    
    ============================================================================
    Procesamiento de eventos en tiempo real
    ============================================================================
    Esta función procesa TODOS los eventos recibidos de Kafka y actualiza
    el estado del sistema según el tipo de evento:
    
    - REQUISITO a) Registro de CPs: Procesa CP_REGISTRATION y 'connect'
    - REQUISITO b) Autorización de suministro: Procesa 'charging_started'
    ============================================================================
    """
    # IMPORTANTE: Ignorar eventos originados por Central mismo para evitar loops infinitos
    if event.get('source') == 'CENTRAL':
        return  # Central no debe procesar sus propios eventos
    
    # FILTRO: Ignorar eventos que Central genera y que no debe procesar
    event_type = event.get('event_type', '')
    action = event.get('action', '')
    
    # Eventos que Central publica pero no debe procesar cuando los recibe
    events_to_ignore = [
        'CP_INFO',                    # Central lo publica para Monitor
        'AUTHORIZATION_RESPONSE',    # Central lo publica para Driver
        'CHARGING_TICKET',           # Central lo publica para Driver
        'MONITOR_AUTH_RESPONSE',     # Central lo publica para Monitor
        'CP_STOP',                   # Comandos que Central envía (no procesar respuestas)
        'CP_RESUME',                 # Comandos que Central envía
        'CP_ERROR_SIMULATED',        # Comandos que Central envía
        'CP_ERROR_FIXED',            # Comandos que Central envía
        'CP_PLUG_IN',                # Comandos que Central envía
        'CP_UNPLUG',                 # Comandos que Central envía
        'charging_started',           # Ya procesado en consume_kafka antes de broadcast
        # NOTA: CHARGING_TIMEOUT NO se ignora - Driver lo envía y Central debe procesarlo
        'CHARGING_INTERRUPTED'       # Eventos que Central genera
    ]
    
    if event_type in events_to_ignore or action in events_to_ignore:
        print(f"[CENTRAL] Ignorando evento {event_type or action} - es un evento que Central genera o ya procesó")
        return
    
    # DEDUPLICACIÓN: Ignorar eventos ya procesados por message_id
    message_id = event.get('message_id')
    if message_id:
        with shared_state.processed_lock:
            if message_id in shared_state.processed_event_ids:
                print(f"[CENTRAL] Evento ya procesado (message_id={message_id[:8]}...), ignorando: {event.get('event_type', 'UNKNOWN')}")
                return
            # Marcar como procesado ANTES de procesarlo (para evitar procesamiento paralelo)
            shared_state.processed_event_ids.add(message_id)
            # Limpiar IDs antiguos para evitar memoria infinita (mantener últimos 1000)
            if len(shared_state.processed_event_ids) > 1000:
                # Mantener solo los últimos 500 (limpiar los más antiguos)
                shared_state.processed_event_ids = set(list(shared_state.processed_event_ids)[-500:])
    
    # IMPORTANTE: Calcular current_time una vez para usar en todas las verificaciones
    import time
    current_time = time.time()
    
    # DEDUPLICACIÓN ADICIONAL: Evitar procesar el mismo tipo de evento para el mismo CP en muy poco tiempo
    # Esto previene bucles cuando el mismo evento llega con diferentes message_ids
    cp_id = event.get('cp_id') or event.get('engine_id')
    event_type = event.get('event_type', '')
    action = event.get('action', '')
    
    # Solo aplicar a eventos de CP que pueden causar bucles
    if cp_id and (event_type in ['CP_REGISTRATION', 'cp_status_change'] or action in ['connect', 'cp_status_change']):
        if not hasattr(shared_state, 'recent_cp_events'):
            shared_state.recent_cp_events = {}  # {(cp_id, event_type): timestamp}
        event_key = (cp_id, event_type or action)
        last_event_time = shared_state.recent_cp_events.get(event_key, 0)
        
        # Ignorar si el mismo evento para el mismo CP ocurrió hace menos de 2 segundos
        if current_time - last_event_time < 2.0:
            print(f"[CENTRAL] Evento {event_type or action} para CP {cp_id} procesado hace {current_time - last_event_time:.2f}s, ignorando duplicado")
            # Quitar del set si ya lo añadimos
            if message_id:
                with shared_state.processed_lock:
                    shared_state.processed_event_ids.discard(message_id)
            return
        
        # Registrar timestamp de este evento
        shared_state.recent_cp_events[event_key] = current_time
        
        # Limpiar eventos antiguos (más de 30 segundos)
        keys_to_remove = [k for k, t in shared_state.recent_cp_events.items() if current_time - t > 30.0]
        for k in keys_to_remove:
            del shared_state.recent_cp_events[k]
    
    # PROTECCIÓN: Ignorar eventos muy antiguos que pueden ser de antes del reinicio
    # current_time ya se calculó arriba en la deduplicación adicional
    central_start_time = shared_state.central_start_time
    time_since_start = current_time - central_start_time
    
    # Verificar timestamp del evento si existe
    event_timestamp = event.get('timestamp')
    if event_timestamp:
        try:
            # Calcular diferencia de tiempo
            event_time = float(event_timestamp)
            age_seconds = current_time - event_time
            
            # Ignorar eventos con más de 30 segundos de antigüedad respecto al tiempo actual
            # Esto asegura que solo procesamos eventos recientes (después del reinicio)
            if age_seconds > 30:  # 30 segundos
                print(f"[CENTRAL] Ignorando evento antiguo ({age_seconds:.0f}s de antigüedad, probablemente de antes del reinicio): {event.get('event_type', 'UNKNOWN')}")
                # Quitar del set si ya lo añadimos
                if message_id:
                    with shared_state.processed_lock:
                        shared_state.processed_event_ids.discard(message_id)
                return
            
            # Si Central acaba de iniciar (menos de 30 segundos), ignorar eventos que sean más antiguos que el inicio
            if time_since_start < 30:
                # El evento debe ser más reciente que el inicio de Central
                if event_time < central_start_time:
                    print(f"[CENTRAL] Ignorando evento anterior al reinicio (Central inició hace {time_since_start:.1f}s): {event.get('event_type', 'UNKNOWN')}")
                    # Quitar del set si ya lo añadimos
                    if message_id:
                        with shared_state.processed_lock:
                            shared_state.processed_event_ids.discard(message_id)
                    return
        except (ValueError, TypeError):
            # Si el timestamp no es válido, verificar si Central acaba de iniciar
            if time_since_start < 30:
                # Si Central acaba de iniciar y el evento no tiene timestamp válido, es probablemente antiguo
                print(f"[CENTRAL] Ignorando evento sin timestamp válido (Central inició hace {time_since_start:.1f}s): {event.get('event_type', 'UNKNOWN')}")
                # Quitar del set si ya lo añadimos
                if message_id:
                    with shared_state.processed_lock:
                        shared_state.processed_event_ids.discard(message_id)
                return
    else:
        # Si el evento no tiene timestamp, y Central acaba de iniciar, ignorarlo
        if time_since_start < 30:
            print(f"[CENTRAL] Ignorando evento sin timestamp (Central inició hace {time_since_start:.1f}s): {event.get('event_type', 'UNKNOWN')}")
            # Quitar del set si ya lo añadimos
            if message_id:
                with shared_state.processed_lock:
                    shared_state.processed_event_ids.discard(message_id)
            return
    
    # PROTECCIÓN ADICIONAL: Evitar procesar CP_REGISTRATION repetidamente
    # (action, event_type y cp_id ya se calcularon arriba)
    # incluso si tienen diferentes message_ids (pueden ser reintentos)
    if (event_type == 'CP_REGISTRATION' or action == 'connect') and cp_id:
        # Verificar si este CP se registró recientemente (últimos 10 segundos)
        if not hasattr(shared_state, 'recent_registrations'):
            shared_state.recent_registrations = {}  # {cp_id: timestamp}
        
        # current_time ya se calculó arriba en la deduplicación adicional
        recent_reg_time = shared_state.recent_registrations.get(cp_id, 0)
        
        # Si se registró recientemente, ignorar registros duplicados
        if current_time - recent_reg_time < 10.0:
            print(f"[CENTRAL] CP {cp_id} ya se registró recientemente ({current_time - recent_reg_time:.1f}s), ignorando registro duplicado")
            return
        
        # Verificar también en BD si ya está registrado como 'available'
        try:
            cp_existing = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
            if cp_existing:
                existing_status = cp_existing.get('estado') or cp_existing.get('status')
                # Solo ignorar si ya está 'available' - permitir si está 'offline' (necesita reconexión)
                if existing_status == 'available':
                    print(f"[CENTRAL] CP {cp_id} ya registrado como 'available' en BD, ignorando registro duplicado")
                    return
                # Si está 'offline', permitir el registro (reconexión después de reinicio)
                elif existing_status == 'offline':
                    print(f"[CENTRAL] CP {cp_id} está 'offline', permitiendo reconexión después de reinicio de Central")
        except Exception as e:
            print(f"[CENTRAL] Error verificando CP existente: {e}")
    
    # Silenciar eventos repetitivos (heartbeats, progreso) a menos que VERBOSE=1
    event_type_for_log = event.get('event_type', 'UNKNOWN')
    if CENTRAL_VERBOSE or event_type_for_log not in ('MONITOR_HEARTBEAT', 'charging_progress', 'CP_INFO'):
        print(f"[KAFKA] Processing event for broadcast: {event_type_for_log}, clients: {len(shared_state.connected_clients)}")
    
    # Determinar el tipo de evento y formatearlo para el dashboard
    action = event.get('action', '')
    event_type = event.get('event_type', '')

    # ========================================================================
    # EVENTOS DEL MONITOR
    # ========================================================================
    
    # Monitor conectado
    if event_type == 'MONITOR_CONNECTED' or action == 'monitor_connected':
        mon_cp_id = event.get('cp_id')
        if mon_cp_id:
            shared_state.last_monitor_seen[mon_cp_id] = time.time()
            print(f"[CENTRAL] Monitor conectado para {mon_cp_id}")
        return
    
    # Monitor desconectado (cierre limpio)
    if event_type == 'MONITOR_DISCONNECTED' or action == 'monitor_disconnected':
        mon_cp_id = event.get('cp_id')
        if mon_cp_id:
            try:
                # Marcar CP como desconectado
                db.update_charging_point_status(mon_cp_id, 'offline')
                print(f"[CENTRAL] Monitor desconectado para {mon_cp_id} → CP marcado offline")
                
                # Finalizar sesión activa si existe
                conn = db.get_connection()
                cur = conn.cursor()
                cur.execute("""
                    SELECT s.id, s.user_id, s.energia_kwh, u.nombre as username
                    FROM charging_sesiones s
                    JOIN usuarios u ON s.user_id = u.id
                    WHERE s.cp_id = ? AND s.estado = 'active'
                """, (mon_cp_id,))
                active_session = cur.fetchone()
                
                if active_session:
                    session_dict = dict(active_session)
                    session_id = session_dict['id']
                    username = session_dict['username']
                    energia = session_dict.get('energia_kwh', 0.0) or 0.0
                    
                    # Finalizar sesión cobrando lo consumido y mantener CP en offline
                    result = db.end_charging_sesion(session_id, energia, cp_status_after='offline')
                    cost = result.get('coste', 0.0) if result else 0.0
                    print(f"[CENTRAL] Sesión {session_id} finalizada por desconexión de Monitor - Usuario: {username}, Energía: {energia:.2f} kWh, Coste: €{cost:.2f}")
                    # Registrar en event_log el motivo
                    try:
                        db.log_event(
                            correlacion_id=None,
                            mensaje_id=generate_message_id(),
                            tipo_evento='CHARGE_ENDED',
                            component='EV_Central',
                            detalles={
                                'session_id': session_id,
                                'cp_id': mon_cp_id,
                                'username': username,
                                'end_reason': 'monitor_failure',
                                'sub_reason': 'monitor_disconnected',
                                'energy_kwh': energia,
                                'cost': cost
                            }
                        )
                    except Exception:
                        pass
                    
                    # Notificar al driver
                    central_instance.publish_event('CHARGING_TICKET', {
                        'username': username,
                        'cp_id': mon_cp_id,
                        'energy_kwh': energia,
                        'cost': cost,
                        'reason': 'monitor_disconnected',
                        'message': 'El Monitor del CP se desconectó durante la carga'
                    })
                
                conn.close()
            except Exception as e:
                print(f"[CENTRAL] Error procesando MONITOR_DISCONNECTED para {mon_cp_id}: {e}")
        return
    
    # Heartbeat del Monitor
    if event_type == 'MONITOR_HEARTBEAT' or action == 'monitor_heartbeat':
        hb_cp_id = event.get('cp_id')
        if hb_cp_id:
            shared_state.last_monitor_seen[hb_cp_id] = time.time()
            # Log reducido para no inundar
            if not hasattr(shared_state, '_last_hb_log'):
                shared_state._last_hb_log = {}
            last_log = shared_state._last_hb_log.get(hb_cp_id, 0)
            now_ts = time.time()
            if now_ts - last_log >= 30.0:
                print(f"[CENTRAL] Heartbeat de Monitor para {hb_cp_id}")
                shared_state._last_hb_log[hb_cp_id] = now_ts
        return
    
    # ========================================================================
    # NUEVO: Procesar confirmación de salud del Engine enviada por el Monitor
    # ========================================================================
    if event_type == 'ENGINE_HEALTH_OK' or action == 'report_engine_ok':
        cp_id_ok = event.get('cp_id')
        if cp_id_ok:
            try:
                # Registrar heartbeat implícito
                shared_state.last_monitor_seen[cp_id_ok] = time.time()
                # Consultar estado actual antes de forzar 'available'
                current_status = None
                try:
                    current_status = db.get_charging_point_status(cp_id_ok)
                except Exception:
                    current_status = None
                # Sólo permitir 'available' para CP_001..CP_004 y si NO está offline
                allowed_cps = {'CP_001','CP_002','CP_003','CP_004'}
                if cp_id_ok in allowed_cps and current_status != 'offline':
                    db.update_charging_point_status(cp_id_ok, 'available')
                    print(f"[CENTRAL] Salud confirmada para {cp_id_ok} → estado 'available' (permitido)")
                else:
                    # Mantener offline o estado actual para CP fuera del rango permitido
                    if cp_id_ok not in allowed_cps:
                        print(f"[CENTRAL] ENGINE_HEALTH_OK: {cp_id_ok} no está en lista permitida (1..4) → estado permanece '{current_status}'")
                    else:
                        print(f"[CENTRAL] ENGINE_HEALTH_OK ignorado: {cp_id_ok} permanece 'offline'")
                # Publicar CP_INFO al Monitor para refrescar paneles (siempre para reflejar estado actual)
                central_instance.publish_cp_info_to_monitor(cp_id_ok, force=True)
            except Exception as e:
                print(f"[CENTRAL] Error procesando ENGINE_HEALTH_OK para {cp_id_ok}: {e}")
        return
    
    # ========================================================================
    # Persistir cambios de estado relevantes SIEMPRE
    # (incluso si no hay clientes WebSocket conectados)
    # ========================================================================
    cp_id = event.get('cp_id') or event.get('engine_id')
    if cp_id:
        # --------------------------------------------------------------------
        # REQUISITO a) AUTO-REGISTRO cuando un CP se conecta
        # --------------------------------------------------------------------
        if action in ['connect'] or event_type in ['CP_REGISTRATION']:
            # Auto-registro/actualización del CP al conectar
            try:
                cp = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
                data = event.get('data', {}) if isinstance(event.get('data'), dict) else {}
                # Extraer localización con múltiples fallbacks para asegurar que se obtiene correctamente
                # CRÍTICO: El Engine envía location en data.location y data.localizacion
                localizacion = (data.get('localizacion') or data.get('location') or 
                              event.get('localizacion') or event.get('location') or '')
                # Normalizar location - eliminar espacios
                if localizacion:
                    localizacion = str(localizacion).strip()
                if not localizacion or localizacion == '':
                    # Si aún no hay location, intentar obtenerla de la BD si el CP ya existe
                    if cp:
                        localizacion = cp.get('localizacion') or cp.get('location') or ''
                        if localizacion:
                            localizacion = str(localizacion).strip()
                    # Si aún está vacío, usar 'Desconocido' como último recurso
                    if not localizacion or localizacion == '':
                        localizacion = 'Desconocido'
                        print(f"[CENTRAL] CP {cp_id} no tiene location en CP_REGISTRATION, usando 'Desconocido'")
                else:
                    print(f"[CENTRAL] CP {cp_id} location extraída de CP_REGISTRATION: '{localizacion}'")
                
                max_kw = data.get('max_kw') or data.get('max_power_kw') or 22.0
                tarifa_kwh = data.get('tarifa_kwh') or data.get('tariff_per_kwh') or data.get('price_eur_kwh') or 0.30
                # Estado inicial: forzar 'offline' por defecto al registrarse
                estado = 'offline'
                # Excepción: si CP ya existe y es uno de los permitidos iniciales y está 'available', mantenerlo
                try:
                    cp_existing = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
                except Exception:
                    cp_existing = None
                if cp_existing:
                    prev_status = cp_existing.get('estado') or cp_existing.get('status')
                    # Mantener 'available' en re-registro para los 4 CP principales
                    if cp_id in ('CP_001', 'CP_002', 'CP_003', 'CP_004') and prev_status == 'available':
                        estado = 'available'
                print(f"[CENTRAL] Auto-reg CP on connect: cp_id={cp_id}, loc={localizacion}, max_kw={max_kw}, tarifa={tarifa_kwh}")
                # Verificar si el CP ya existe antes de registrar (cp_existing calculado arriba)
                
                # Registrar o actualizar
                if hasattr(db, 'register_or_update_charging_point'):
                    db.register_or_update_charging_point(cp_id, localizacion, max_kw=max_kw, tarifa_kwh=tarifa_kwh, estado=estado)
                else:
                    # Fallback: intentar solo actualizar estado
                    db.update_charging_point_status(cp_id, estado)
                
                # REGISTRAR timestamp del registro para ignorar cp_status_change subsecuentes
                if not hasattr(shared_state, 'recent_registrations'):
                    shared_state.recent_registrations = {}
                import time
                shared_state.recent_registrations[cp_id] = time.time()
                
                # CRÍTICO: Para nuevo registro inicial, enviar CP_INFO con los datos del evento directamente
                # en lugar de leer de BD inmediatamente (puede haber race condition donde BD aún no se ha actualizado)
                # Guardar los datos que acabamos de procesar para enviarlos al Monitor
                registration_location = localizacion
                registration_status = estado
                
                # Confirmar existencia y enviar CP_INFO solo una vez
                cp_after = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
                if cp_after:
                    stored_location = cp_after.get('localizacion') or cp_after.get('location') or 'Desconocido'
                    stored_status = cp_after.get('estado') or cp_after.get('status') or 'offline'
                    # Si stored_location está vacío pero tenemos registration_location, usar la del registro
                    if (not stored_location or stored_location == '' or stored_location == 'Desconocido') and registration_location:
                        stored_location = registration_location
                    print(f"[CENTRAL] CP registrado/actualizado: {cp_after['cp_id']} en '{stored_location}' estado={stored_status}" )
                    #  PUBLICAR INFORMACIÓN DEL CP AL MONITOR solo si es nuevo registro o cambió realmente
                    # IMPORTANTE: Evitar publicar CP_INFO innecesariamente para prevenir bucles
                    previous_status = cp_existing.get('estado') if cp_existing else None
                    previous_location = cp_existing.get('localizacion') or cp_existing.get('location') if cp_existing else None
                    previous_max_kw = cp_existing.get('max_kw') if cp_existing else None
                    previous_tariff = cp_existing.get('tarifa_kwh') if cp_existing else None
                    
                    # Verificar si realmente hay cambios
                    status_changed = previous_status != estado
                    location_changed = previous_location != localizacion
                    max_kw_changed = abs((previous_max_kw or 0) - max_kw) > 0.01 if previous_max_kw else True
                    tariff_changed = abs((previous_tariff or 0) - tarifa_kwh) > 0.01 if previous_tariff else True
                    
                    # CRÍTICO: Si es nuevo CP O si cambió de 'offline' a 'available', SIEMPRE enviar CP_INFO al Monitor
                    # Esto asegura que cuando los Engines se registran, el Monitor recibe la información correcta inmediatamente
                    # También enviar si location cambió de vacío/Unknown a un valor real
                    should_send = False
                    send_reason = ""
                    
                    if not cp_existing:
                        should_send = True
                        send_reason = "nuevo CP"
                    elif status_changed and previous_status == 'offline' and estado == 'available':
                        should_send = True
                        send_reason = "offline→available"
                    elif location_changed and (previous_location == '' or previous_location == 'Unknown' or previous_location == 'Desconocido'):
                        should_send = True
                        send_reason = f"location actualizada: '{previous_location}' → '{localizacion}'"
                    elif status_changed or location_changed or max_kw_changed or tariff_changed:
                        should_send = True
                        send_reason = "datos cambiaron"
                    
                    if should_send:
                        # Nuevo CP o hay cambios, publicar información al Monitor
                        if not cp_existing:
                            print(f"[CENTRAL] Nuevo CP {cp_id} registrado, enviando CP_INFO al Monitor (location: '{registration_location}', status: {registration_status})")
                            # CRÍTICO: Para nuevos CPs, usar los datos del registro directamente
                            # para evitar race condition donde BD aún no se ha actualizado
                            central_instance.publish_cp_info_to_monitor_with_data(
                                cp_id, registration_location, registration_status, max_kw, tarifa_kwh, force=True
                            )
                        elif status_changed and previous_status == 'offline' and estado == 'available':
                            print(f"[CENTRAL] CP {cp_id} se registró (offline→available), enviando CP_INFO al Monitor (location: '{registration_location}')")
                            # CRÍTICO: Para reconexión, usar los datos del registro directamente
                            central_instance.publish_cp_info_to_monitor_with_data(
                                cp_id, registration_location, registration_status, max_kw, tarifa_kwh, force=True
                            )
                        else:
                            print(f"[CENTRAL] CP {cp_id} cambió ({send_reason}), enviando CP_INFO al Monitor (location: '{localizacion}', status: {estado})")
                            central_instance.publish_cp_info_to_monitor(cp_id, force=(status_changed and previous_status == 'offline'))
                    else:
                        # Mismo estado y datos, no publicar (evitar bucles)
                        print(f"[CENTRAL] CP {cp_id} ya registrado sin cambios (status={estado}, location='{stored_location}'), omitiendo CP_INFO para evitar bucle")
                else:
                    print(f"[CENTRAL] No se pudo verificar CP {cp_id} tras auto-registro")
            except Exception as e:
                print(f"[CENTRAL] Error auto-registrando CP {cp_id}: {e}")
        
        # --------------------------------------------------------------------
        # REQUISITO b) AUTORIZACIÓN DE SUMINISTRO - Sesión iniciada
        # --------------------------------------------------------------------
        elif action in ['charging_started']:
            # Crear sesión de carga y cambiar estado del CP
            username = event.get('username')
            user_id = event.get('user_id')
            
            print(f"[CENTRAL] DEBUG charging_started: username={username}, user_id={user_id}, cp_id={cp_id}")
            
            # Si no tenemos user_id, buscarlo por username
            if not user_id and username:
                try:
                    user = db.get_user_by_username(username)
                    if user:
                        user_id = user.get('id')
                        print(f"[CENTRAL] DEBUG: user_id encontrado para {username}: {user_id}")
                    else:
                        print(f"[CENTRAL] Usuario {username} no encontrado en BD")
                except Exception as e:
                    print(f"[CENTRAL] Error buscando usuario {username}: {e}")
            
            if user_id and cp_id:
                try:
                    # Crear sesión de carga (esto cambia el CP a 'charging')
                    print(f"[CENTRAL] DEBUG: Creando sesión - user_id={user_id}, cp_id={cp_id}")
                    session_id = db.create_charging_session(user_id, cp_id, event.get('correlation_id'))
                    if session_id:
                        print(f"[CENTRAL] Suministro iniciado - Sesión {session_id} en CP {cp_id} para usuario {username}")
                        #  PUBLICAR CAMBIO DE ESTADO AL MONITOR (CP ahora en 'charging')
                        central_instance.publish_cp_info_to_monitor(cp_id)
                    else:
                        print(f"[CENTRAL] Error creando sesión de carga para CP {cp_id} - session_id es None")
                except Exception as e:
                    print(f"[CENTRAL] Error al crear sesión: {e}")
                    import traceback
                    traceback.print_exc()
                else:
                    print(f"[CENTRAL] No se puede crear sesión: user_id={user_id}, cp_id={cp_id}")
                # Fallback: solo cambiar estado
                if cp_id:
                    db.update_charging_point_status(cp_id, 'charging')
                    print(f"[CENTRAL] ⚡ CP {cp_id} ahora en modo 'charging' (sin sesión)")
                    #  PUBLICAR CAMBIO DE ESTADO AL MONITOR
                    central_instance.publish_cp_info_to_monitor(cp_id)
        
        elif action in ['charging_stopped']:
            # Finalizar sesión de carga y liberar CP (salvo que sea consecuencia de caída de Engine)
            username = event.get('username')
            user_id = event.get('user_id')
            energy_kwh = event.get('energy_kwh', 0)
            forced = event.get('forced')  # Parada forzosa (monitor timeout u otra causa)
            reason = event.get('reason') or ('forced_stop' if forced else 'manual_stop')

            print(f"[CENTRAL] Procesando charging_stopped: user={username}, cp={cp_id}, energy={energy_kwh}")

            # -----------------------------------------------------------------
            # GUARD CLAUSE: Si el Engine ha caído recientemente con Monitor vivo,
            # NO cerrar ni ticketear. Emitimos interrupción + error y, si procede,
            # forzamos estado 'fault'. Evita comportarse como kill de Monitor.
            # -----------------------------------------------------------------
            recent_fail_ts = getattr(shared_state, 'engine_failure_seen_at', {}).get(cp_id, 0)
            fail_age = time.time() - recent_fail_ts if recent_fail_ts else 9999
            # ¿Monitor vivo?
            last_hb_cs = shared_state.last_monitor_seen.get(cp_id, 0) if cp_id else 0
            hb_grace_cs = max(shared_state.monitor_timeout_seconds * 3.0, 15.0)
            monitor_alive_cs = last_hb_cs > 0 and (time.time() - last_hb_cs) <= hb_grace_cs
            blocked_reasons = {'manual_stop', 'forced_stop', 'monitor_timeout'}
            engine_fail_active = (cp_id and monitor_alive_cs and fail_age <= 60)
            if engine_fail_active and reason not in blocked_reasons and not forced:
                try:
                    # Marcar CP como 'fault' si no lo está
                    try:
                        current_cp_status = db.get_charging_point_status(cp_id)
                    except Exception:
                        current_cp_status = None
                    if current_cp_status != 'fault':
                        db.update_charging_point_status(cp_id, 'fault')
                        central_instance.publish_cp_info_to_monitor(cp_id, force=True)
                    active_sessions_cf = db.get_active_sessions_for_cp(cp_id) if hasattr(db, 'get_active_sessions_for_cp') else []
                    if not active_sessions_cf and hasattr(db, 'get_all_sessions'):
                        all_sessions_cf = db.get_all_sessions()
                        active_sessions_cf = [s for s in all_sessions_cf if s.get('cp_id') == cp_id and s.get('estado') == 'active']
                    if active_sessions_cf:
                        sess_cf = active_sessions_cf[0]
                        sess_id_cf = sess_cf.get('id')
                        energia_parcial_cf = sess_cf.get('energia_kwh') or 0.0
                        user_id_cf = sess_cf.get('user_id')
                        user_cf = db.get_user_by_id(user_id_cf) if hasattr(db, 'get_user_by_id') else None
                        username_cf = username or (user_cf.get('username') if user_cf else '')
                        if sess_id_cf not in getattr(shared_state, 'interrupted_notified_sessions', set()):
                            central_instance.publish_event('CHARGING_INTERRUPTED', {
                                'cp_id': cp_id,
                                'session_id': sess_id_cf,
                                'username': username_cf,
                                'user_id': user_id_cf,
                                'partial_energy_kwh': energia_parcial_cf,
                                'reason': 'engine_failure_charging_stopped',
                                'message': 'Interrupción por fallo de Engine. Sesión sigue abierta sin ticket.'
                            })
                            try:
                                shared_state.interrupted_notified_sessions.add(sess_id_cf)
                            except Exception:
                                pass
                        central_instance.publish_event('CP_ENGINE_ERROR', {
                            'cp_id': cp_id,
                            'session_id': sess_id_cf,
                            'username': username_cf,
                            'partial_energy_kwh': energia_parcial_cf,
                            'message': 'Fallo de Engine detectado. Sesión sigue abierta sin ticket final.'
                        })
                        print(f"[CENTRAL] charging_stopped convertido en interrupción (ENGINE_FAILURE reciente) sesión={sess_id_cf}")
                        return
                except Exception as e:
                    print(f"[CENTRAL] Error en guard clause engine_fail_active en charging_stopped: {e}")
            
            # ENVIAR COMANDO AL CP_E PARA QUE DETENGA LA CARGA
            if cp_id:
                central_instance.publish_event('charging_stopped', {
                    'action': 'charging_stopped',
                    'cp_id': cp_id,
                    'username': username,
                    'user_id': user_id,
                    'energy_kwh': energy_kwh,
                    'forced': forced,
                    'reason': reason
                })
                print(f"[CENTRAL] Comando charging_stopped enviado a CP_E {cp_id}")

            # Si es parada forzosa, intentar cerrar inmediatamente la sesión activa por CP (aunque falte user_id)
            if forced and cp_id:
                try:
                    conn_f = db.get_connection()
                    cur_f = conn_f.cursor()
                    cur_f.execute("""
                        SELECT s.id, s.user_id, s.start_time, s.energia_kwh
                        FROM charging_sesiones s
                        WHERE s.cp_id = ? AND s.estado = 'active'
                        ORDER BY s.start_time DESC
                        LIMIT 1
                    """, (cp_id,))
                    row = cur_f.fetchone()
                    conn_f.close()
                    if row:
                        session_id_f = row['id']
                        user_id_f = row['user_id']
                        start_time_f = row['start_time']
                        # Usar la energía reportada si es mayor, si no la de la sesión
                        energia_final = energy_kwh if energy_kwh >= (row['energia_kwh'] or 0) else (row['energia_kwh'] or 0)
                        result_f = db.end_charging_sesion(session_id_f, energia_final, cp_status_after='offline')
                        final_cost_f = result_f.get('coste', 0.0) if result_f else 0.0
                        duration_sec_f = 0
                        if start_time_f:
                            try:
                                duration_sec_f = int(time.time() - float(start_time_f))
                            except Exception:
                                duration_sec_f = 0
                        # BLOQUEO: Si hubo fallo Engine reciente y monitor vivo, NO enviar ticket, solo marcar fault y error.
                        recent_fail_forced = getattr(shared_state, 'engine_failure_seen_at', {}).get(cp_id, 0)
                        last_hb_forced = shared_state.last_monitor_seen.get(cp_id, 0)
                        hb_grace_forced = max(shared_state.monitor_timeout_seconds * 3.0, 15.0)
                        monitor_alive_forced = last_hb_forced > 0 and (time.time() - last_hb_forced) <= hb_grace_forced
                        fail_age_forced = time.time() - recent_fail_forced if recent_fail_forced else 9999
                        engine_fail_path = monitor_alive_forced and fail_age_forced <= 60
                        if engine_fail_path:
                            # Mantener sesión abierta, estado fault, y emitir error (sin ticket)
                            try:
                                current_cp_status_f = db.get_charging_point_status(cp_id)
                                if current_cp_status_f != 'fault':
                                    db.update_charging_point_status(cp_id, 'fault')
                                    central_instance.publish_cp_info_to_monitor(cp_id, force=True)
                            except Exception:
                                pass
                            central_instance.publish_event('CP_ENGINE_ERROR', {
                                'cp_id': cp_id,
                                'session_id': session_id_f,
                                'username': username,
                                'partial_energy_kwh': energia_final,
                                'message': 'Parada forzada mientras Engine caído. Sesión sigue abierta, sin ticket.'
                            })
                            # Notificación de interrupción (si no enviada)
                            if session_id_f not in getattr(shared_state, 'interrupted_notified_sessions', set()):
                                central_instance.publish_event('CHARGING_INTERRUPTED', {
                                    'cp_id': cp_id,
                                    'session_id': session_id_f,
                                    'username': username,
                                    'partial_energy_kwh': energia_final,
                                    'reason': 'engine_failure_forced_stop',
                                    'message': 'Stopped forzado durante fallo de Engine. Esperando recuperación.'
                                })
                                try:
                                    shared_state.interrupted_notified_sessions.add(session_id_f)
                                except Exception:
                                    pass
                            print(f"[CENTRAL] (FORZADA) Parada en fallo Engine: sesión {session_id_f} permanece abierta sin ticket")
                        else:
                            central_instance.publish_event('CHARGING_TICKET', {
                            'username': username,
                            'user_id': user_id_f,
                            'cp_id': cp_id,
                            'energy_kwh': energia_final,
                            'cost': final_cost_f,
                            'duration_sec': duration_sec_f,
                            'reason': reason,
                            'forced': True,
                            'timestamp': time.time()
                            })
                            print(f"[CENTRAL] (FORZADA) Sesión {session_id_f} cerrada con ticket: energía={energia_final:.2f} kWh, coste=€{final_cost_f:.2f}, duración={duration_sec_f}s")
                        # Marcar sesión como cerrada (ignorar progresos tardíos)
                        try:
                            shared_state.recently_closed_sessions[session_id_f] = time.time()
                        except Exception:
                            pass
                        # Publicar CP_INFO para refrescar paneles tras liberación
                        central_instance.publish_cp_info_to_monitor(cp_id, force=True)
                        return  # Evitar flujo estándar (ya cerrado)
                except Exception as e:
                    print(f"[CENTRAL] Error cerrando sesión forzada por cp_id {cp_id}: {e}")
            
            # 1. Si no tenemos user_id, buscar por username
            if not user_id and username:
                try:
                    user = db.get_user_by_username(username)
                    if user:
                        user_id = user.get('id')
                except Exception as e:
                    print(f"[CENTRAL] Error buscando usuario {username}: {e}")
            
            # 2. Buscar sesión activa del usuario
            try:
                if user_id:
                    session = db.get_active_sesion_for_user(user_id)
                    if session:
                        session_id = session.get('id')
                        start_time = session.get('start_time')
                        
                        # 3. Finalizar sesión en BD (usa end_charging_sesion, no session)
                        if session_id:
                            result = db.end_charging_sesion(session_id, energy_kwh)
                            if result:
                                final_cost = result.get('coste', 0)
                                # Calcular duración
                                duration_sec = 0
                                if start_time:
                                    duration_sec = int(time.time() - start_time)
                                
                                print(f"[CENTRAL] Sesión {session_id} finalizada: {energy_kwh} kWh, coste=€{final_cost:.2f}")
                                
                                # ENVIAR TICKET FINAL AL CONDUCTOR (vía Kafka)
                                # Bloqueo: si hubo fallo Engine reciente y monitor vivo, sustituir ticket por error y mantener sesión abierta
                                recent_fail_manual = getattr(shared_state, 'engine_failure_seen_at', {}).get(cp_id, 0)
                                last_hb_manual = shared_state.last_monitor_seen.get(cp_id, 0)
                                hb_grace_manual = max(shared_state.monitor_timeout_seconds * 3.0, 15.0)
                                monitor_alive_manual = last_hb_manual > 0 and (time.time() - last_hb_manual) <= hb_grace_manual
                                fail_age_manual = time.time() - recent_fail_manual if recent_fail_manual else 9999
                                engine_fail_path_manual = monitor_alive_manual and fail_age_manual <= 60
                                if engine_fail_path_manual:
                                    try:
                                        current_cp_status_m = db.get_charging_point_status(cp_id)
                                        if current_cp_status_m != 'fault':
                                            db.update_charging_point_status(cp_id, 'fault')
                                            central_instance.publish_cp_info_to_monitor(cp_id, force=True)
                                    except Exception:
                                        pass
                                    central_instance.publish_event('CP_ENGINE_ERROR', {
                                        'username': username,
                                        'user_id': user_id,
                                        'cp_id': cp_id,
                                        'session_id': session_id,
                                        'partial_energy_kwh': energy_kwh,
                                        'message': 'Parada manual recibida durante fallo de Engine. Sesión sigue abierta sin ticket.'
                                    })
                                    if session_id not in getattr(shared_state,'interrupted_notified_sessions', set()):
                                        central_instance.publish_event('CHARGING_INTERRUPTED', {
                                            'cp_id': cp_id,
                                            'session_id': session_id,
                                            'username': username,
                                            'partial_energy_kwh': energy_kwh,
                                            'reason': 'engine_failure_manual_stop',
                                            'message': 'Stop manual durante fallo de Engine. Esperando recuperación.'
                                        })
                                        try:
                                            shared_state.interrupted_notified_sessions.add(session_id)
                                        except Exception:
                                            pass
                                    print(f"[CENTRAL] Ticket suprimido por fallo Engine reciente en sesión {session_id}")
                                else:
                                    central_instance.publish_event('CHARGING_TICKET', {
                                    'username': username,
                                    'user_id': user_id,
                                    'cp_id': cp_id,
                                    'energy_kwh': energy_kwh,
                                    'cost': final_cost,
                                    'duration_sec': duration_sec,
                                    'reason': 'manual_stop',
                                    'timestamp': time.time()
                                    })
                                    print(f"[CENTRAL] Ticket enviado a conductor {username}")
                                # Marcar sesión como cerrada para ignorar charging_progress tardíos
                                try:
                                    shared_state.recently_closed_sessions[session_id] = time.time()
                                except Exception:
                                    pass
                            else:
                                print(f"[CENTRAL] Error finalizando sesión {session_id}")
                        
                        # Note: end_charging_sesion ya libera el CP automáticamente
                        #  PUBLICAR CAMBIO DE ESTADO AL MONITOR
                        central_instance.publish_cp_info_to_monitor(cp_id)
                    else:
                        print(f"[CENTRAL] No se encontró sesión activa para user_id={user_id}")
                        # Liberar el CP solo si no está offline
                        if cp_id:
                            current_status = db.get_charging_point_status(cp_id)
                            if current_status != 'offline':
                                db.update_charging_point_status(cp_id, 'available')
                            #  PUBLICAR CAMBIO DE ESTADO AL MONITOR
                            central_instance.publish_cp_info_to_monitor(cp_id)
                else:
                    print(f"[CENTRAL] No se pudo obtener user_id para {username}")
                    # Liberar el CP solo si no está offline
                    if cp_id:
                        current_status = db.get_charging_point_status(cp_id)
                        if current_status != 'offline':
                            db.update_charging_point_status(cp_id, 'available')
                        #  PUBLICAR CAMBIO DE ESTADO AL MONITOR
                        central_instance.publish_cp_info_to_monitor(cp_id)
            except Exception as e:
                print(f"[CENTRAL] Error procesando charging_stopped: {e}")
                import traceback
                traceback.print_exc()
                # Liberar el CP solo si no está offline
                if cp_id:
                    current_status = db.get_charging_point_status(cp_id)
                    if current_status != 'offline':
                        db.update_charging_point_status(cp_id, 'available')
                    #  PUBLICAR CAMBIO DE ESTADO AL MONITOR
                    central_instance.publish_cp_info_to_monitor(cp_id)
        
        # ========================================================================
        # TIMEOUT: CP no respondió después de autorización
        # ========================================================================
        elif action in ['charging_timeout'] or event_type == 'CHARGING_TIMEOUT':
            username = event.get('username')
            reason = event.get('reason', 'CP no respondió después de autorización')
            
            print(f"[CENTRAL] Procesando CHARGING_TIMEOUT: user={username}, cp={cp_id}, reason={reason}")
            
            # Buscar sesión activa y cancelarla
            try:
                if username:
                    user = db.get_user_by_username(username)
                    if user:
                        user_id = user.get('id')
                        session = db.get_active_sesion_for_user(user_id)
                        if session:
                            session_id = session.get('id')
                            # Cancelar sesión (sin energía consumida)
                            if hasattr(db, 'cancel_charging_session'):
                                db.cancel_charging_session(session_id)
                            else:
                                # Fallback: finalizar con 0 energía
                                db.end_charging_sesion(session_id, 0.0)
                            print(f"[CENTRAL] Sesión {session_id} cancelada por timeout")
            except Exception as e:
                print(f"[CENTRAL] Error cancelando sesión por timeout: {e}")
            
            # Liberar el CP (cambiar a 'available') salvo que esté 'offline'
            try:
                if cp_id:
                    current_status = db.get_charging_point_status(cp_id)
                    if current_status != 'offline':
                        db.update_charging_point_status(cp_id, 'available')
                        print(f"[CENTRAL] CP {cp_id} liberado después de timeout")
                    else:
                        print(f"[CENTRAL] charging_timeout: CP {cp_id} permanece 'offline' (monitor caído/timeout)")
                    #  PUBLICAR CAMBIO/ESTADO AL MONITOR
                    central_instance.publish_cp_info_to_monitor(cp_id)
            except Exception as e:
                print(f"[CENTRAL] Error liberando CP {cp_id}: {e}")
        
        # ========================================================================
        # REQUISITO 9: Desenchufe manual desde CP - Enviar ticket al conductor
        # ========================================================================
        elif action in ['charging_completed']:
            username = event.get('username')
            user_id = event.get('user_id')
            energy_kwh = event.get('energy_kwh', 0)
            cost = event.get('cost', 0)
            duration_sec = event.get('duration_sec', 0)
            reason = event.get('reason', 'unknown')
            
            print(f"[CENTRAL] Procesando charging_completed (desenchufe): user={username}, cp={cp_id}, energy={energy_kwh}")
            
            # 1. Buscar user_id si no lo tenemos
            if not user_id and username:
                try:
                    user = db.get_user_by_username(username)
                    if user:
                        user_id = user.get('id')
                except Exception as e:
                    print(f"[CENTRAL] Error buscando usuario {username}: {e}")
            
            # 2. Buscar y finalizar sesión activa
            try:
                if user_id:
                    session = db.get_active_sesion_for_user(user_id)
                    if session:
                        session_id = session.get('id')
                        
                        # Finalizar sesión en BD
                        if session_id:
                            result = db.end_charging_sesion(session_id, energy_kwh)
                            if result:
                                final_cost = result.get('coste', cost)
                                print(f"[CENTRAL] Sesión {session_id} finalizada por desenchufe")
                                print(f"[CENTRAL]    Usuario: {username}, Energía: {energy_kwh:.2f} kWh, Coste: €{final_cost:.2f}")
                                
                                # 3. ENVIAR TICKET FINAL AL CONDUCTOR (vía Kafka)
                                central_instance.publish_event('CHARGING_TICKET', {
                                    'username': username,
                                    'user_id': user_id,
                                    'cp_id': cp_id,
                                    'energy_kwh': energy_kwh,
                                    'cost': final_cost,
                                    'duration_sec': duration_sec,
                                    'reason': reason,
                                    'timestamp': time.time()
                                })
                                print(f"[CENTRAL] Ticket enviado a conductor {username}")
                                try:
                                    shared_state.recently_closed_sessions[session_id] = time.time()
                                except Exception:
                                    pass
                            else:
                                print(f"[CENTRAL] Error finalizando sesión {session_id}")
                        
                        # end_charging_sesion ya libera el CP automáticamente
                    else:
                        print(f"[CENTRAL] No se encontró sesión activa para user_id={user_id}")
                        if cp_id:
                            current_status = db.get_charging_point_status(cp_id)
                            if current_status != 'offline':
                                db.update_charging_point_status(cp_id, 'available')
                            #  PUBLICAR CAMBIO DE ESTADO AL MONITOR
                            central_instance.publish_cp_info_to_monitor(cp_id)
                else:
                    print(f"[CENTRAL] No se pudo obtener user_id para {username}")
                    if cp_id:
                        current_status = db.get_charging_point_status(cp_id)
                        if current_status != 'offline':
                            db.update_charging_point_status(cp_id, 'available')
                        #  PUBLICAR CAMBIO DE ESTADO AL MONITOR
                        central_instance.publish_cp_info_to_monitor(cp_id)
            except Exception as e:
                print(f"[CENTRAL] Error procesando charging_completed: {e}")
                import traceback
                traceback.print_exc()
                if cp_id:
                    current_status = db.get_charging_point_status(cp_id)
                    if current_status != 'offline':
                        db.update_charging_point_status(cp_id, 'available')
                    #  PUBLICAR CAMBIO DE ESTADO AL MONITOR
                    central_instance.publish_cp_info_to_monitor(cp_id)
        
        # ========================================================================
        # ACTUALIZACIÓN DE PROGRESO DE CARGA (del CP_E)
        # ========================================================================
        elif action in ['charging_progress'] or event_type == 'charging_progress':
            # PROTECCIÓN: Throttling para charging_progress - no actualizar más de una vez por segundo
            # porque el Engine envía actualizaciones cada segundo
            if not hasattr(shared_state, '_last_progress_update'):
                shared_state._last_progress_update = {}  # {(username, cp_id): timestamp}

            username = event.get('username')
            energy_kwh = event.get('energy_kwh', 0.0)
            cost = event.get('cost', 0.0)
            # Registrar timestamp de progreso para detección de inactividad
            if cp_id:
                shared_state.last_progress_per_cp[cp_id] = time.time()
            # Ignorar progreso si el CP no está en 'charging' o si la sesión se cerró recientemente
            try:
                if cp_id:
                    cp_row = db.get_charging_point(cp_id)
                    cp_state = (cp_row.get('estado') or cp_row.get('status')) if cp_row else None
                    # Aceptar progreso también cuando el CP está en 'fault' si la sesión sigue activa
                    if cp_state and cp_state not in ('charging', 'fault'):
                        if CENTRAL_VERBOSE:
                            print(f"[CENTRAL] Ignorando charging_progress para {cp_id} en estado {cp_state}")
                        return
                if username:
                    user = db.get_user_by_username(username)
                    if user:
                        user_id = user.get('id')
                        session = db.get_active_sesion_for_user(user_id)
                        if not session:
                            return
                        sid = session.get('id')
                        closed_at = shared_state.recently_closed_sessions.get(sid)
                        if closed_at and (current_time - closed_at) < getattr(shared_state, 'closed_session_ttl', 10.0):
                            return
            except Exception:
                pass

            progress_key = (username or '', cp_id or '')
            last_update_time = shared_state._last_progress_update.get(progress_key, 0)
            if current_time - last_update_time < 0.5:
                pass
            else:
                shared_state._last_progress_update[progress_key] = current_time
                if CENTRAL_VERBOSE:
                    print(f"[CENTRAL] Progreso de carga: {username} → {energy_kwh:.2f} kWh, €{cost:.2f}")
                try:
                    if username:
                        user = db.get_user_by_username(username)
                        if user:
                            user_id = user.get('id')
                            session = db.get_active_sesion_for_user(user_id)
                            if session:
                                session_id = session.get('id')
                                conn = db.get_connection()
                                cur = conn.cursor()
                                cur.execute("""
                                    UPDATE charging_sesiones
                                    SET energia_kwh = ?
                                    WHERE id = ? AND estado = 'active'
                                """, (energy_kwh, session_id))
                                conn.commit()
                                conn.close()
                                if int(current_time) % 5 == 0:
                                    print(f"[CENTRAL] Sesión {session_id} actualizada: {energy_kwh:.2f} kWh")
                except Exception as e:
                    print(f"[CENTRAL] Error actualizando progreso de sesión: {e}")
        
        elif action in ['cp_status_change']:
            """
            IMPORTANTE: Este evento viene del Engine que YA cambió su estado.
            Central solo debe ACTUALIZAR la BD para reflejar el cambio, NO causar más cambios.
            No debe publicar eventos que puedan causar que el Engine vuelva a cambiar estado.
            """
            status = event.get('status')
            if not status:
                print(f"[CENTRAL] cp_status_change sin 'status', ignorando")
                return
            
            # PROTECCIÓN: Ignorar cp_status_change que viene justo después de CP_REGISTRATION
            # porque el registro ya incluye el estado 'available'
            # Verificar si este CP se registró recientemente (últimos 5 segundos)
            if not hasattr(shared_state, 'recent_registrations'):
                shared_state.recent_registrations = {}  # {cp_id: timestamp}
            
            import time
            current_time = time.time()
            recent_reg_time = shared_state.recent_registrations.get(cp_id, 0)
            
            if current_time - recent_reg_time < 5.0 and status == 'available':
                print(f"[CENTRAL] Ignorando cp_status_change a 'available' para CP {cp_id} - ya registrado recientemente ({current_time - recent_reg_time:.1f}s)")
                return
            
            # Asegurar CP existe antes de actualizar
            try:
                if not db.get_charging_point_by_id(cp_id) and hasattr(db, 'register_or_update_charging_point'):
                    db.register_or_update_charging_point(cp_id, 'Desconocido', max_kw=22.0, tarifa_kwh=0.30, estado=status)
                    print(f"[CENTRAL] CP auto-creado en cp_status_change: {cp_id}")
            except Exception as e:
                print(f"[CENTRAL] Error asegurando CP en cp_status_change: {e}")
            
            # Solo actualizar BD si el estado cambió realmente (sincronización con Engine)
            cp_current = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
            current_status = cp_current.get('estado') or cp_current.get('status') if cp_current else None
            
            # CRÍTICO: Solo actualizar BD si el estado realmente cambió
            # NO publicar CP_INFO cuando el estado ya está sincronizado para evitar bucles infinitos
            # El Monitor ya recibe el cp_status_change del Engine directamente
            if current_status == status:
                print(f"[CENTRAL] Estado {status} para CP {cp_id} ya está sincronizado en BD, omitiendo actualización para evitar bucle")
                # NO llamar a publish_cp_info_to_monitor aquí porque ya está sincronizado
                # Esto previene bucles infinitos cuando el estado no cambió realmente
                return
            
            # PROTECCIÓN ADICIONAL: Si el estado es 'available' y hubo un registro reciente, ignorar
            # Esto evita que cp_status_change a 'available' después de CP_REGISTRATION cause bucles
            if status == 'available':
                if not hasattr(shared_state, 'recent_registrations'):
                    shared_state.recent_registrations = {}
                recent_reg_time = shared_state.recent_registrations.get(cp_id, 0)
                if recent_reg_time > 0:
                    time_since_reg = time.time() - recent_reg_time
                    if time_since_reg < 5.0:  # Si se registró hace menos de 5 segundos
                        print(f"[CENTRAL] Ignorando cp_status_change a 'available' para CP {cp_id} - ya registrado recientemente ({time_since_reg:.1f}s)")
                        return
            
            # PROTECCIÓN CRÍTICA: Ignorar cp_status_change a 'offline' si el CP se acaba de registrar como 'available'
            # Esto previene que mensajes antiguos de Kafka o reinicios de Engine causen que los CPs vuelvan a 'offline'
            # después de haberse registrado correctamente
            if status == 'offline' and current_status == 'available':
                if not hasattr(shared_state, 'recent_registrations'):
                    shared_state.recent_registrations = {}
                recent_reg_time = shared_state.recent_registrations.get(cp_id, 0)
                if recent_reg_time > 0:
                    time_since_reg = time.time() - recent_reg_time
                    if time_since_reg < 30.0:  # Si se registró hace menos de 30 segundos, ignorar cambio a 'offline'
                        print(f"[CENTRAL] Ignorando cp_status_change a 'offline' para CP {cp_id} - acaba de registrarse como 'available' hace {time_since_reg:.1f}s")
                        print(f"[CENTRAL]    Esto previene que mensajes antiguos de Kafka o reinicios causen desconexión incorrecta")
                        return

            # Recuperar lógica de interrupción: charging→offline + fallo reciente + monitor vivo => fault + CHARGING_INTERRUPTED
            if status == 'offline':
                now_ts2 = time.time()
                last_fail_ts2 = getattr(shared_state, 'engine_failure_seen_at', {}).get(cp_id, 0)
                last_hb2 = shared_state.last_monitor_seen.get(cp_id, 0)
                hb_grace2 = max(shared_state.monitor_timeout_seconds * 3.0, 15.0)
                monitor_alive2 = last_hb2 > 0 and (now_ts2 - last_hb2) <= hb_grace2
                failure_recent2 = last_fail_ts2 > 0 and (now_ts2 - last_fail_ts2) <= 25.0
                if monitor_alive2 and failure_recent2:
                    print(f"[CENTRAL] DIAG: offline mientras charging con monitor vivo y fallo Engine reciente → fault. hb_age={(now_ts2 - last_hb2):.1f}s fail_age={(now_ts2 - last_fail_ts2):.1f}s")
                    try:
                        cp_row_cur = db.get_charging_point(cp_id)
                        prev = (cp_row_cur.get('estado') or cp_row_cur.get('status')) if cp_row_cur else None
                        if prev != 'fault':
                            db.update_charging_point_status(cp_id, 'fault')
                            central_instance.publish_cp_info_to_monitor(cp_id, force=True)
                        # Sesión activa
                        conn_it = db.get_connection()
                        cur_it = conn_it.cursor()
                        cur_it.execute("""
                            SELECT s.id, s.user_id, s.energia_kwh, s.start_time, u.nombre as username
                            FROM charging_sesiones s
                            JOIN usuarios u ON s.user_id = u.id
                            WHERE s.cp_id = ? AND s.estado = 'active'
                            ORDER BY s.start_time DESC
                            LIMIT 1
                        """, (cp_id,))
                        active_row = cur_it.fetchone()
                        conn_it.close()
                        if active_row:
                            session_id_it = active_row['id']
                            if session_id_it not in shared_state.interrupted_notified_sessions:
                                energia_it = (active_row['energia_kwh'] or 0.0)
                                username_it = active_row.get('username') or ''
                                central_instance.publish_event('CHARGING_INTERRUPTED', {
                                    'cp_id': cp_id,
                                    'session_id': session_id_it,
                                    'username': username_it,
                                    'partial_energy_kwh': energia_it,
                                    'reason': 'engine_failure_offline_transition',
                                    'message': 'Engine caído pero monitor vivo. Sesión en pausa (fault) esperando recuperación.'
                                })
                                shared_state.interrupted_notified_sessions.add(session_id_it)
                                print(f"[CENTRAL] charging→offline convertido a fault (interrupción) CP {cp_id} sesión {session_id_it}")
                        return
                    except Exception as e:
                        print(f"[CENTRAL] Error aplicando interrupción charging→offline en {cp_id}: {e}")
            if status == 'offline' and current_status == 'charging':
                # NUEVO: No cerrar ni ticketear; marcar fault + interrupción + evento de error
                # Solo aplica si el Monitor está vivo (si no, respetar 'offline')
                try:
                    last_hb_nc = shared_state.last_monitor_seen.get(cp_id, 0)
                    hb_grace_nc = max(shared_state.monitor_timeout_seconds * 3.0, 15.0)
                    monitor_alive_nc = last_hb_nc > 0 and (time.time() - last_hb_nc) <= hb_grace_nc
                    if not monitor_alive_nc:
                        # Monitor caído → mantener 'offline'
                        print(f"[CENTRAL] DIAG: charging→offline sin correlación y monitor NO vivo → tratar como caída de monitor (offline pegajoso) cp={cp_id}")
                        # Continuar a sincronización normal sin convertir a fault
                    else:
                        print(f"[CENTRAL] DIAG: charging→offline sin correlación con monitor vivo → reclasificar a fault (averiado) cp={cp_id}")
                        # Marcar estado 'fault' si no lo está
                        if current_status != 'fault':
                            db.update_charging_point_status(cp_id, 'fault')
                            central_instance.publish_cp_info_to_monitor(cp_id, force=True)
                        # Recuperar sesión activa
                        conn_t = db.get_connection()
                        cur_t = conn_t.cursor()
                        cur_t.execute("""
                            SELECT s.id, s.user_id, s.energia_kwh, s.start_time, u.nombre as username
                            FROM charging_sesiones s
                            JOIN usuarios u ON s.user_id = u.id
                            WHERE s.cp_id = ? AND s.estado = 'active'
                            ORDER BY s.start_time DESC
                            LIMIT 1
                        """, (cp_id,))
                        active_row = cur_t.fetchone()
                        conn_t.close()
                        if active_row:
                            session_id_t = active_row['id']
                            energia_t = (active_row['energia_kwh'] or 0.0)
                            username_t = active_row.get('username') or ''
                            # Notificar interrupción si no se notificó
                            if session_id_t not in shared_state.interrupted_notified_sessions:
                                central_instance.publish_event('CHARGING_INTERRUPTED', {
                                    'cp_id': cp_id,
                                    'session_id': session_id_t,
                                    'username': username_t,
                                    'partial_energy_kwh': energia_t,
                                    'reason': 'engine_unreachable_no_correlation',
                                    'message': 'El Engine del CP no responde. Sesión pausada (averiado) sin ticket final.'
                                })
                                shared_state.interrupted_notified_sessions.add(session_id_t)
                            # Evento explícito de error de Engine inaccesible
                            central_instance.publish_event('CP_ENGINE_ERROR', {
                                'cp_id': cp_id,
                                'session_id': session_id_t,
                                'username': username_t,
                                'partial_energy_kwh': energia_t,
                                'message': 'El CP no puede conectar con su Engine. Estado marcado como averiado.'
                            })
                            print(f"[CENTRAL] charging→offline sin correlación convertido a fault + interrupción CP {cp_id} sesión {session_id_t}")
                        return  # Importante: no continuar al flujo estándar (sin ticket)
                except Exception as e:
                    print(f"[CENTRAL] Error manejando charging→offline sin correlación en {cp_id}: {e}")
            
            # -----------------------------------------------------------------
            # FALLBACK OFFLINE→FAULT: Si llega un cp_status_change a 'offline' y
            # hay sesión activa o progreso reciente pero no se aplicó la lógica
            # anterior (retorno temprano), forzar estado 'fault'. Evita quedar
            # simplemente 'offline' tras caída del Engine sin correlación clara.
            # -----------------------------------------------------------------
            if status == 'offline':
                try:
                    final_state_before_fb = db.get_charging_point_status(cp_id)
                    if final_state_before_fb != 'fault':
                        # Solo aplicar fallback si el Monitor está vivo
                        last_hb_fb2 = shared_state.last_monitor_seen.get(cp_id, 0)
                        hb_grace_fb2 = max(shared_state.monitor_timeout_seconds * 3.0, 15.0)
                        monitor_alive_fb2 = last_hb_fb2 > 0 and (time.time() - last_hb_fb2) <= hb_grace_fb2
                        if not monitor_alive_fb2:
                            # Monitor caído/ausente → mantener 'offline'
                            print(f"[CENTRAL] DIAG: FALLBACK offline→fault omitido (monitor NO vivo) cp={cp_id}")
                            raise SystemExit  # salir del try interno sin aplicar fallback
                        # ¿Sesión activa?
                        active_fb = []
                        if hasattr(db, 'get_active_sessions_for_cp'):
                            active_fb = db.get_active_sessions_for_cp(cp_id) or []
                        if not active_fb and hasattr(db, 'get_all_sessions'):
                            all_fb = db.get_all_sessions()
                            active_fb = [s for s in all_fb if s.get('cp_id') == cp_id and s.get('estado') == 'active']
                        # ¿Progreso reciente?
                        last_prog_fb = getattr(shared_state, 'last_progress_per_cp', {}).get(cp_id, 0)
                        prog_age_fb = time.time() - last_prog_fb if last_prog_fb else 9999
                        progress_recent_fb = prog_age_fb < (getattr(shared_state, 'engine_inactivity_threshold', 20.0) * 2.0)
                        if active_fb or progress_recent_fb:
                            db.update_charging_point_status(cp_id, 'fault')
                            central_instance.publish_cp_info_to_monitor(cp_id, force=True)
                            print(f"[CENTRAL] DIAG: FALLBACK aplicado offline→fault cp={cp_id} prog_age={prog_age_fb:.1f}s sesiones={len(active_fb)} monitor_alive=True")
                            if active_fb:
                                sess_fb = active_fb[0]
                                sess_id_fb = sess_fb.get('id')
                                energia_fb = sess_fb.get('energia_kwh') or 0.0
                                user_id_fb = sess_fb.get('user_id')
                                user_fb = db.get_user_by_id(user_id_fb) if hasattr(db, 'get_user_by_id') else None
                                username_fb = user_fb.get('username') if user_fb else ''
                                if sess_id_fb not in getattr(shared_state, 'interrupted_notified_sessions', set()):
                                    central_instance.publish_event('CHARGING_INTERRUPTED', {
                                        'cp_id': cp_id,
                                        'session_id': sess_id_fb,
                                        'username': username_fb,
                                        'user_id': user_id_fb,
                                        'partial_energy_kwh': energia_fb,
                                        'reason': 'offline_fallback_fault',
                                        'message': 'Estado offline forzado a averiado para mantener sesión en pausa.'
                                    })
                                    try:
                                        shared_state.interrupted_notified_sessions.add(sess_id_fb)
                                    except Exception:
                                        pass
                                central_instance.publish_event('CP_ENGINE_ERROR', {
                                    'cp_id': cp_id,
                                    'session_id': sess_id_fb,
                                    'username': username_fb,
                                    'partial_energy_kwh': energia_fb,
                                    'message': 'Transición a offline sin correlación; marcado como averiado.'
                                })
                except SystemExit:
                    pass
                except Exception as e:
                    print(f"[CENTRAL] Error en fallback offline→fault para {cp_id}: {e}")

            # Solo si el estado cambió realmente, actualizar BD
            # PROTECCIÓN: Cuando un CP está 'offline' (p.ej., por kill/timeout del Monitor),
            # ignorar cualquier intento de cambio de estado que no sea 'offline'.
            # Esto hace que el estado 'offline' sea pegajoso (sticky) hasta que un flujo explícito lo cambie.
            if current_status == 'offline' and status != 'offline':
                print(f"[CENTRAL] Ignorando cp_status_change a '{status}' para CP {cp_id} - permanece 'offline' (monitor caído/timeout)")
                return
            
            print(f"[CENTRAL] Sincronizando estado BD: {cp_id} → {current_status} → {status} (cambio reportado por Engine)")
            db.update_charging_point_status(cp_id, status)
            
            # IMPORTANTE: Publicar CP_INFO al Monitor SOLO una vez después de actualizar BD
            # Esto informa al Monitor del cambio de estado sin causar bucles
            central_instance.publish_cp_info_to_monitor(cp_id)
        elif action in ['cp_error_simulated', 'cp_error_fixed']:
            new_status = event.get('new_status') or event.get('status')
            if new_status:
                db.update_charging_point_status(cp_id, new_status)
                #  PUBLICAR CAMBIO DE ESTADO AL MONITOR
                central_instance.publish_cp_info_to_monitor(cp_id)
        
        # ========================================================================
        # FALLOS DEL ENGINE REPORTADOS POR EL MONITOR
        # ========================================================================
        # Cuando el Monitor detecta que el Engine no responde (3+ timeouts),
        # notifica a Central para que cancele sesiones activas y libere el CP
    elif event_type in ['ENGINE_FAILURE'] or action in ['report_engine_failure']:
            # Nuevo flujo: Engine cae pero Monitor sigue vivo y reporta fallo.
            failure_type = event.get('failure_type', 'unknown')
            consecutive_failures = event.get('consecutive_failures', 0)
            print(f"[CENTRAL] ENGINE_FAILURE recibido: cp={cp_id}, type={failure_type}, failures={consecutive_failures}")
            # Registrar timestamp para correlación de charging→offline (una sola vez)
            try:
                shared_state.engine_failure_seen_at[cp_id] = time.time()
            except Exception:
                pass
            # Marcar CP como 'fault' (Averiado) si no lo estaba
            try:
                cp_row = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
                prev_state = (cp_row.get('estado') or cp_row.get('status')) if cp_row else None
                if prev_state != 'fault':
                    db.update_charging_point_status(cp_id, 'fault')
                    central_instance.publish_cp_info_to_monitor(cp_id)
                    print(f"[CENTRAL] CP {cp_id} marcado como 'fault' (averiado)")
            except Exception as e:
                print(f"[CENTRAL] Error marcando CP fault: {e}")
            # Notificar interrupción al Driver si había sesión activa pero NO cerrarla aún (permitir datos finales posteriores)
            try:
                active_sessions = db.get_active_sessions_for_cp(cp_id) if hasattr(db, 'get_active_sessions_for_cp') else []
                if not active_sessions:
                    all_sessions = db.get_all_sessions() if hasattr(db, 'get_all_sessions') else []
                    active_sessions = [s for s in all_sessions if s.get('cp_id') == cp_id and s.get('estado') == 'active']
                for session in active_sessions:
                    session_id = session.get('id')
                    user_id = session.get('user_id')
                    energia_parcial = session.get('energia_kwh') or 0.0
                    user = db.get_user_by_id(user_id) if hasattr(db, 'get_user_by_id') else None
                    username = user.get('username') if user else ''
                    # Evento informativo al driver
                    central_instance.publish_event('CHARGING_INTERRUPTED', {
                        'cp_id': cp_id,
                        'session_id': session_id,
                        'username': username,
                        'user_id': user_id,
                        'partial_energy_kwh': energia_parcial,
                        'reason': f'Engine fallo ({failure_type})',
                        'message': f'La carga en {cp_id} se interrumpió. Esperando recuperación para datos finales.'
                    })
                    # Evento explícito de error del Engine
                    central_instance.publish_event('CP_ENGINE_ERROR', {
                        'cp_id': cp_id,
                        'session_id': session_id,
                        'username': username,
                        'partial_energy_kwh': energia_parcial,
                        'message': f'Engine falló ({failure_type}). Sesión sigue abierta sin ticket.'
                    })
                    print(f"[CENTRAL] Sesión {session_id} marcada como interrumpida (no cerrada) - energía parcial {energia_parcial:.2f} kWh")
            except Exception as e:
                print(f"[CENTRAL] Error notificando interrupción de sesión en ENGINE_FAILURE: {e}")
    elif event_type in ['ENGINE_OFFLINE'] or action in ['report_engine_offline']:
            # Nuevo criterio: si el Monitor está vivo pero reporta ENGINE_OFFLINE,
            # tratamos como interrupción: marcar 'fault', NO cerrar sesión, notificar al Driver.
            print(f"[CENTRAL] ENGINE_OFFLINE recibido para {cp_id} → tratar como 'fault' e interrupción (sin cierre)")
            try:
                try:
                    shared_state.engine_failure_seen_at[cp_id] = time.time()
                except Exception:
                    pass
                db.update_charging_point_status(cp_id, 'fault')
                central_instance.publish_cp_info_to_monitor(cp_id)
            except Exception as e:
                print(f"[CENTRAL] Error marcando CP fault tras ENGINE_OFFLINE: {e}")
            # Notificar interrupción si hay sesión activa (sin cerrarla)
            try:
                active_sessions = db.get_active_sessions_for_cp(cp_id) if hasattr(db, 'get_active_sessions_for_cp') else []
                if not active_sessions and hasattr(db, 'get_all_sessions'):
                    all_sessions = db.get_all_sessions()
                    active_sessions = [s for s in all_sessions if s.get('cp_id') == cp_id and s.get('estado') == 'active']
                for session in active_sessions:
                    session_id = session.get('id')
                    if session_id in getattr(shared_state, 'interrupted_notified_sessions', set()):
                        continue
                    user_id = session.get('user_id')
                    energia_parcial = session.get('energia_kwh') or 0.0
                    user = db.get_user_by_id(user_id) if hasattr(db, 'get_user_by_id') else None
                    username = user.get('username') if user else ''
                    central_instance.publish_event('CHARGING_INTERRUPTED', {
                        'cp_id': cp_id,
                        'session_id': session_id,
                        'username': username,
                        'user_id': user_id,
                        'partial_energy_kwh': energia_parcial,
                        'reason': 'engine_offline_reported',
                        'message': 'Engine reportado offline por el Monitor. Sesión interrumpida a la espera de recuperación.'
                    })
                    try:
                        shared_state.interrupted_notified_sessions.add(session_id)
                    except Exception:
                        pass
                    central_instance.publish_event('CP_ENGINE_ERROR', {
                        'cp_id': cp_id,
                        'session_id': session_id,
                        'username': username,
                        'partial_energy_kwh': energia_parcial,
                        'message': 'Engine offline reportado. Sesión sigue abierta sin ticket.'
                    })
                    print(f"[CENTRAL] Sesión {session_id} interrumpida (ENGINE_OFFLINE reportado) en {cp_id}")
            except Exception as e:
                print(f"[CENTRAL] Error notificando interrupción tras ENGINE_OFFLINE: {e}")
    elif event_type in ['ENGINE_RECOVERED'] or action in ['report_engine_recovered']:
            # Engine se recupera y envía métricas finales
            recovered_cp = event.get('cp_id')
            final_energy = event.get('final_energy_kwh', 0.0)
            final_cost = event.get('final_cost', 0.0)
            final_duration = event.get('final_duration_sec', 0)
            print(f"[CENTRAL] ENGINE_RECOVERED recibido: cp={recovered_cp}, energía final={final_energy:.2f} kWh")
            try:
                # Restaurar estado del CP (solo si estaba fault u offline)
                current_state = db.get_charging_point_status(recovered_cp)
                if current_state in ['fault', 'offline']:
                    db.update_charging_point_status(recovered_cp, 'available')
                    central_instance.publish_cp_info_to_monitor(recovered_cp)
                # Finalizar sesión activa si quedó interrumpida
                active_sessions = db.get_active_sessions_for_cp(recovered_cp) if hasattr(db, 'get_active_sessions_for_cp') else []
                if not active_sessions:
                    all_sessions = db.get_all_sessions() if hasattr(db, 'get_all_sessions') else []
                    active_sessions = [s for s in all_sessions if s.get('cp_id') == recovered_cp and s.get('estado') == 'active']
                for session in active_sessions:
                    session_id = session.get('id')
                    user_id = session.get('user_id')
                    user = db.get_user_by_id(user_id) if hasattr(db, 'get_user_by_id') else None
                    username = user.get('username') if user else ''
                    result = db.end_charging_sesion(session_id, final_energy, cp_status_after='available')
                    ticket_cost = result.get('coste', final_cost) if result else final_cost
                    central_instance.publish_event('CHARGING_TICKET', {
                        'username': username,
                        'cp_id': recovered_cp,
                        'energy_kwh': final_energy,
                        'cost': ticket_cost,
                        'duration_sec': final_duration,
                        'reason': 'engine_recovered',
                        'message': 'Sesión finalizada tras recuperación del Engine'
                    })
                    print(f"[CENTRAL] Sesión {session_id} finalizada tras recuperación de Engine en {recovered_cp}")
            except Exception as e:
                print(f"[CENTRAL] Error procesando ENGINE_RECOVERED para {recovered_cp}: {e}")
        
        # ========================================================================
        # AUTENTICACIÓN DEL MONITOR
        # ========================================================================
        # Al arrancar, el Monitor se conecta a Central para autenticarse
        # y validar que está operativo y preparado para prestar servicios
    elif event_type == 'MONITOR_AUTH' or action == 'authenticate':
            monitor_id = event.get('monitor_id', f'MONITOR-{cp_id}')
            monitor_status = event.get('status', 'UNKNOWN')
            engine_host = event.get('engine_host', 'unknown')
            engine_port = event.get('engine_port', 0)
            
            print(f"[CENTRAL] Monitor authentication received")
            print(f"[CENTRAL]    Monitor:      {monitor_id}")
            print(f"[CENTRAL]    CP:           {cp_id}")
            print(f"[CENTRAL]    Status:       {monitor_status}")
            print(f"[CENTRAL]    Engine:       {engine_host}:{engine_port}")
            
            # Validar que el CP existe en la BD
            try:
                cp = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
                if cp:
                    print(f"[CENTRAL] Monitor {monitor_id} authenticated and validated")
                    print(f"[CENTRAL] Monitor is ready to supervise {cp_id}")
                    
                    # Opcional: Publicar confirmación de autenticación
                    central_instance.publish_event('MONITOR_AUTH_RESPONSE', {
                        'cp_id': cp_id,
                        'monitor_id': monitor_id,
                        'status': 'AUTHENTICATED',
                        'message': f'Monitor {monitor_id} authenticated successfully'
                    })
                else:
                    print(f"[CENTRAL]  Monitor {monitor_id} authentication failed: CP {cp_id} not found")
            except Exception as e:
                print(f"[CENTRAL] Error authenticating monitor {monitor_id}: {e}")
        
        # ========================================================================
        # NOTA: ENGINE_FAILURE y ENGINE_OFFLINE ya se procesan arriba (línea ~1839)
        # Esta sección duplicada fue eliminada para evitar procesamiento doble
        # ========================================================================

    # ========================================================================
    # BROADCAST A CLIENTES WEBSOCKET (solo si hay clientes conectados)
    # ========================================================================
    # El procesamiento de eventos ya se hizo arriba (actualizaciones de BD, etc.)
    # Ahora solo necesitamos notificar a los clientes WebSocket si están conectados
    # ========================================================================
    if not shared_state.connected_clients:
        print(f"[KAFKA]  No clients connected, skipping broadcast (events already processed)")
        return

    # Crear mensaje según el tipo de acción
    if action == 'charging_started':
        message = json.dumps({
            'type': 'session_started',
            'username': event.get('username'),
            'cp_id': event.get('cp_id')
        })
        # Inicializar timestamp de progreso para inactividad (marca comienzo)
        cp_start_id = event.get('cp_id')
        if cp_start_id:
            shared_state.last_progress_per_cp[cp_start_id] = time.time()
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
            'message': f"Error simulado en {event.get('cp_id')}: {event.get('error_type')}"
        })
    elif action == 'cp_error_fixed':
        message = json.dumps({
            'type': 'cp_fixed',
            'cp_id': event.get('cp_id'),
            'status': event.get('new_status'),
            'message': f"{event.get('cp_id')} reparado y disponible"
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
        print(f"[KAFKA] Broadcasting generic event: {event_desc}")
    
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

async def broadcast_system_message(text: str):
    """Envía un mensaje simple al stream de eventos del dashboard (tipo system_event)."""
    if not shared_state.connected_clients:
        return
    message = json.dumps({
        'type': 'system_event',
        'message': text
    })
    disconnected_clients = set()
    for client in shared_state.connected_clients:
        try:
            if hasattr(client, 'send_str'):
                await client.send_str(message)
            else:
                await client.send(message)
        except:
            disconnected_clients.add(client)
    for client in disconnected_clients:
        shared_state.connected_clients.discard(client)

async def main():
    """Función principal que inicia todos los servicios"""
    local_ip = get_local_ip()
    
    print("\n" + "=" * 80)
    print(" " * 22 + "EV CENTRAL - Admin WebSocket Server")
    print("=" * 80)
    print(f"  Local Access:     http://localhost:{SERVER_PORT}")
    print(f"  Network Access:   http://{local_ip}:{SERVER_PORT}")
    print(f"  WebSocket:        ws://{local_ip}:{SERVER_PORT}/ws")
    print(f"  Database:         ev_charging.db")
    print(f"   Kafka Broker:     {KAFKA_BROKER}")
    print(f"  Consuming:        {', '.join(KAFKA_TOPICS_CONSUME)}")
    print(f"  Publishing:       {KAFKA_TOPIC_PRODUCE}")
    print("=" * 80)
    print(f"\n   Access from other PCs: http://{local_ip}:{SERVER_PORT}")
    print(f"   Make sure firewall allows port {SERVER_PORT}")
    print("=" * 80 + "\n")
    
    if not WS_AVAILABLE:
        print("ERROR: WebSocket dependencies not installed")
        print("Run: pip install websockets aiohttp")
        return
    
    # Verificar base de datos
    # En Docker, la BD está en /app/ev_charging.db; en local puede estar en el directorio actual
    db_path = Path('/app/ev_charging.db')
    if not db_path.exists():
        db_path = Path('ev_charging.db')

    if not db_path.exists():
        print(" Database not found. Please run: python init_db.py")
        return

    # Requisito: al iniciar Central TODO debe estar apagado
    try:
        # Actualizar timestamp de inicio para filtrar eventos antiguos
        shared_state.central_start_time = time.time()
        print(f"[CENTRAL] Timestamp de inicio de Central: {shared_state.central_start_time}")
        
        # 1) Terminar cualquier sesión activa que haya quedado de ejecuciones anteriores
        if hasattr(db, 'terminate_all_active_sessions'):
            sess, cps = db.terminate_all_active_sessions(mark_cp_offline=False)
            print(f"[CENTRAL] Inicio: sesiones activas terminadas: {sess}")
        
        # 2) Política de disponibilidad: solo CP_001..CP_004 pueden estar 'available'
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            allowed = ('CP_001','CP_002','CP_003','CP_004')
            # Poner en available los permitidos SIEMPRE
            cursor.execute("UPDATE charging_points SET estado='available' WHERE cp_id IN ('CP_001','CP_002','CP_003','CP_004')")
            allowed_changed = cursor.rowcount
            # Forzar offline TODOS los otros CPs (cualquiera sea su estado previo)
            cursor.execute("UPDATE charging_points SET estado='offline' WHERE cp_id NOT IN ('CP_001','CP_002','CP_003','CP_004')")
            others_forced_offline = cursor.rowcount
            conn.commit()
            conn.close()
            if allowed_changed > 0:
                print(f"[CENTRAL] CP permitidos activados: {allowed_changed} marcados 'available' (solo 1..4)")
            if others_forced_offline > 0:
                print(f"[CENTRAL] Política aplicada: {others_forced_offline} CP(s) fuera de 1..4 forzados a 'offline'")
        except Exception as e:
            print(f"[CENTRAL] Error aplicando política de disponibilidad 1..4: {e}")
    except Exception as e:
        print(f"[CENTRAL] No se pudo limpiar estado al inicio: {e}")
    
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
        print(f"[WS] 🔌 WebSocket endpoint at ws://0.0.0.0:{SERVER_PORT}/ws")
        
        # Iniciar broadcast de actualizaciones
        broadcast_task = asyncio.create_task(broadcast_updates())
        
        # Iniciar listener de Kafka
        kafka_task = asyncio.create_task(kafka_listener())
        
        # Iniciar monitor de timeouts de Monitores
        timeout_task = asyncio.create_task(monitor_timeout_checker())
        # Iniciar checker de inactividad del Engine
        engine_inact_task = asyncio.create_task(engine_inactivity_checker())
        
        print("\nAll services started successfully!")
        print(f"Open http://localhost:{SERVER_PORT} in your browser\n")
        
        # Mantener el servidor corriendo
        await asyncio.gather(broadcast_task, kafka_task, timeout_task, engine_inact_task)
        
    except Exception as e:
        print(f"\nError starting server: {e}")

if __name__ == "__main__":
    # ========================================================================
    # ARGUMENTOS DE LÍNEA DE COMANDOS
    # ========================================================================
    parser = argparse.ArgumentParser(
        description='EV Central - Sistema Central de Gestión de Puntos de Recarga'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.environ.get('CENTRAL_PORT', CENTRAL_CONFIG['ws_port'])),
        help=f'Puerto del servidor WebSocket (default: {CENTRAL_CONFIG["ws_port"]} o env CENTRAL_PORT)'
    )
    parser.add_argument(
        '--kafka-broker',
        default=os.environ.get('KAFKA_BROKER', KAFKA_BROKER_DEFAULT),
        help='Kafka broker address (default: from env KAFKA_BROKER or config)'
    )
    
    args = parser.parse_args()
    
    # Actualizar configuración global (no necesita 'global' en el scope del módulo)
    SERVER_PORT = args.port
    KAFKA_BROKER = args.kafka_broker
    
    print(f"""
================================================================================
  EV CENTRAL - Sistema Central de Gestión
================================================================================
  WebSocket Port:  {SERVER_PORT}
  Kafka Broker:    {KAFKA_BROKER}
  Dashboard:       http://localhost:{SERVER_PORT}
================================================================================
""")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Al apagar CENTRAL, terminar todas las sesiones activas y marcar CPs offline
        try:
            if hasattr(db, 'terminate_all_active_sessions'):
                sess, cps = db.terminate_all_active_sessions(mark_cp_offline=True)
                print(f"\n[CENTRAL] 🔌 Shutdown cleanup -> sessions terminated: {sess}, CPs set offline: {cps}")
        except Exception as e:
            print(f"\n[CENTRAL] Shutdown cleanup error: {e}")
        print("\n[CENTRAL] Server stopped by user")
    except Exception as e:
        print(f"\nFatal error: {e}")
