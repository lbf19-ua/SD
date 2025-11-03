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
        self.central_start_time = time.time() 
        self.processed_event_ids = set()  
        self.processed_lock = threading.Lock() 

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
        for attempt in range(max_retries):
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=self.kafka_broker,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
                print(f"[CENTRAL] Kafka producer initialized")
                return
            except Exception as e:
                print(f"[CENTRAL] Attempt {attempt+1}/{max_retries} - Kafka not available: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    print(f"[CENTRAL] Failed to connect to Kafka after {max_retries} attempts")
    
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
                            print(f"[CENTRAL] Fixed: Added cp_id={cp_id_nested} from nested data")
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
                cp_id_log = event.get('cp_id', 'UNKNOWN')
                print(f"[CENTRAL] CP_INFO publicado a {KAFKA_TOPIC_PRODUCE} - cp_id={cp_id_log}")
            else:
                print(f"[CENTRAL] Evento {event_type} publicado a {KAFKA_TOPIC_PRODUCE}")
        except Exception as e:
            print(f"[CENTRAL] Error publicando evento {event_type}: {e}")
            import traceback
            traceback.print_exc()

    def publish_cp_info_to_monitor(self, cp_id, force=False):
        if not hasattr(self, '_last_cp_info_publish'):
            self._last_cp_info_publish = {}
        
        if not force:
            current_time = time.time()
            last_publish = self._last_cp_info_publish.get(cp_id, 0)
            time_since_last = current_time - last_publish
            # Mínimo 3 segundos entre publicaciones del mismo CP
            if time_since_last < 3.0:  
                print(f"[CENTRAL]  Throttling: CP_INFO para {cp_id} ya se publicó hace {time_since_last:.2f}s, omitiendo para evitar bucle")
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
            if not location or location.strip() == '':
                # Si no hay location en BD, intentar obtenerla de los datos originales
                location = cp_row.get('localizacion') or cp_row.get('location') or 'Unknown'
                if location.strip() == '':
                    location = 'Unknown'
            
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
            print(f"[CENTRAL] CP_INFO enviado al Monitor - CP: {cp_id}, Location: {location}, Status: {status}, Max Power: {max_power} kW, Tariff: €{tariff}/kWh")
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
        if not location or location.strip() == '':
            location = ''
        
        # Extraer estado y normalizarlo
        # La BD usa 'estado' (español), convertir a 'status' (inglés)
        raw_status = cp_row.get('estado') or cp_row.get('status') or 'offline'
        status = self._normalize_status(raw_status)
        
        # Extraer potencia máxima
        # La BD usa 'max_kw', convertir a 'max_power_kw'
        max_power = cp_row.get('max_kw') or cp_row.get('max_power_kw')
        if not max_power:
            max_power = 22.0
        
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
                
                # Mapear usuarios con su estado de sesión activa
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
                print(f"[CENTRAL] Published event: {event_type} to central-events: {data}")
            except Exception as e:
                print(f"[CENTRAL] Failed to publish event: {e}")

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
    print(f"[WS] New admin client connected. Total clients: {len(shared_state.connected_clients)}")
    
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
                        
                        # PUBLICAR INFORMACIÓN DEL CP AL MONITOR
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
                        
                        # Cambiar estado a available
                        db.update_charging_point_status(cp_id, 'available')
                        
                        # PUBLICAR EVENTO EN KAFKA para notificar al Driver
                        central_instance.publish_event('CP_ERROR_FIXED', {
                            'cp_id': cp_id,
                            'new_status': 'available',
                            'message': f'Error corregido en {cp_id}'
                        })
                        print(f"[CENTRAL] Publicado CP_ERROR_FIXED en Kafka para {cp_id}")
                        
                        # PUBLICAR INFORMACIÓN DEL CP AL MONITOR
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
                                    
                                    # PUBLICAR INFORMACIÓN DEL CP AL MONITOR
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
                                print(f"[CENTRAL]  Error terminando sesión en {cp_id}: {e}")
                            
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
                            
                            # PUBLICAR INFORMACIÓN DEL CP AL MONITOR
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
                            print(f"[CENTRAL]  Reanudando TODOS los CPs...")
                            all_cps = db.get_all_charging_points() if hasattr(db, 'get_all_charging_points') else []
                            
                            for cp in all_cps:
                                cp_id_item = cp.get('cp_id') or cp.get('id')
                                if cp_id_item:
                                    # Cambiar a available
                                    db.update_charging_point_status(cp_id_item, 'available')
                                    
                                    # Publicar comando vía Kafka al CP_E
                                    central_instance.publish_event('CP_RESUME', {
                                        'cp_id': cp_id_item,
                                        'action': 'resume',
                                        'new_status': 'available',
                                        'reason': 'Resumed by admin'
                                    })
                                    
                                    # PUBLICAR INFORMACIÓN DEL CP AL MONITOR
                                    central_instance.publish_cp_info_to_monitor(cp_id_item)
                            
                            await ws.send_str(json.dumps({
                                'type': 'resume_cp_success',
                                'message': f'Todos los CPs reanudados'
                            }))
                        elif cp_id:
                            # Reanudar CP específico
                            print(f"[CENTRAL]  Reanudando CP {cp_id}...")
                            
                            # Cambiar estado a available
                            db.update_charging_point_status(cp_id, 'available')
                            
                            # Publicar comando vía Kafka al CP_E
                            central_instance.publish_event('CP_RESUME', {
                                'cp_id': cp_id,
                                'action': 'resume',
                                'new_status': 'available',
                                'reason': 'Resumed by admin'
                            })
                            print(f"[CENTRAL] Publicado CP_RESUME en Kafka para {cp_id}")
                            
                            # PUBLICAR INFORMACIÓN DEL CP AL MONITOR
                            central_instance.publish_cp_info_to_monitor(cp_id)
                            
                            await ws.send_str(json.dumps({
                                'type': 'resume_cp_success',
                                'message': f'CP {cp_id} reanudado'
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
                                
                                # PUBLICAR INFORMACIÓN DEL CP AL MONITOR
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
                    print(f"[WS]   Invalid JSON from {client_id}")
            elif msg.type == web.WSMsgType.ERROR:
                print(f"[WS]   WebSocket error: {ws.exception()}")
                
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
        max_retries = 15
        retry_count = 0
        consumer = None
        
        while retry_count < max_retries:
            try:
                print(f"[KAFKA] Attempt {retry_count + 1}/{max_retries} to connect to Kafka at {KAFKA_BROKER}")
                
                #  CRÍTICO: Usar group_id único en cada inicio para evitar leer mensajes antiguos
                # Esto asegura que Central solo procese mensajes nuevos después de conectarse
                unique_group_id = f'ev_central_ws_group_{int(time.time())}'
                print(f"[KAFKA] Using unique group_id: {unique_group_id} (ignores old messages)")
                
                consumer = KafkaConsumer(
                    *KAFKA_TOPICS_CONSUME,
                    bootstrap_servers=KAFKA_BROKER,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='latest',  #  CRÍTICO: Solo mensajes nuevos (después de conectarse)
                    group_id=unique_group_id,  #  CRÍTICO: Group ID único por inicio (no reutiliza offsets anteriores)
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
                print(f"[KAFKA]  Error connecting to Kafka: {offset_error}")
                import traceback
                traceback.print_exc()
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2)
                    continue
                else:
                    print(f"[KAFKA] Failed to connect after {max_retries} attempts")
                    return
            except Exception as e:
                retry_count += 1
                if consumer:
                    consumer.close()
                print(f"[KAFKA]  Attempt {retry_count}/{max_retries} failed: {e}")
                if retry_count < max_retries:
                    time.sleep(2)
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
                                
                                print(f"[KAFKA] Received event #{message_count}: {event_type} | CP: {cp_id} | msg_id: {message_id} | topic: {message.topic} | source: {source} | timestamp: {timestamp}")
                            except Exception as e:
                                print(f"[KAFKA]  Error deserializing message: {e}")
                                continue
                            
                            # Procesar el evento (solo imprimir tipo para evitar duplicación)
                            event_type = event.get('event_type', 'UNKNOWN')
                            # NO volver a imprimir aquí - ya se imprimió arriba
                            
                            #  IMPORTANTE: Todo el procesamiento de eventos se hace en broadcast_kafka_event()
                            # para evitar procesamiento duplicado. Este listener solo consume y pasa eventos.
                            
                            # ====================================================================
                            # MONITOR AUTH: Excepción - procesar aquí porque no debe pasar por broadcast
                            # ====================================================================
                            et = event.get('event_type', '')
                            if et == 'MONITOR_AUTH' or event.get('action', '') == 'authenticate':
                                cp_id = event.get('cp_id')
                                if cp_id:
                                    print(f"[CENTRAL] Monitor autenticado para CP {cp_id}")
                                    #  NO publicar CP_INFO aquí - se enviará cuando el Engine se registre
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
                                        print(f"[CENTRAL]  Error verificando CP {cp_id} para Monitor: {e}")
                            
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
                                            continue
                                        
                                        print(f"[CENTRAL] CP {cp_id} asignado y reservado automáticamente para {username}")
                                        
                                        # Ya está reservado, enviar respuesta positiva al Driver
                                        central_instance.publish_event('AUTHORIZATION_RESPONSE', {
                                            'client_id': client_id,
                                            'cp_id': cp_id, 
                                            'authorized': True
                                        })
                                        
                                        # Obtener user_id si no está en el evento
                                        user_id = event.get('user_id')
                                        if not user_id and username:
                                            try:
                                                user = db.get_user_by_username(username)
                                                if user:
                                                    user_id = user.get('id')
                                                    print(f"[CENTRAL] DEBUG: user_id encontrado para {username}: {user_id}")
                                            except Exception as e:
                                                print(f"[CENTRAL]  Error buscando user_id para {username}: {e}")
                                        
                                        # Crear sesión de carga directamente (no enviar evento a Kafka)
                                        if user_id and cp_id:
                                            try:
                                                correlation_id = event.get('correlation_id')
                                                session_id = db.create_charging_session(user_id, cp_id, correlation_id)
                                                if session_id:
                                                    print(f"[CENTRAL] Sesión {session_id} creada para usuario {username} en CP {cp_id}")
                                                else:
                                                    print(f"[CENTRAL]  Error: session_id es None")
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
                                            continue
                                            
                                        current_status = cp.get('status') or cp.get('estado')
                                        print(f"[CENTRAL] CP {cp_id} tiene estado: {current_status}")
                                        
                                        # Solo rechazar si está en estado 'fault', 'out_of_service', 'charging' o 'reserved'
                                        if current_status in ('fault', 'out_of_service', 'charging', 'reserved'):
                                            central_instance.publish_event('AUTHORIZATION_RESPONSE', {
                                                'client_id': client_id,
                                                'cp_id': cp_id,
                                                'authorized': False,
                                                'reason': f'CP no disponible (estado: {current_status})'
                                            })
                                            continue
                                        
                                        # Intentar reservar el punto de carga específico
                                        if db.reserve_charging_point(cp_id):
                                            print(f"[CENTRAL] CP {cp_id} reservado para cliente {client_id}")
                                            central_instance.publish_event('AUTHORIZATION_RESPONSE', {
                                                'client_id': client_id,
                                                'cp_id': cp_id, 
                                                'authorized': True
                                            })
                                            
                                            # Obtener user_id si no está en el evento
                                            user_id = event.get('user_id')
                                            if not user_id and username:
                                                try:
                                                    user = db.get_user_by_username(username)
                                                    if user:
                                                        user_id = user.get('id')
                                                except Exception as e:
                                                    print(f"[CENTRAL]  Error buscando user_id para {username}: {e}")
                                            
                                            # Crear sesión de carga directamente (no enviar evento a Kafka)
                                            if user_id and cp_id:
                                                try:
                                                    correlation_id = event.get('correlation_id')
                                                    session_id = db.create_charging_session(user_id, cp_id, correlation_id)
                                                    if session_id:
                                                        print(f"[CENTRAL] Sesión {session_id} creada para usuario {username} en CP {cp_id}")
                                                    else:
                                                        print(f"[CENTRAL]  Error: session_id es None")
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
                                except Exception as e:
                                    print(f"[CENTRAL]  Error procesando autorización: {e}")
                                    if client_id and cp_id:
                                        central_instance.publish_event('AUTHORIZATION_RESPONSE', {
                                            'client_id': client_id,
                                            'cp_id': cp_id,
                                            'authorized': False,
                                            'reason': f'Error interno: {str(e)}'
                                        })
                            
                            # Los eventos 'charging_started' son peticiones ya autorizadas por
                            # el Driver (que valida usuario, balance, disponibilidad).
                            # La Central actualiza el estado del CP y registra la sesión.
                            # --------------------------------------------------------------------
                            
                            #  IMPORTANTE: Pasar TODOS los eventos (excepto los procesados arriba) 
                            # a broadcast_kafka_event() para procesamiento unificado
                            # Esto evita procesamiento duplicado de CP_REGISTRATION y cp_status_change
                            if et not in ['MONITOR_AUTH', 'AUTHORIZATION_REQUEST']:
                                try:
                                    asyncio.run_coroutine_threadsafe(
                                        broadcast_kafka_event(event),
                                        loop
                                    )
                                except Exception as e:
                                    print(f"[CENTRAL]  Error scheduling broadcast: {e}")
                            
                except Exception as poll_error:
                    # Errores de polling no deberían detener el bucle
                    print(f"[KAFKA]  Error during poll: {poll_error}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(1)  # Esperar un poco antes de reintentar
                    continue
                
        except Exception as e:
            print(f"[KAFKA]   Consumer error during loop: {e}")
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
    #  IMPORTANTE: Ignorar eventos originados por Central mismo para evitar loops infinitos
    if event.get('source') == 'CENTRAL':
        return  # Central no debe procesar sus propios eventos
    
    #  FILTRO: Ignorar eventos que Central genera y que no debe procesar
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
        'CHARGING_TIMEOUT',          # Eventos internos que no necesitan procesamiento adicional
        'CHARGING_INTERRUPTED'       # Eventos que Central genera
    ]
    
    if event_type in events_to_ignore or action in events_to_ignore:
        print(f"[CENTRAL]  Ignorando evento {event_type or action} - es un evento que Central genera o ya procesó")
        return
    
    #  DEDUPLICACIÓN: Ignorar eventos ya procesados por message_id
    message_id = event.get('message_id')
    if message_id:
        with shared_state.processed_lock:
            if message_id in shared_state.processed_event_ids:
                print(f"[CENTRAL]  Evento ya procesado (message_id={message_id[:8]}...), ignorando: {event.get('event_type', 'UNKNOWN')}")
                return
            # Marcar como procesado ANTES de procesarlo (para evitar procesamiento paralelo)
            shared_state.processed_event_ids.add(message_id)
            # Limpiar IDs antiguos para evitar memoria infinita (mantener últimos 1000)
            if len(shared_state.processed_event_ids) > 1000:
                # Mantener solo los últimos 500 (limpiar los más antiguos)
                shared_state.processed_event_ids = set(list(shared_state.processed_event_ids)[-500:])
    
    #  IMPORTANTE: Calcular current_time una vez para usar en todas las verificaciones
    import time
    current_time = time.time()
    
    #  DEDUPLICACIÓN ADICIONAL: Evitar procesar el mismo tipo de evento para el mismo CP en muy poco tiempo
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
            print(f"[CENTRAL]  Evento {event_type or action} para CP {cp_id} procesado hace {current_time - last_event_time:.2f}s, ignorando duplicado")
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
    
    #  PROTECCIÓN: Ignorar eventos muy antiguos que pueden ser de antes del reinicio
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
                print(f"[CENTRAL]  Ignorando evento antiguo ({age_seconds:.0f}s de antigüedad, probablemente de antes del reinicio): {event.get('event_type', 'UNKNOWN')}")
                # Quitar del set si ya lo añadimos
                if message_id:
                    with shared_state.processed_lock:
                        shared_state.processed_event_ids.discard(message_id)
                return
            
            # Si Central acaba de iniciar (menos de 30 segundos), ignorar eventos que sean más antiguos que el inicio
            if time_since_start < 30:
                # El evento debe ser más reciente que el inicio de Central
                if event_time < central_start_time:
                    print(f"[CENTRAL]  Ignorando evento anterior al reinicio (Central inició hace {time_since_start:.1f}s): {event.get('event_type', 'UNKNOWN')}")
                    # Quitar del set si ya lo añadimos
                    if message_id:
                        with shared_state.processed_lock:
                            shared_state.processed_event_ids.discard(message_id)
                    return
        except (ValueError, TypeError):
            # Si el timestamp no es válido, verificar si Central acaba de iniciar
            if time_since_start < 30:
                # Si Central acaba de iniciar y el evento no tiene timestamp válido, es probablemente antiguo
                print(f"[CENTRAL]  Ignorando evento sin timestamp válido (Central inició hace {time_since_start:.1f}s): {event.get('event_type', 'UNKNOWN')}")
                # Quitar del set si ya lo añadimos
                if message_id:
                    with shared_state.processed_lock:
                        shared_state.processed_event_ids.discard(message_id)
                return
    else:
        # Si el evento no tiene timestamp, y Central acaba de iniciar, ignorarlo
        if time_since_start < 30:
            print(f"[CENTRAL]  Ignorando evento sin timestamp (Central inició hace {time_since_start:.1f}s): {event.get('event_type', 'UNKNOWN')}")
            # Quitar del set si ya lo añadimos
            if message_id:
                with shared_state.processed_lock:
                    shared_state.processed_event_ids.discard(message_id)
            return
    
    #  PROTECCIÓN ADICIONAL: Evitar procesar CP_REGISTRATION repetidamente
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
            print(f"[CENTRAL]  CP {cp_id} ya se registró recientemente ({current_time - recent_reg_time:.1f}s), ignorando registro duplicado")
            return
        
        # Verificar también en BD si ya está registrado como 'available'
        try:
            cp_existing = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
            if cp_existing:
                existing_status = cp_existing.get('estado') or cp_existing.get('status')
                # Solo ignorar si ya está 'available' - permitir si está 'offline' (necesita reconexión)
                if existing_status == 'available':
                    print(f"[CENTRAL]  CP {cp_id} ya registrado como 'available' en BD, ignorando registro duplicado")
                    return
                # Si está 'offline', permitir el registro (reconexión después de reinicio)
                elif existing_status == 'offline':
                    print(f"[CENTRAL] CP {cp_id} está 'offline', permitiendo reconexión después de reinicio de Central")
        except Exception as e:
            print(f"[CENTRAL]  Error verificando CP existente: {e}")
    
    print(f"[KAFKA] Processing event for broadcast: {event.get('event_type', 'UNKNOWN')}, clients: {len(shared_state.connected_clients)}")
    
    # Determinar el tipo de evento y formatearlo para el dashboard
    action = event.get('action', '')
    event_type = event.get('event_type', '')
    
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
                localizacion = (data.get('localizacion') or data.get('location') or 
                              event.get('localizacion') or event.get('location') or 'Desconocido')
                # Normalizar location - eliminar espacios
                if localizacion:
                    localizacion = str(localizacion).strip()
                if not localizacion or localizacion == '':
                    # Si aún no hay location, intentar obtenerla de la BD si el CP ya existe
                    if cp:
                        localizacion = cp.get('localizacion') or cp.get('location') or 'Desconocido'
                    if not localizacion or localizacion.strip() == '':
                        localizacion = 'Desconocido'
                
                max_kw = data.get('max_kw') or data.get('max_power_kw') or 22.0
                tarifa_kwh = data.get('tarifa_kwh') or data.get('tariff_per_kwh') or data.get('price_eur_kwh') or 0.30
                estado = 'available'
                print(f"[CENTRAL] Auto-reg CP on connect: cp_id={cp_id}, loc={localizacion}, max_kw={max_kw}, tarifa={tarifa_kwh}")
                # Verificar si el CP ya existe antes de registrar
                cp_existing = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
                
                # Registrar o actualizar
                if hasattr(db, 'register_or_update_charging_point'):
                    db.register_or_update_charging_point(cp_id, localizacion, max_kw=max_kw, tarifa_kwh=tarifa_kwh, estado=estado)
                else:
                    # Fallback: intentar solo actualizar estado
                    db.update_charging_point_status(cp_id, estado)
                
                #  REGISTRAR timestamp del registro para ignorar cp_status_change subsecuentes
                if not hasattr(shared_state, 'recent_registrations'):
                    shared_state.recent_registrations = {}
                import time
                shared_state.recent_registrations[cp_id] = time.time()
                
                # Confirmar existencia y enviar CP_INFO solo una vez
                cp_after = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
                if cp_after:
                    stored_location = cp_after.get('localizacion') or cp_after.get('location') or 'Desconocido'
                    stored_status = cp_after.get('estado') or cp_after.get('status') or 'offline'
                    print(f"[CENTRAL] CP registrado/actualizado: {cp_after['cp_id']} en '{stored_location}' estado={stored_status}" )
                    # PUBLICAR INFORMACIÓN DEL CP AL MONITOR solo si es nuevo registro o cambió realmente
                    #  IMPORTANTE: Evitar publicar CP_INFO innecesariamente para prevenir bucles
                    previous_status = cp_existing.get('estado') if cp_existing else None
                    previous_location = cp_existing.get('localizacion') or cp_existing.get('location') if cp_existing else None
                    previous_max_kw = cp_existing.get('max_kw') if cp_existing else None
                    previous_tariff = cp_existing.get('tarifa_kwh') if cp_existing else None
                    
                    # Verificar si realmente hay cambios
                    status_changed = previous_status != estado
                    location_changed = previous_location != localizacion
                    max_kw_changed = abs((previous_max_kw or 0) - max_kw) > 0.01 if previous_max_kw else True
                    tariff_changed = abs((previous_tariff or 0) - tarifa_kwh) > 0.01 if previous_tariff else True
                    
                    # Simplificado: Si es nuevo CP o cambió de 'offline' a 'available', siempre enviar CP_INFO al Monitor
                    # Esto asegura que cuando Central marca todos como 'offline' y luego los Engines se registran,
                    # el Monitor recibe la información correcta
                    if not cp_existing or status_changed or location_changed or max_kw_changed or tariff_changed:
                        # Nuevo CP o hay cambios (especialmente offline→available), publicar información al Monitor
                        if not cp_existing:
                            print(f"[CENTRAL] Nuevo CP {cp_id} registrado, enviando CP_INFO al Monitor")
                        elif status_changed and previous_status == 'offline' and estado == 'available':
                            print(f"[CENTRAL] CP {cp_id} se registró (offline→available), enviando CP_INFO al Monitor")
                        else:
                            print(f"[CENTRAL] CP {cp_id} cambió, enviando CP_INFO al Monitor")
                        central_instance.publish_cp_info_to_monitor(cp_id, force=(status_changed and previous_status == 'offline'))
                    else:
                        # Mismo estado y datos, no publicar (evitar bucles)
                        print(f"[CENTRAL] CP {cp_id} ya registrado sin cambios (status={estado}), omitiendo CP_INFO para evitar bucle")
                else:
                    print(f"[CENTRAL]  No se pudo verificar CP {cp_id} tras auto-registro")
            except Exception as e:
                print(f"[CENTRAL]  Error auto-registrando CP {cp_id}: {e}")
        
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
                        print(f"[CENTRAL]  Usuario {username} no encontrado en BD")
                except Exception as e:
                    print(f"[CENTRAL]  Error buscando usuario {username}: {e}")
            
            if user_id and cp_id:
                try:
                    # Crear sesión de carga (esto cambia el CP a 'charging')
                    print(f"[CENTRAL] DEBUG: Creando sesión - user_id={user_id}, cp_id={cp_id}")
                    session_id = db.create_charging_session(user_id, cp_id, event.get('correlation_id'))
                    if session_id:
                        print(f"[CENTRAL] Suministro iniciado - Sesión {session_id} en CP {cp_id} para usuario {username}")
                        # PUBLICAR CAMBIO DE ESTADO AL MONITOR (CP ahora en 'charging')
                        central_instance.publish_cp_info_to_monitor(cp_id)
                    else:
                        print(f"[CENTRAL]  Error creando sesión de carga para CP {cp_id} - session_id es None")
                except Exception as e:
                    print(f"[CENTRAL] Error al crear sesión: {e}")
                    import traceback
                    traceback.print_exc()
                else:
                    print(f"[CENTRAL]  No se puede crear sesión: user_id={user_id}, cp_id={cp_id}")
                # Fallback: solo cambiar estado
                if cp_id:
                    db.update_charging_point_status(cp_id, 'charging')
                    print(f"[CENTRAL] CP {cp_id} ahora en modo 'charging' (sin sesión)")
                    # PUBLICAR CAMBIO DE ESTADO AL MONITOR
                    central_instance.publish_cp_info_to_monitor(cp_id)
        
        elif action in ['charging_stopped']:
            # Finalizar sesión de carga y liberar CP
            username = event.get('username')
            user_id = event.get('user_id')
            energy_kwh = event.get('energy_kwh', 0)
            
            print(f"[CENTRAL] Procesando charging_stopped: user={username}, cp={cp_id}, energy={energy_kwh}")
            
            # ENVIAR COMANDO AL CP_E PARA QUE DETENGA LA CARGA
            if cp_id:
                central_instance.publish_event('charging_stopped', {
                    'action': 'charging_stopped',
                    'cp_id': cp_id,
                    'username': username,
                    'user_id': user_id,
                    'energy_kwh': energy_kwh
                })
                print(f"[CENTRAL] Comando charging_stopped enviado a CP_E {cp_id}")
            
            # 1. Si no tenemos user_id, buscar por username
            if not user_id and username:
                try:
                    user = db.get_user_by_username(username)
                    if user:
                        user_id = user.get('id')
                except Exception as e:
                    print(f"[CENTRAL]  Error buscando usuario {username}: {e}")
            
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
                            else:
                                print(f"[CENTRAL]  Error finalizando sesión {session_id}")
                        
                        # Note: end_charging_sesion ya libera el CP automáticamente
                        # PUBLICAR CAMBIO DE ESTADO AL MONITOR
                        central_instance.publish_cp_info_to_monitor(cp_id)
                    else:
                        print(f"[CENTRAL]  No se encontró sesión activa para user_id={user_id}")
                        # Liberar el CP de todas formas
                        if cp_id:
                            db.update_charging_point_status(cp_id, 'available')
                            # PUBLICAR CAMBIO DE ESTADO AL MONITOR
                            central_instance.publish_cp_info_to_monitor(cp_id)
                else:
                    print(f"[CENTRAL]  No se pudo obtener user_id para {username}")
                    # Liberar el CP de todas formas
                    if cp_id:
                        db.update_charging_point_status(cp_id, 'available')
                        # PUBLICAR CAMBIO DE ESTADO AL MONITOR
                        central_instance.publish_cp_info_to_monitor(cp_id)
            except Exception as e:
                print(f"[CENTRAL] Error procesando charging_stopped: {e}")
                import traceback
                traceback.print_exc()
                # Liberar el CP de todas formas
                if cp_id:
                    db.update_charging_point_status(cp_id, 'available')
                    # PUBLICAR CAMBIO DE ESTADO AL MONITOR
                    central_instance.publish_cp_info_to_monitor(cp_id)
        
        # ========================================================================
        # TIMEOUT: CP no respondió después de autorización
        # ========================================================================
        elif action in ['charging_timeout']:
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
                print(f"[CENTRAL]  Error cancelando sesión por timeout: {e}")
            
            # Liberar el CP (cambiar a 'available')
            try:
                    if cp_id:
                        db.update_charging_point_status(cp_id, 'available')
                        print(f"[CENTRAL] CP {cp_id} liberado después de timeout")
                        # PUBLICAR CAMBIO DE ESTADO AL MONITOR
                        central_instance.publish_cp_info_to_monitor(cp_id)
            except Exception as e:
                print(f"[CENTRAL]  Error liberando CP {cp_id}: {e}")
        
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
                    print(f"[CENTRAL]  Error buscando usuario {username}: {e}")
            
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
                            else:
                                print(f"[CENTRAL]  Error finalizando sesión {session_id}")
                        
                        # end_charging_sesion ya libera el CP automáticamente
                    else:
                        print(f"[CENTRAL]  No se encontró sesión activa para user_id={user_id}")
                        if cp_id:
                            db.update_charging_point_status(cp_id, 'available')
                            # PUBLICAR CAMBIO DE ESTADO AL MONITOR
                            central_instance.publish_cp_info_to_monitor(cp_id)
                else:
                    print(f"[CENTRAL]  No se pudo obtener user_id para {username}")
                    if cp_id:
                        db.update_charging_point_status(cp_id, 'available')
                        # PUBLICAR CAMBIO DE ESTADO AL MONITOR
                        central_instance.publish_cp_info_to_monitor(cp_id)
            except Exception as e:
                print(f"[CENTRAL] Error procesando charging_completed: {e}")
                import traceback
                traceback.print_exc()
                if cp_id:
                    db.update_charging_point_status(cp_id, 'available')
                    # PUBLICAR CAMBIO DE ESTADO AL MONITOR
                    central_instance.publish_cp_info_to_monitor(cp_id)
        
        # ========================================================================
        # ACTUALIZACIÓN DE PROGRESO DE CARGA (del CP_E)
        # ========================================================================
        elif action in ['charging_progress'] or event_type == 'charging_progress':
            #  PROTECCIÓN: Throttling para charging_progress - no actualizar más de una vez por segundo
            # porque el Engine envía actualizaciones cada segundo
            if not hasattr(shared_state, '_last_progress_update'):
                shared_state._last_progress_update = {}  # {(username, cp_id): timestamp}
            
            username = event.get('username')
            energy_kwh = event.get('energy_kwh', 0.0)
            cost = event.get('cost', 0.0)
            
            # Verificar throttling por usuario y CP
            progress_key = (username or '', cp_id or '')
            last_update_time = shared_state._last_progress_update.get(progress_key, 0)
            
            # Solo actualizar si pasó al menos 0.5 segundos desde la última actualización
            # Esto reduce el ruido en logs pero permite actualizaciones razonables
            if current_time - last_update_time < 0.5:
                # Silenciar para no saturar logs, pero no es un error
                pass  # Omitir actualización muy frecuente
            else:
                shared_state._last_progress_update[progress_key] = current_time
                print(f"[CENTRAL] Progreso de carga: {username} → {energy_kwh:.2f} kWh, €{cost:.2f}")
                
                # Actualizar energía en la sesión activa de la BD
                try:
                    if username:
                        user = db.get_user_by_username(username)
                        if user:
                            user_id = user.get('id')
                            session = db.get_active_sesion_for_user(user_id)
                            if session:
                                session_id = session.get('id')
                                # Actualizar energia_kwh en la sesión
                                conn = db.get_connection()
                                cur = conn.cursor()
                                cur.execute("""
                                    UPDATE charging_sesiones
                                    SET energia_kwh = ?
                                    WHERE id = ? AND estado = 'active'
                                """, (energy_kwh, session_id))
                                conn.commit()
                                conn.close()
                                # Solo imprimir cada 5 segundos para reducir ruido
                                if int(current_time) % 5 == 0:
                                    print(f"[CENTRAL] Sesión {session_id} actualizada: {energy_kwh:.2f} kWh")
                except Exception as e:
                    print(f"[CENTRAL]  Error actualizando progreso de sesión: {e}")
        
        elif action in ['cp_status_change']:
            """
             IMPORTANTE: Este evento viene del Engine que YA cambió su estado.
            Central solo debe ACTUALIZAR la BD para reflejar el cambio, NO causar más cambios.
            No debe publicar eventos que puedan causar que el Engine vuelva a cambiar estado.
            """
            status = event.get('status')
            if not status:
                print(f"[CENTRAL]  cp_status_change sin 'status', ignorando")
                return
            
            #  PROTECCIÓN: Ignorar cp_status_change que viene justo después de CP_REGISTRATION
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
                print(f"[CENTRAL]  Error asegurando CP en cp_status_change: {e}")
            
            # Solo actualizar BD si el estado cambió realmente (sincronización con Engine)
            cp_current = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
            current_status = cp_current.get('estado') or cp_current.get('status') if cp_current else None
            
            #  CRÍTICO: Solo actualizar BD si el estado realmente cambió
            # NO publicar CP_INFO cuando el estado ya está sincronizado para evitar bucles infinitos
            # El Monitor ya recibe el cp_status_change del Engine directamente
            if current_status == status:
                print(f"[CENTRAL] Estado {status} para CP {cp_id} ya está sincronizado en BD, omitiendo actualización para evitar bucle")
                # NO llamar a publish_cp_info_to_monitor aquí porque ya está sincronizado
                # Esto previene bucles infinitos cuando el estado no cambió realmente
                return
            
            #  PROTECCIÓN ADICIONAL: Si el estado es 'available' y hubo un registro reciente, ignorar
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
            
            #  PROTECCIÓN CRÍTICA: Ignorar cp_status_change a 'offline' si el CP se acaba de registrar como 'available'
            # Esto previene que mensajes antiguos de Kafka o reinicios de Engine causen que los CPs vuelvan a 'offline'
            # después de haberse registrado correctamente
            if status == 'offline' and current_status == 'available':
                if not hasattr(shared_state, 'recent_registrations'):
                    shared_state.recent_registrations = {}
                recent_reg_time = shared_state.recent_registrations.get(cp_id, 0)
                if recent_reg_time > 0:
                    time_since_reg = time.time() - recent_reg_time
                    if time_since_reg < 30.0:  # Si se registró hace menos de 30 segundos, ignorar cambio a 'offline'
                        print(f"[CENTRAL]  Ignorando cp_status_change a 'offline' para CP {cp_id} - acaba de registrarse como 'available' hace {time_since_reg:.1f}s")
                        print(f"[CENTRAL]    Esto previene que mensajes antiguos de Kafka o reinicios causen desconexión incorrecta")
                        return
            
            # Solo si el estado cambió realmente, actualizar BD
            print(f"[CENTRAL] Sincronizando estado BD: {cp_id} → {current_status} → {status} (cambio reportado por Engine)")
            db.update_charging_point_status(cp_id, status)
            
            #  IMPORTANTE: Publicar CP_INFO al Monitor SOLO una vez después de actualizar BD
            # Esto informa al Monitor del cambio de estado sin causar bucles
            central_instance.publish_cp_info_to_monitor(cp_id)
        elif action in ['cp_error_simulated', 'cp_error_fixed']:
            new_status = event.get('new_status') or event.get('status')
            if new_status:
                db.update_charging_point_status(cp_id, new_status)
                # PUBLICAR CAMBIO DE ESTADO AL MONITOR
                central_instance.publish_cp_info_to_monitor(cp_id)
        
        # ========================================================================
        # FALLOS DEL ENGINE REPORTADOS POR EL MONITOR
        # ========================================================================
        # Cuando el Monitor detecta que el Engine no responde (3+ timeouts),
        # notifica a Central para que cancele sesiones activas y libere el CP
        elif event_type in ['ENGINE_FAILURE', 'ENGINE_OFFLINE'] or action in ['report_engine_failure', 'report_engine_offline']:
            failure_type = event.get('failure_type', 'unknown')
            consecutive_failures = event.get('consecutive_failures', 0)
            
            print(f"[CENTRAL] ENGINE_FAILURE recibido: cp={cp_id}, type={failure_type}, failures={consecutive_failures}")
            
            # Cambiar estado del CP a 'offline' o 'fault'
            new_status = 'offline' if event_type == 'ENGINE_OFFLINE' else 'fault'
            
            #  PROTECCIÓN: Verificar si el estado ya está sincronizado para evitar procesamiento innecesario
            try:
                cp_current = db.get_charging_point(cp_id) if hasattr(db, 'get_charging_point') else None
                current_status = cp_current.get('estado') or cp_current.get('status') if cp_current else None
                
                # Si el estado ya está sincronizado, solo procesar la cancelación de sesiones si es necesario
                if current_status == new_status:
                    print(f"[CENTRAL] Estado {new_status} para CP {cp_id} ya está sincronizado, omitiendo actualización de BD para evitar bucle")
                    # NO publicar CP_INFO porque el estado ya está sincronizado
                    # Solo procesar cancelación de sesiones si hay alguna activa
                    # NO llamar a publish_cp_info_to_monitor aquí porque causaría bucle
                else:
                    # El estado cambió realmente, actualizar BD
                    db.update_charging_point_status(cp_id, new_status)
                    print(f"[CENTRAL] CP {cp_id} marcado como {new_status} (era {current_status})")
                    # PUBLICAR CAMBIO DE ESTADO AL MONITOR solo si el estado realmente cambió
                    # NO usar force=True aquí para respetar throttling
                    central_instance.publish_cp_info_to_monitor(cp_id)
            except Exception as e:
                print(f"[CENTRAL]  Error verificando/actualizando estado del CP: {e}")
            
            # Buscar y cancelar sesión activa en este CP
            try:
                # Buscar sesión activa en este CP
                active_sessions = db.get_active_sessions_for_cp(cp_id) if hasattr(db, 'get_active_sessions_for_cp') else []
                
                if not active_sessions:
                    # Fallback: buscar sesión activa más reciente
                    all_sessions = db.get_all_sessions() if hasattr(db, 'get_all_sessions') else []
                    active_sessions = [s for s in all_sessions if s.get('cp_id') == cp_id and s.get('estado') == 'active']
                
                for session in active_sessions:
                    session_id = session.get('id')
                    user_id = session.get('user_id')
                    
                    if session_id and user_id:
                        # Obtener usuario
                        user = db.get_user_by_id(user_id)
                        if user:
                            username = user.get('username')
                            
                            # Cancelar sesión (0 energía porque el CP falló)
                            if hasattr(db, 'cancel_charging_session'):
                                db.cancel_charging_session(session_id)
                            else:
                                db.end_charging_sesion(session_id, 0.0)
                            
                            print(f"[CENTRAL] Sesión {session_id} cancelada por ENGINE_FAILURE para usuario {username}")
                            
                            # Notificar al Driver vía Kafka para que cancele la sesión
                            central_instance.publish_event('CP_ERROR_SIMULATED', {
                                'cp_id': cp_id,
                                'error_type': 'engine_failure',
                                'message': f'El punto de carga {cp_id} no responde. La carga ha sido cancelada.',
                                'username': username,
                                'user_id': user_id
                            })
                            
                            # También enviar evento específico de timeout para limpiar estado
                            central_instance.publish_event('CHARGING_TIMEOUT', {
                                'username': username,
                                'user_id': user_id,
                                'cp_id': cp_id,
                                'reason': f'CP Engine no responde ({failure_type})',
                                'timestamp': time.time()
                            })
                            
                            print(f"[CENTRAL] Notificación de fallo enviada a Driver para usuario {username}")
            except Exception as e:
                print(f"[CENTRAL]  Error cancelando sesión por ENGINE_FAILURE: {e}")
                import traceback
                traceback.print_exc()
        
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
                    print(f"[CENTRAL]   Monitor {monitor_id} authentication failed: CP {cp_id} not found")
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
        print(f"[KAFKA]   No clients connected, skipping broadcast (events already processed)")
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
            'message': f" Error simulado en {event.get('cp_id')}: {event.get('error_type')}"
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

async def main():
    """Función principal que inicia todos los servicios"""
    local_ip = get_local_ip()
    
    print("\n" + "=" * 80)
    print(" " * 22 + " EV CENTRAL - Admin WebSocket Server")
    print("=" * 80)
    print(f"  Local Access:     http://localhost:{SERVER_PORT}")
    print(f"  Network Access:   http://{local_ip}:{SERVER_PORT}")
    print(f"  WebSocket:        ws://{local_ip}:{SERVER_PORT}/ws")
    print(f"  Database:         ev_charging.db")
    print(f"  Kafka Broker:     {KAFKA_BROKER}")
    print(f"  Consuming:        {', '.join(KAFKA_TOPICS_CONSUME)}")
    print(f"  Publishing:       {KAFKA_TOPIC_PRODUCE}")
    print("=" * 80)
    print(f"\n   Access from other PCs: http://{local_ip}:{SERVER_PORT}")
    print(f"    Make sure firewall allows port {SERVER_PORT}")
    print("=" * 80 + "\n")
    
    if not WS_AVAILABLE:
        print("ERROR: WebSocket dependencies not installed")
        print("Run: pip install websockets aiohttp")
        return
    
    # Verificar base de datos
    # En Docker, la BD está en /app/ev_charging.db
    db_path = Path('/app/ev_charging.db')
    if not db_path.exists():
        # Intentar también en el directorio actual
        db_path = Path('ev_charging.db')
        if not db_path.exists():
            print("  Database not found. Please run: python init_db.py")
            return
    else:
        # Requisito: al iniciar Central TODO debe estar apagado
        try:
            # Actualizar timestamp de inicio para filtrar eventos antiguos
            shared_state.central_start_time = time.time()
            print(f"[CENTRAL] Timestamp de inicio de Central: {shared_state.central_start_time}")
            
            # 1) Terminar cualquier sesión activa que haya quedado de ejecuciones anteriores
            if hasattr(db, 'terminate_all_active_sessions'):
                sess, cps = db.terminate_all_active_sessions(mark_cp_offline=True)
                print(f"[CENTRAL] Inicio: sesiones activas terminadas: {sess}, CPs marcados offline: {cps}")
            # 2) Marcar TODOS los CPs como 'offline' al iniciar Central
            # Esto asegura que Central no asume que los CPs están conectados hasta que se registren
            updated = db.set_all_cps_status_offline() if hasattr(db, 'set_all_cps_status_offline') else 0
            if updated > 0:
                print(f"[CENTRAL] {updated} CP(s) marcado(s) como 'offline' al inicio - esperando registro de Engines")
            else:
                print(f"[CENTRAL] No hay CPs en BD o ya están marcados como offline")
        except Exception as e:
            print(f"[CENTRAL]  No se pudo limpiar estado al inicio: {e}")
    
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
        
        print("\nAll services started successfully!")
        print(f"Open http://localhost:{SERVER_PORT} in your browser\n")
        
        # Mantener el servidor corriendo
        await asyncio.gather(broadcast_task, kafka_task)
        
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
            print(f"\n[CENTRAL]  Shutdown cleanup error: {e}")
        print("\n[CENTRAL] Server stopped by user")
    except Exception as e:
        print(f"\nFatal error: {e}")
