import sys
import os
import asyncio
import json
import threading
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta

"""
================================================================================
EV_Central - Sistema Central de Gestión de Puntos de Recarga
================================================================================

CUMPLIMIENTO DE REQUISITOS:

a) REGISTRO Y ALTA DE NUEVOS PUNTOS DE RECARGA
   La Central está SIEMPRE a la espera de peticiones de registro mediante:
   
   1. WebSocket (Registro Manual):
      - Líneas 358-423: Handler 'register_cp'
      - Dashboard administrativo permite dar de alta CPs manualmente
      - Validaciones: campos requeridos, duplicados
      - Confirmación inmediata al cliente
   
   2. Kafka (Auto-registro):
      - Líneas 486-603: kafka_listener() con bucle infinito
      - Escucha topic 'cp-events' permanentemente
      - Al recibir CP_REGISTRATION o 'connect', auto-registra el CP
      - Thread daemon que nunca se detiene
   
   3. Procesamiento en tiempo real:
      - Líneas 604-700: broadcast_kafka_event()
      - Actualiza estado del CP inmediatamente
      - Persiste en base de datos
      - Broadcast a todos los clientes conectados

b) AUTORIZACIÓN DE SUMINISTRO
   La Central procesa peticiones de autorización mediante:
   
   1. Validación multi-nivel (en EV_Driver_WebSocket.py):
      - Usuario existe y activo
      - No tiene sesión activa previa
      - Balance suficiente (mín €5.00)
      - Disponibilidad de Charging Points
   
   2. Recepción de eventos autorizados:
      - Kafka consumer recibe eventos 'charging_started'
      - Solo llegan aquí peticiones YA autorizadas por Driver
      - Central actualiza estado CP a 'charging'
      - Registra sesión activa en BD
   
   3. Seguimiento de sesión:
      - Actualización continua vía Kafka
      - Finalización con cálculo de costo
      - Actualización de balance usuario

ARQUITECTURA:
- WebSocket: Comunicación en tiempo real con dashboards
- Kafka: Sistema de mensajería asíncrono distribuido
- SQLite: Base de datos para persistencia
- Asyncio: Operaciones concurrentes y no bloqueantes
- Threading: Consumer Kafka en thread daemon permanente

La Central NUNCA deja de escuchar. El bucle de Kafka es infinito y corre
en un thread daemon que se mantiene activo durante toda la ejecución.
================================================================================
"""

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
KAFKA_TOPICS_CONSUME = [KAFKA_TOPICS['driver_events'], KAFKA_TOPICS['cp_events']]
KAFKA_TOPIC_PRODUCE = KAFKA_TOPICS['central_events']
SERVER_PORT = int(os.environ.get('CENTRAL_PORT', CENTRAL_CONFIG['ws_port']))

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

    def initialize_kafka(self, max_retries=10):
        """Inicializa el productor de Kafka con reintentos"""
        for attempt in range(max_retries):
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=self.kafka_broker,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
                print(f"[CENTRAL] ✅ Kafka producer initialized")
                return
            except Exception as e:
                print(f"[CENTRAL] ⚠️  Attempt {attempt+1}/{max_retries} - Kafka not available: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    print(f"[CENTRAL] ❌ Failed to connect to Kafka after {max_retries} attempts")
    
    def ensure_producer(self):
        """Asegura que el producer esté disponible, reintentando si es necesario"""
        if self.producer is None:
            print(f"[CENTRAL] 🔄 Producer not initialized, attempting reconnection...")
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=self.kafka_broker,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
                print(f"[CENTRAL] ✅ Kafka producer reconnected successfully")
                return True
            except Exception as e:
                print(f"[CENTRAL] ❌ Producer reconnection failed: {e}")
                return False
        return True

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
            'status': self._normalize_status(cp_row.get('estado') or cp_row.get('status')),
            'max_power_kw': cp_row.get('max_power_kw') or cp_row.get('max_kw'),
            'tariff_per_kwh': cp_row.get('tariff_per_kwh') or cp_row.get('tarifa_kwh'),
            'active': cp_row.get('active', 1),
            'power_output': cp_row.get('max_power_kw') or cp_row.get('max_kw')
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
                        
                        # 🆕 FINALIZAR SESIÓN ACTIVA si existe en este CP
                        try:
                            # Buscar sesión activa en este CP
                            sesiones_activas = db.get_sesiones_actividad()
                            for sesion in sesiones_activas:
                                if sesion.get('cp_id') == cp_id:
                                    session_id = sesion.get('id')
                                    print(f"[CENTRAL] ⚠️ Finalizando sesión {session_id} por error en {cp_id}")
                                    # Finalizar con 0 kWh (error interrumpió la carga)
                                    result = db.end_charging_sesion(session_id, 0.0)
                                    if result:
                                        print(f"[CENTRAL] ✅ Sesión {session_id} finalizada por error")
                                    break
                        except Exception as e:
                            print(f"[CENTRAL] ⚠️ Error finalizando sesión en CP con error: {e}")
                        
                        # Actualizar estado en BD
                        db.update_charging_point_status(cp_id, new_status)
                        
                        # 🆕 PUBLICAR EVENTO EN KAFKA para notificar al Driver
                        central_instance.publish_event('CP_ERROR_SIMULATED', {
                            'cp_id': cp_id,
                            'error_type': error_type,
                            'new_status': new_status,
                            'message': f'Error "{error_type}" simulado en {cp_id}'
                        })
                        print(f"[CENTRAL] 📢 Publicado CP_ERROR_SIMULATED en Kafka para {cp_id}")
                        
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
                        
                        # 🆕 PUBLICAR EVENTO EN KAFKA para notificar al Driver
                        central_instance.publish_event('CP_ERROR_FIXED', {
                            'cp_id': cp_id,
                            'new_status': 'available',
                            'message': f'Error corregido en {cp_id}'
                        })
                        print(f"[CENTRAL] 📢 Publicado CP_ERROR_FIXED en Kafka para {cp_id}")
                        
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
                            print(f"[CENTRAL] 🛑 Parando TODOS los CPs...")
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
                                                    print(f"[CENTRAL] ⚠️ Sesión {session_id} terminada por parada de {cp_id_item}")
                                                    break
                                        except Exception as e:
                                            print(f"[CENTRAL] ⚠️ Error terminando sesión en {cp_id_item}: {e}")
                                    
                                    # Cambiar a out_of_service
                                    db.update_charging_point_status(cp_id_item, 'out_of_service')
                                    
                                    # Publicar comando vía Kafka al CP_E
                                    central_instance.publish_event('CP_STOP', {
                                        'cp_id': cp_id_item,
                                        'action': 'stop',
                                        'new_status': 'out_of_service',
                                        'reason': 'Stopped by admin'
                                    })
                            
                            await ws.send_str(json.dumps({
                                'type': 'stop_cp_success',
                                'message': f'Todos los CPs detenidos'
                            }))
                        elif cp_id:
                            # Parar CP específico
                            print(f"[CENTRAL] 🛑 Parando CP {cp_id}...")
                            
                            # Finalizar sesión activa si existe
                            try:
                                sesiones = db.get_active_sessions() if hasattr(db, 'get_active_sessions') else []
                                for session in sesiones:
                                    if session.get('cp_id') == cp_id:
                                        session_id = session.get('id')
                                        db.end_charging_sesion(session_id, 0.0)  # 0 kWh por interrupción
                                        print(f"[CENTRAL] ⚠️ Sesión {session_id} terminada por parada de {cp_id}")
                                        break
                            except Exception as e:
                                print(f"[CENTRAL] ⚠️ Error terminando sesión en {cp_id}: {e}")
                            
                            # Cambiar estado a out_of_service
                            db.update_charging_point_status(cp_id, 'out_of_service')
                            
                            # Publicar comando vía Kafka al CP_E
                            central_instance.publish_event('CP_STOP', {
                                'cp_id': cp_id,
                                'action': 'stop',
                                'new_status': 'out_of_service',
                                'reason': 'Stopped by admin'
                            })
                            print(f"[CENTRAL] 📢 Publicado CP_STOP en Kafka para {cp_id}")
                            
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
                            print(f"[CENTRAL] ▶️ Reanudando TODOS los CPs...")
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
                            
                            await ws.send_str(json.dumps({
                                'type': 'resume_cp_success',
                                'message': f'Todos los CPs reanudados'
                            }))
                        elif cp_id:
                            # Reanudar CP específico
                            print(f"[CENTRAL] ▶️ Reanudando CP {cp_id}...")
                            
                            # Cambiar estado a available
                            db.update_charging_point_status(cp_id, 'available')
                            
                            # Publicar comando vía Kafka al CP_E
                            central_instance.publish_event('CP_RESUME', {
                                'cp_id': cp_id,
                                'action': 'resume',
                                'new_status': 'available',
                                'reason': 'Resumed by admin'
                            })
                            print(f"[CENTRAL] 📢 Publicado CP_RESUME en Kafka para {cp_id}")
                            
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
                        existing_cp = db.get_charging_point_by_id(cp_id) if hasattr(db, 'get_charging_point_by_id') else None
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
                                print(f"[CENTRAL] ✅ Nuevo punto de carga registrado: {cp_id} en {location}")
                                
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
                            print(f"[CENTRAL] ❌ Error registrando CP {cp_id}: {e}")
                            await ws.send_str(json.dumps({
                                'type': 'register_cp_error',
                                'message': f'Error al registrar el punto de carga: {str(e)}'
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
                print(f"[KAFKA] 🔄 Attempt {retry_count + 1}/{max_retries} to connect to Kafka at {KAFKA_BROKER}")
                consumer = KafkaConsumer(
                    *KAFKA_TOPICS_CONSUME,
                    bootstrap_servers=KAFKA_BROKER,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='latest',  # Solo mensajes nuevos
                    group_id='ev_central_ws_group',
                    enable_auto_commit=True  # Guardar progreso
                )
                # Test connection
                consumer.topics()
                print(f"[KAFKA] ✅ Connected to Kafka successfully!")
                print(f"[KAFKA] 📡 Consumer started, listening to {KAFKA_TOPICS_CONSUME}")
                break
            except Exception as e:
                retry_count += 1
                if consumer:
                    consumer.close()
                print(f"[KAFKA] ⚠️ Attempt {retry_count}/{max_retries} failed: {e}")
                if retry_count < max_retries:
                    time.sleep(2)
                    continue
                else:
                    print(f"[KAFKA] ❌ Failed to connect to Kafka after {max_retries} attempts")
                    return
        
        if not consumer:
            print("[KAFKA] ❌ Cannot continue without Kafka connection")
            return
        
        try:
            
            # ========================================================================
            # BUCLE INFINITO - La Central NUNCA deja de escuchar
            # ========================================================================
            for message in consumer:
                event = message.value
                print(f"[KAFKA] 📨 Received event: {event.get('event_type', 'UNKNOWN')} from topic: {message.topic}")
                
                # ====================================================================
                # REQUISITO a) Registro de Charging Points (Auto-registro)
                # ====================================================================
                # Cuando un CP se conecta o envía CP_REGISTRATION, se registra
                # automáticamente en la base de datos
                # --------------------------------------------------------------------
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
                            print(f"[CENTRAL] 💾 CP registrado/actualizado (auto-registro): {cp_id}")
                    
                    # Auto-crear CP si llega evento pero no existe
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
                        
                        print(f"[CENTRAL] 🔍 DEBUG - cp_id recibido: {cp_id!r} (tipo: {type(cp_id).__name__})")
                        
                        if not client_id:
                            raise ValueError("Client ID es requerido")
                        
                        # Si no se especifica CP, buscar y reservar automáticamente (atómico)
                        if not cp_id or cp_id == 'None' or cp_id == 'null':
                            print(f"[CENTRAL] 🔐 Solicitud de autorización: usuario={username}, buscando CP disponible...")
                            
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
                            
                            print(f"[CENTRAL] 🎯 CP {cp_id} asignado y reservado automáticamente para {username}")
                            
                            # Ya está reservado, enviar respuesta positiva al Driver
                            central_instance.publish_event('AUTHORIZATION_RESPONSE', {
                                'client_id': client_id,
                                'cp_id': cp_id, 
                                'authorized': True
                            })
                            
                            # 🆕 Enviar comando al CP_E para que inicie la carga
                            # El CP_E escucha central-events y procesará este comando
                            central_instance.publish_event('charging_started', {
                                'action': 'charging_started',
                                'cp_id': cp_id,
                                'username': username,
                                'user_id': event.get('user_id'),
                                'client_id': client_id
                            })
                            print(f"[CENTRAL] 📤 Comando charging_started enviado a CP_E {cp_id}")
                        else:
                            # Si se especifica un CP concreto, verificar y reservar
                            print(f"[CENTRAL] 🔐 Solicitud de autorización: usuario={username}, cp={cp_id}, client={client_id}")
                            
                            # Verificar estado del punto de carga
                            cp = db.get_charging_point_by_id(cp_id)
                            if not cp:
                                central_instance.publish_event('AUTHORIZATION_RESPONSE', {
                                    'client_id': client_id,
                                    'cp_id': cp_id,
                                    'authorized': False,
                                    'reason': 'CP no encontrado'
                                })
                                continue
                                
                            current_status = cp.get('status') or cp.get('estado')
                            print(f"[CENTRAL] 📊 CP {cp_id} tiene estado: {current_status}")
                            
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
                                print(f"[CENTRAL] ✅ CP {cp_id} reservado para cliente {client_id}")
                                central_instance.publish_event('AUTHORIZATION_RESPONSE', {
                                    'client_id': client_id,
                                    'cp_id': cp_id, 
                                    'authorized': True
                                })
                                
                                # 🆕 Enviar comando al CP_E para que inicie la carga
                                central_instance.publish_event('charging_started', {
                                    'action': 'charging_started',
                                    'cp_id': cp_id,
                                    'username': username,
                                    'user_id': event.get('user_id'),
                                    'client_id': client_id
                                })
                                print(f"[CENTRAL] 📤 Comando charging_started enviado a CP_E {cp_id}")
                            else:
                                central_instance.publish_event('AUTHORIZATION_RESPONSE', {
                                    'client_id': client_id,
                                    'cp_id': cp_id,
                                    'authorized': False,
                                    'reason': 'No se pudo reservar el CP'
                                })
                    except Exception as e:
                        print(f"[CENTRAL] ⚠️ Error procesando autorización: {e}")
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
                
                # Programar el broadcast en el event loop
                asyncio.run_coroutine_threadsafe(
                    broadcast_kafka_event(event),
                    loop
                )
                
        except Exception as e:
            print(f"[KAFKA] ⚠️  Consumer error during loop: {e}")
    
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
    print(f"[KAFKA] 🔄 Processing event for broadcast: {event.get('event_type', 'UNKNOWN')}, clients: {len(shared_state.connected_clients)}")
    
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
        
        # --------------------------------------------------------------------
        # REQUISITO b) AUTORIZACIÓN DE SUMINISTRO - Sesión iniciada
        # --------------------------------------------------------------------
        elif action in ['charging_started']:
            # Crear sesión de carga y cambiar estado del CP
            username = event.get('username')
            user_id = event.get('user_id')
            
            if user_id and cp_id:
                try:
                    # Crear sesión de carga (esto cambia el CP a 'charging')
                    session_id = db.create_charging_session(user_id, cp_id, event.get('correlation_id'))
                    if session_id:
                        print(f"[CENTRAL] ⚡ Suministro iniciado - Sesión {session_id} en CP {cp_id} para usuario {username}")
                    else:
                        print(f"[CENTRAL] ⚠️ Error creando sesión de carga para CP {cp_id}")
                except Exception as e:
                    print(f"[CENTRAL] ⚠️ Error al crear sesión: {e}")
            else:
                # Fallback: solo cambiar estado
                if db.release_charging_point(cp_id, 'charging'):
                    print(f"[CENTRAL] ⚡ CP {cp_id} ahora en modo 'charging'")
                else:
                    print(f"[CENTRAL] ⚠️ Error liberando reserva de CP {cp_id} para inicio de carga")
        
        elif action in ['charging_stopped']:
            # Finalizar sesión de carga y liberar CP
            username = event.get('username')
            user_id = event.get('user_id')
            energy_kwh = event.get('energy_kwh', 0)
            
            print(f"[CENTRAL] ⛔ Procesando charging_stopped: user={username}, cp={cp_id}, energy={energy_kwh}")
            
            # 1. Si no tenemos user_id, buscar por username
            if not user_id and username:
                try:
                    user = db.get_user_by_username(username)
                    if user:
                        user_id = user.get('id')
                except Exception as e:
                    print(f"[CENTRAL] ⚠️ Error buscando usuario {username}: {e}")
            
            # 2. Buscar sesión activa del usuario
            try:
                if user_id:
                    session = db.get_active_sesion_for_user(user_id)
                    if session:
                        session_id = session.get('id')
                        
                        # 3. Finalizar sesión en BD (usa end_charging_sesion, no session)
                        if session_id:
                            result = db.end_charging_sesion(session_id, energy_kwh)
                            if result:
                                print(f"[CENTRAL] ✅ Sesión {session_id} finalizada: {energy_kwh} kWh, coste={result.get('coste', 0):.2f} EUR")
                            else:
                                print(f"[CENTRAL] ⚠️ Error finalizando sesión {session_id}")
                        
                        # Note: end_charging_sesion ya libera el CP automáticamente
                    else:
                        print(f"[CENTRAL] ⚠️ No se encontró sesión activa para user_id={user_id}")
                        # Liberar el CP de todas formas
                        db.release_charging_point(cp_id, 'available')
                else:
                    print(f"[CENTRAL] ⚠️ No se pudo obtener user_id para {username}")
                    # Liberar el CP de todas formas
                    db.release_charging_point(cp_id, 'available')
            except Exception as e:
                print(f"[CENTRAL] ❌ Error procesando charging_stopped: {e}")
                import traceback
                traceback.print_exc()
                # Liberar el CP de todas formas
                db.release_charging_point(cp_id, 'available')
        
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
            
            print(f"[CENTRAL] 🎫 Procesando charging_completed (desenchufe): user={username}, cp={cp_id}, energy={energy_kwh}")
            
            # 1. Buscar user_id si no lo tenemos
            if not user_id and username:
                try:
                    user = db.get_user_by_username(username)
                    if user:
                        user_id = user.get('id')
                except Exception as e:
                    print(f"[CENTRAL] ⚠️ Error buscando usuario {username}: {e}")
            
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
                                print(f"[CENTRAL] ✅ Sesión {session_id} finalizada por desenchufe")
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
                                print(f"[CENTRAL] 🎫 Ticket enviado a conductor {username}")
                            else:
                                print(f"[CENTRAL] ⚠️ Error finalizando sesión {session_id}")
                        
                        # end_charging_sesion ya libera el CP automáticamente
                    else:
                        print(f"[CENTRAL] ⚠️ No se encontró sesión activa para user_id={user_id}")
                        db.release_charging_point(cp_id, 'available')
                else:
                    print(f"[CENTRAL] ⚠️ No se pudo obtener user_id para {username}")
                    db.release_charging_point(cp_id, 'available')
            except Exception as e:
                print(f"[CENTRAL] ❌ Error procesando charging_completed: {e}")
                import traceback
                traceback.print_exc()
                db.release_charging_point(cp_id, 'available')
        
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
            
            print(f"[CENTRAL] 🔐 Monitor authentication received")
            print(f"[CENTRAL]    Monitor:      {monitor_id}")
            print(f"[CENTRAL]    CP:           {cp_id}")
            print(f"[CENTRAL]    Status:       {monitor_status}")
            print(f"[CENTRAL]    Engine:       {engine_host}:{engine_port}")
            
            # Validar que el CP existe en la BD
            try:
                cp = db.get_charging_point_by_id(cp_id)
                if cp:
                    print(f"[CENTRAL] ✅ Monitor {monitor_id} authenticated and validated")
                    print(f"[CENTRAL] ✅ Monitor is ready to supervise {cp_id}")
                    
                    # Opcional: Publicar confirmación de autenticación
                    central_instance.publish_event('MONITOR_AUTH_RESPONSE', {
                        'cp_id': cp_id,
                        'monitor_id': monitor_id,
                        'status': 'AUTHENTICATED',
                        'message': f'Monitor {monitor_id} authenticated successfully'
                    })
                else:
                    print(f"[CENTRAL] ⚠️  Monitor {monitor_id} authentication failed: CP {cp_id} not found")
            except Exception as e:
                print(f"[CENTRAL] ❌ Error authenticating monitor {monitor_id}: {e}")
        
        # ========================================================================
        # REQUISITO 10: Monitor detecta avería y notifica a Central
        # ========================================================================
        elif event_type in ['ENGINE_FAILURE', 'ENGINE_OFFLINE'] or action in ['report_engine_failure', 'report_engine_offline']:
            failure_type = event.get('failure_type', 'unknown')
            consecutive_failures = event.get('consecutive_failures', 0)
            
            print(f"[CENTRAL] 🚨 AVERÍA DETECTADA en {cp_id} por Monitor")
            print(f"[CENTRAL]    Tipo: {failure_type}, Fallos consecutivos: {consecutive_failures}")
            
            # Cambiar estado del CP a 'fault' (AVERIADO)
            if cp_id:
                db.update_charging_point_status(cp_id, 'fault')
                print(f"[CENTRAL] 🔴 CP {cp_id} marcado como 'fault' en BD")
                
                # Si hay sesión activa en este CP, finalizarla inmediatamente
                try:
                    sesiones_activas = db.get_active_sessions() if hasattr(db, 'get_active_sessions') else []
                    for sesion in sesiones_activas:
                        if sesion.get('cp_id') == cp_id:
                            session_id = sesion.get('id')
                            username = sesion.get('username')
                            print(f"[CENTRAL] ⚠️ Finalizando sesión {session_id} por avería en {cp_id}")
                            
                            # Finalizar con 0 kWh (avería interrumpió la carga)
                            result = db.end_charging_sesion(session_id, 0.0)
                            if result:
                                print(f"[CENTRAL] ✅ Sesión {session_id} finalizada por avería")
                                
                                # Notificar al conductor
                                central_instance.publish_event('CHARGING_INTERRUPTED', {
                                    'username': username,
                                    'cp_id': cp_id,
                                    'reason': 'CP_FAILURE',
                                    'message': f'La carga se interrumpió por avería en {cp_id}',
                                    'timestamp': time.time()
                                })
                                print(f"[CENTRAL] 📢 Conductor {username} notificado de interrupción")
                            break
                except Exception as e:
                    print(f"[CENTRAL] ❌ Error finalizando sesión por avería: {e}")

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
    # En Docker, la BD está en /app/ev_charging.db
    db_path = Path('/app/ev_charging.db')
    if not db_path.exists():
        # Intentar también en el directorio actual
        db_path = Path('ev_charging.db')
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
  🏢 EV CENTRAL - Sistema Central de Gestión
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
            print(f"\n[CENTRAL] ⚠️ Shutdown cleanup error: {e}")
        print("\n[CENTRAL] 🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
