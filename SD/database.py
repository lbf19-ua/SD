"""
Database module for EV Charging System
SQLite database with users, charging points, sesiones, and event logs
"""
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
import json
import sys

# Ruta de la base de datos (en la carpeta SD)
# En Docker: la BD está en /app/ev_charging.db
# Fuera de Docker: en el directorio padre de database.py
if Path('/app/ev_charging.db').exists():
    DB_PATH = Path('/app/ev_charging.db')
else:
    DB_PATH = Path(__file__).parent / "ev_charging.db"

# Abre y devuelve una conexión SQLite
def get_connection():
    """Obtiene una conexión a la base de datos con optimizaciones para concurrencia"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)  # Timeout más largo para concurrencia
    conn.row_factory = sqlite3.Row  # Permite acceder a columnas por nombre
    # Habilitar WAL mode para mejor concurrencia (permite lecturas mientras hay escrituras)
    conn.execute('PRAGMA journal_mode=WAL')
    # Optimizaciones adicionales
    conn.execute('PRAGMA synchronous=NORMAL')  # Balance entre seguridad y velocidad
    conn.execute('PRAGMA cache_size=10000')    # Cache más grande
    conn.execute('PRAGMA temp_store=MEMORY')   # Tablas temporales en memoria
    return conn

# Crea las tablas y los índices si no existen
def init_database():
    """
    Inicializa la base de datos con el esquema completo.
    Ejecutar al arrancar EV_Central por primera vez.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de usuarios (drivers)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            contraseña TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'driver',
            balance REAL DEFAULT 100.0,
            active INTEGER DEFAULT 1,
            created_at REAL DEFAULT (julianday('now'))
        )
    """)
    
    # Tabla de puntos de carga
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS charging_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cp_id TEXT UNIQUE NOT NULL,
            localizacion TEXT,
            estado TEXT DEFAULT 'available',
            max_kw REAL DEFAULT 22.0,
            tarifa_kwh REAL DEFAULT 0.30,
            last_maintenance REAL,
            active INTEGER DEFAULT 1
        )
    """)
    
    # Tabla de sesiones de carga
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS charging_sesiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            cp_id TEXT NOT NULL,
            correlacion_id TEXT,
            start_time REAL NOT NULL,
            end_time REAL,
            energia_kwh REAL DEFAULT 0.0,
            coste REAL DEFAULT 0.0,
            estado TEXT DEFAULT 'active',
            pago_estado TEXT DEFAULT 'pending',
            FOREIGN KEY(user_id) REFERENCES usuarios(id),
            FOREIGN KEY(cp_id) REFERENCES charging_points(cp_id)
        )
    """)
    
    # Tabla de log de eventos (opcional, para auditoría)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correlacion_id TEXT,
            mensaje_id TEXT,
            tipo_evento TEXT,
            component TEXT,
            detalles TEXT,
            timestamp REAL DEFAULT (julianday('now'))
        )
    """)
    
    # Crea índices para mejorar consultas
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sesiones_user ON charging_sesiones(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sesiones_cp ON charging_sesiones(cp_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sesiones_estado ON charging_sesiones(estado)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_correlacion ON event_log(correlacion_id)")
    
    conn.commit()
    conn.close()
    print(f"[DB] Database initialized at {DB_PATH}")

# Devuelve el hash de la contraseña
def contraseña_hash(password: str) -> str:
    """Genera hash SHA256 de una contraseña"""
    return hashlib.sha256(password.encode()).hexdigest()

# Inserta datos en la base de datos para probar
def seed_test_data():
    """
    Carga datos de prueba en la base de datos.
    Útil para desarrollo y testing.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Usuarios de prueba
    test_users = [
        ('driver1', 'pass123', 'driver1@ev.com', 'driver', 150.0),
        ('driver2', 'pass456', 'driver2@ev.com', 'driver', 200.0),
        ('driver3', 'pass789', 'driver3@ev.com', 'driver', 75.50),
        ('driver4', 'pass321', 'driver4@ev.com', 'driver', 300.0),
        ('driver5', 'pass654', 'driver5@ev.com', 'driver', 25.75),
        ('maria_garcia', 'maria2025', 'maria@gmail.com', 'driver', 180.0),
        ('juan_lopez', 'juan123', 'juan@hotmail.com', 'driver', 95.25),
        ('ana_martinez', 'ana456', 'ana@yahoo.com', 'driver', 220.0),
        ('pedro_sanchez', 'pedro789', 'pedro@outlook.com', 'driver', 45.0),
        ('laura_fernandez', 'laura321', 'laura@gmail.com', 'driver', 165.50),
        ('admin', 'admin123', 'admin@ev.com', 'admin', 0.0),
        ('operator1', 'oper123', 'operator1@ev.com', 'operator', 0.0),
        ('lbf19', 'lbf19', 'lbf19@ev.com', 'admin', 0.0),
    ]
    
    for nombre, password, email, role, balance in test_users:
        try:
            cursor.execute("""
                INSERT INTO usuarios (nombre, contraseña, email, role, balance)
                VALUES (?, ?, ?, ?, ?)
            """, (nombre, contraseña_hash(password), email, role, balance))
        except sqlite3.IntegrityError:
            pass  # Usuario ya existe
    
    # Puntos de carga de prueba
    test_cps = [
        ('CP_001', 'Campus Norte', 'available', 22.0, 0.30),
        ('CP_002', 'Campus Sur', 'available', 50.0, 0.35),
        ('CP_003', 'Biblioteca', 'available', 11.0, 0.25),
        ('CP_004', 'Estacionamiento Principal', 'available', 22.0, 0.28),
        ('CP_005', 'Edificio Deportes', 'available', 7.4, 0.22),
        ('CP_006', 'Centro Comercial Plaza', 'available', 43.0, 0.38),
        ('CP_007', 'Hospital San Juan', 'available', 50.0, 0.32),
        ('CP_008', 'Estación de Tren', 'available', 150.0, 0.45),
        ('CP_009', 'Aeropuerto Terminal 1', 'available', 120.0, 0.42),
        ('CP_010', 'Parking Residencial Sur', 'available', 11.0, 0.26),
    ]
    
    for cp_id, localizacion, estado, max_power, tariff in test_cps:
        try:
            cursor.execute("""
                INSERT INTO charging_points (cp_id, localizacion, estado, max_kw, tarifa_kwh)
                VALUES (?, ?, ?, ?, ?)
            """, (cp_id, localizacion, estado, max_power, tariff))
        except sqlite3.IntegrityError:
            pass  # CP ya existe
    
    # Sesiones históricas de prueba
    import random
    from datetime import datetime, timedelta
    
    # Generar sesiones completadas de los últimos 30 días
    base_time = datetime.now().timestamp()
    
    test_sesiones = [
        (1, 'CP_001', base_time - 86400*5, base_time - 86400*5 + 3600*2, 25.5, 'completed'),
        (1, 'CP_003', base_time - 86400*3, base_time - 86400*3 + 3600*1.5, 12.8, 'completed'),
        (1, 'CP_002', base_time - 86400*1, base_time - 86400*1 + 3600*3, 45.2, 'completed'),
        
        (2, 'CP_001', base_time - 86400*7, base_time - 86400*7 + 3600*2.5, 30.0, 'completed'),
        (2, 'CP_004', base_time - 86400*4, base_time - 86400*4 + 3600*1, 15.5, 'completed'),
        
        (6, 'CP_005', base_time - 86400*10, base_time - 86400*10 + 3600*4, 18.5, 'completed'),
        (6, 'CP_001', base_time - 86400*6, base_time - 86400*6 + 3600*2, 22.0, 'completed'),
        (6, 'CP_003', base_time - 86400*2, base_time - 86400*2 + 3600*1, 10.2, 'completed'),
        
        (7, 'CP_002', base_time - 86400*8, base_time - 86400*8 + 3600*3, 52.3, 'completed'),
        (7, 'CP_006', base_time - 86400*5, base_time - 86400*5 + 3600*2, 35.8, 'completed'),
        
        (8, 'CP_007', base_time - 86400*12, base_time - 86400*12 + 3600*1.5, 28.0, 'completed'),
        (8, 'CP_008', base_time - 86400*9, base_time - 86400*9 + 3600*0.5, 75.0, 'completed'),
        (8, 'CP_001', base_time - 86400*4, base_time - 86400*4 + 3600*2, 24.5, 'completed'),
        
        (9, 'CP_003', base_time - 86400*15, base_time - 86400*15 + 3600*3, 16.2, 'completed'),
        (9, 'CP_005', base_time - 86400*11, base_time - 86400*11 + 3600*4, 19.8, 'completed'),
        
        (10, 'CP_009', base_time - 86400*20, base_time - 86400*20 + 3600*1, 60.0, 'completed'),
        (10, 'CP_006', base_time - 86400*14, base_time - 86400*14 + 3600*2.5, 42.5, 'completed'),
        (10, 'CP_002', base_time - 86400*7, base_time - 86400*7 + 3600*3.5, 55.0, 'completed'),
    ]
    
    for user_id, cp_id, start_time, end_time, energia_kwh, estado in test_sesiones:
        try:
            cursor.execute("SELECT tarifa_kwh FROM charging_points WHERE cp_id = ?", (cp_id,))
            result = cursor.fetchone()
            tariff = result['tarifa_kwh'] if result else 0.30
            coste = energia_kwh * tariff
            
            cursor.execute("""
                INSERT INTO charging_sesiones (user_id, cp_id, start_time, end_time, energia_kwh, coste, estado, pago_estado)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'completed')
            """, (user_id, cp_id, start_time, end_time, energia_kwh, coste, estado))
        except Exception as e:
            pass  
    
    test_events = [
        ('corr_001', 'msg_001', 'AUTH', 'EV_Driver', '{"nombre": "driver1", "result": "success"}'),
        ('corr_002', 'msg_002', 'REQUEST_CHARGE', 'EV_Driver', '{"user": "driver1", "cp": "CP_001"}'),
        ('corr_003', 'msg_003', 'CHARGE_START', 'EV_CP_E', '{"cp_id": "CP_001", "sesion": 1}'),
        ('corr_004', 'msg_004', 'CHARGE_COMPLETE', 'EV_Central', '{"sesion": 1, "energia": 25.5}'),
        ('corr_005', 'msg_005', 'AUTH', 'EV_Driver', '{"nombre": "maria_garcia", "result": "success"}'),
    ]
    
    for corr_id, msg_id, tipo_evento, component, detalles in test_events:
        try:
            cursor.execute("""
                INSERT INTO event_log (correlacion_id, mensaje_id, tipo_evento, component, detalles)
                VALUES (?, ?, ?, ?, ?)
            """, (corr_id, msg_id, tipo_evento, component, detalles))
        except Exception:
            pass
    
    conn.commit()
    conn.close()
    print(f"[DB] Test data seeded successfully with extended data")

# Comprueba si existe un usuario con nombre, contraseña y active = 1
def autentificación_usuario(nombre: str, password: str) -> dict | None:
    """
    Autentica un usuario.
    Retorna dict con datos del usuario si es válido, None si no.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    contraseña = contraseña_hash(password)
    cursor.execute("""
        SELECT id, nombre, email, role, balance, active
        FROM usuarios
        WHERE nombre = ? AND contraseña = ? AND active = 1
    """, (nombre, contraseña))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row['id'],
            'nombre': row['nombre'],
            'email': row['email'],
            'role': row['role'],
            'balance': row['balance'],
            'active': row['active']
        }
    return None

# Recupera y devuelve el usuario por ID
def get_user_by_id(user_id: int) -> dict | None:
    """Obtiene datos de un usuario por ID"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, nombre, email, role, balance, active
        FROM usuarios
        WHERE id = ?
    """, (user_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

# Igual que la función anterior pero por nombre
def get_user_by_nombre(nombre: str) -> dict | None:
    """Obtiene datos de un usuario por nombre"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, nombre, email, role, balance, active
        FROM usuarios
        WHERE nombre = ?
    """, (nombre,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

# Alias para compatibilidad con código que usa 'username'
def get_user_by_username(username: str) -> dict | None:
    """Obtiene datos de un usuario por username (alias de get_user_by_nombre)"""
    return get_user_by_nombre(username)

# Recupera y devuelve el punto de carga por su cp_id
def get_charging_point(cp_id: str) -> dict | None:
    """Obtiene información de un punto de carga"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, cp_id, localizacion, estado, max_kw, tarifa_kwh, active
        FROM charging_points
        WHERE cp_id = ?
    """, (cp_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

# Actualiza el campo "estado" de charging_points buscando el punto de carga por su cp_id
def update_cp_estado(cp_id: str, estado: str):
    """Actualiza el estado de un punto de carga"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE charging_points
        SET estado = ?
        WHERE cp_id = ?
    """, (estado, cp_id))
    
    conn.commit()
    conn.close()

# Mirando el cp_id del punto de carga, i existe lo actualiza, si no existe lo crea
def register_or_update_charging_point(cp_id: str, localizacion: str, max_kw: float = 22.0, 
                                     tarifa_kwh: float = 0.30, estado: str = 'available'):
    """
    Registra un nuevo punto de carga o actualiza uno existente.
    Útil cuando los CP se conectan dinámicamente al sistema.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM charging_points WHERE cp_id = ?", (cp_id,))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute("""
            UPDATE charging_points
            SET estado = ?, localizacion = ?, max_kw = ?, tarifa_kwh = ?
            WHERE cp_id = ?
        """, (estado, localizacion, max_kw, tarifa_kwh, cp_id))
    else:
        cursor.execute("""
            INSERT INTO charging_points (cp_id, localizacion, estado, max_kw, tarifa_kwh)
            VALUES (?, ?, ?, ?, ?)
        """, (cp_id, localizacion, estado, max_kw, tarifa_kwh))
    
    conn.commit()
    conn.close()

# Devuelve lista de puntos de carga cuyo estado es 'available' o 'offline' y active = 1
def get_available_charging_points():
    """
    Obtiene lista de puntos de carga disponibles.
    Considera disponibles: 'available' y 'offline' (offline = listo para uso, solo desconectado)
    NO considera: 'charging' (en uso), 'fault' (con fallo), 'out_of_service' (fuera de servicio)
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT cp_id, localizacion, max_kw, tarifa_kwh
        FROM charging_points
        WHERE estado IN ('available', 'offline') AND active = 1
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# Devuelve todos los puntos de carga sin filtros
def get_all_charging_points():
    """Obtiene lista de todos los puntos de carga registrados"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT cp_id, localizacion, estado, max_kw, tarifa_kwh, active
        FROM charging_points
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# Actualiza el estado de un punto de carga e imprime un mensaje en caso de éxito o de fallo
def update_charging_point_status(cp_id: str, new_status: str) -> bool:
    """
    Actualiza el estado de un punto de carga.
    Estados válidos: available, reserved, charging, fault, out_of_service, offline
    Retorna True si se actualizó correctamente.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE charging_points
            SET estado = ?
            WHERE cp_id = ?
        """, (new_status, cp_id))
        
        conn.commit()
        success = cursor.rowcount > 0
        
        if success:
            print(f"[DB] OK CP {cp_id} status updated to '{new_status}'")
        else:
            print(f"[DB] ADVERTENCIA CP {cp_id} not found")
        
        return success
    except Exception as e:
        print(f"[DB] ERROR updating CP status: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# Actualiza todos los puntos de carga a 'offline'
def set_all_cps_status_offline() -> int:
    """Marca TODOS los puntos de carga registrados como 'offline'. Retorna filas afectadas."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Resetear TODOS los estados a offline al reiniciar Central
        # Marcar todas las CPs registradas (sin filtrar por active, para incluir todas)
        cursor.execute("""
            UPDATE charging_points
            SET estado = 'offline'
        """)
        conn.commit()
        affected = cursor.rowcount
        print(f"[DB] OK Reset {affected} CP(s) registrado(s) to offline")
        return affected
    except Exception as e:
        print(f"[DB] ERROR setting all CPs offline: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()

# Marca estado = 'charging' para CPs que tengan sesiones con estado = 'active'
def set_cps_with_active_sessions_to_charging() -> int:
    """Marca como 'charging' los CPs que tienen sesiones activas."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE charging_points
            SET estado = 'charging'
            WHERE cp_id IN (
                SELECT DISTINCT cp_id FROM charging_sesiones WHERE estado = 'active'
            )
        """)
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        print(f"[DB] ERROR setting CPs with active sessions to 'charging': {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()

# Selecciones los CPs que tienen sesiones activas, las actualiza con set end_time = 'now' y estado = 'terminated
# Si mark_cp_offline es True, pone el estado de esos CPs a 'offline'
def terminate_all_active_sessions(mark_cp_offline: bool = True) -> tuple[int, int]:
    """Termina todas las sesiones activas y opcionalmente pone sus CPs en 'offline'.

    Retorna (sesiones_terminadas, cps_actualizados)
    """
    from datetime import datetime as _dt

    conn = get_connection()
    cursor = conn.cursor()
    try:
        now_ts = _dt.now().timestamp()

        # Obtener CPs afectados antes de cerrar sesiones
        cursor.execute("""
            SELECT DISTINCT cp_id FROM charging_sesiones WHERE estado = 'active'
        """)
        cp_rows = [r[0] for r in cursor.fetchall()]

        # Terminar sesiones activas sin cobrar ni modificar balances
        cursor.execute("""
            UPDATE charging_sesiones
            SET end_time = ?, estado = 'terminated'
            WHERE estado = 'active'
        """, (now_ts,))
        sessions_closed = cursor.rowcount

        cps_updated = 0
        if mark_cp_offline and cp_rows:
            cursor.execute(
                f"""
                UPDATE charging_points
                SET estado = 'offline'
                WHERE cp_id IN ({','.join(['?'] * len(cp_rows))})
                """,
                cp_rows,
            )
            cps_updated = cursor.rowcount

        conn.commit()
        if sessions_closed or cps_updated:
            print(f"[DB] INFO Terminated active sessions: {sessions_closed}, CPs set offline: {cps_updated}")
        return sessions_closed, cps_updated
    except Exception as e:
        print(f"[DB] ERROR terminating active sessions on shutdown: {e}")
        conn.rollback()
        return 0, 0
    finally:
        conn.close()


# === Funciones de reserva de puntos de carga ===

def find_and_reserve_available_cp(max_attempts: int = 10) -> str:
    """
    Busca y reserva atomicamente el primer CP disponible.
    Retorna el cp_id reservado, o None si no hay CPs disponibles.
    Esta operación es completamente atómica para evitar condiciones de carrera.
    """
    for attempt in range(max_attempts):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Buscar un CP disponible que NO haya sido reservado
            cursor.execute("""
                SELECT cp_id FROM charging_points
                WHERE estado IN ('available', 'offline')
                AND active = 1
                AND cp_id NOT IN (
                    SELECT DISTINCT cp_id FROM charging_sesiones WHERE estado = 'active'
                )
                ORDER BY cp_id
                LIMIT 1
            """)
            
            result = cursor.fetchone()
            if not result:
                print(f"[DB] ADVERTENCIA No available CPs to reserve")
                return None
            
            cp_id = result[0]
            
            # Intentar reservar atomicamente (solo si sigue disponible)
            cursor.execute("""
                UPDATE charging_points
                SET estado = 'reserved'
                WHERE cp_id = ? 
                AND estado IN ('available', 'offline')
                AND active = 1
            """, (cp_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                print(f"[DB] OK CP {cp_id} found and reserved atomically")
                return cp_id
            else:
                # Otro proceso lo reservó primero, intentar con el siguiente
                print(f"[DB] ADVERTENCIA CP {cp_id} was taken, retry {attempt + 1}/{max_attempts}")
                conn.rollback()
                continue
                
        except Exception as e:
            print(f"[DB] ERROR finding/reserving CP: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    # Si llegamos aquí, se agotaron los intentos
    print(f"[DB] ERROR Failed to reserve CP after {max_attempts} attempts")
    return None

def reserve_charging_point(cp_id: str, timeout_seconds: int = 5) -> bool:
    """
    Intenta reservar un punto de carga de forma atómica.
    Solo reserva si estado actual es 'available' u 'offline'.
    Retorna True si se pudo reservar.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Actualizar estado atomicamente solo si está disponible
        cursor.execute("""
            UPDATE charging_points
            SET estado = 'reserved'
            WHERE cp_id = ? 
            AND estado IN ('available', 'offline')
            AND active = 1
        """, (cp_id,))
        
        success = cursor.rowcount > 0
        if success:
            conn.commit()
            print(f"[DB] OK CP {cp_id} reserved successfully")
        else:
            print(f"[DB] ADVERTENCIA CP {cp_id} could not be reserved (unavailable)")
        return success
            
    except Exception as e:
        print(f"[DB] ERROR reserving CP: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def release_charging_point(cp_id: str, set_estado: str = 'available') -> bool:
    """
    Libera un punto de carga reservado.
    Si set_estado='available': vuelve a disponible
    Si set_estado='offline': vuelve a desconectado
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE charging_points
            SET estado = ?
            WHERE cp_id = ? AND estado = 'reserved'
        """, (set_estado, cp_id))
        
        success = cursor.rowcount > 0
        if success:
            conn.commit()
            print(f"[DB] OK CP {cp_id} released to {set_estado}")
        else:
            print(f"[DB] ADVERTENCIA CP {cp_id} was not in reserved state")
        return success
            
    except Exception as e:
        print(f"[DB] ERROR releasing CP: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# === Funciones de sesiones de carga ===


# Crea e inserta una nueva fila en charging_sessions con estado = 'active' y start_time actual
# Y cambia el estado del CP a 'charging'
def create_charging_session(user_id: int, cp_id: str, correlation_id: str = None) -> int:
    """
    Crea una nueva sesión de carga.
    Retorna el ID de la sesión creada.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    start_time = datetime.now().timestamp()
    
    cursor.execute("""
        INSERT INTO charging_sesiones (user_id, cp_id, correlacion_id, start_time, estado)
        VALUES (?, ?, ?, ?, 'active')
    """, (user_id, cp_id, correlation_id, start_time))
    
    sesion_id = cursor.lastrowid
    
    cursor.execute("""
        UPDATE charging_points
        SET estado = 'charging'
        WHERE cp_id = ?
    """, (cp_id,))
    
    conn.commit()
    conn.close()
    
    return sesion_id


# Busca la sesión activa con ese id, calcula el coste según coste = energia_kwh * tarifa_kwh del CP
# Actualiza la sesión con end_time actual, energia_kwh, coste y estado = 'completed'
# Resta el coste del balance del usuario y pone el estado = 'available' y devuelve un resumen de la carga
def end_charging_sesion(sesion_id: int, energia_kwh: float) -> dict:
    """
    Finaliza una sesión de carga, calcula el costo y actualiza el balance del usuario.
    Retorna dict con sesion_id, coste, y updated_balance.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT s.id, s.user_id, s.cp_id, s.start_time, cp.tarifa_kwh
        FROM charging_sesiones s
        JOIN charging_points cp ON s.cp_id = cp.cp_id
        WHERE s.id = ? AND s.estado = 'active'
    """, (sesion_id,))
    
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    
    sesion = dict(row)
    end_time = datetime.now().timestamp()
    coste = energia_kwh * sesion['tarifa_kwh']
    
    cursor.execute("""
        UPDATE charging_sesiones
        SET end_time = ?, energia_kwh = ?, coste = ?, estado = 'completed'
        WHERE id = ?
    """, (end_time, energia_kwh, coste, sesion_id))
    
    cursor.execute("""
        UPDATE usuarios
        SET balance = balance - ?
        WHERE id = ?
    """, (coste, sesion['user_id']))
    
    cursor.execute("""
        UPDATE charging_points
        SET estado = 'available'
        WHERE cp_id = ?
    """, (sesion['cp_id'],))
    
    cursor.execute("SELECT balance FROM usuarios WHERE id = ?", (sesion['user_id'],))
    new_balance = cursor.fetchone()['balance']
    
    conn.commit()
    conn.close()
    
    return {
        'sesion_id': sesion_id,
        'coste': coste,
        'energia_kwh': energia_kwh,
        'updated_balance': new_balance
    }


# Devuelve la sesión activa más reciente para un usuario, si es que existe.
def get_active_sesion_for_user(user_id: int) -> dict | None:
    """Obtiene la sesión activa de un usuario, si existe"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, user_id, cp_id, correlacion_id, start_time, estado
        FROM charging_sesiones
        WHERE user_id = ? AND estado = 'active'
        ORDER BY start_time DESC
        LIMIT 1
    """, (user_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

# Devuelve el historial de sesiones de un usuario ordenadas por start_time descendente, limitado a 'limit' resultados.
def get_user_sesiones(user_id: int, limit: int = 10):
    """Obtiene el historial de sesiones de un usuario"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, cp_id, start_time, end_time, energia_kwh, coste, estado
        FROM charging_sesiones
        WHERE user_id = ?
        ORDER BY start_time DESC
        LIMIT ?
    """, (user_id, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# Crea e inserta una nueva fila en event_log con 'detalles_json', si es que tuviera.
def log_event(correlacion_id: str, mensaje_id: str, tipo_evento: str, 
              component: str, detalles: dict = None):
    """Registra un evento en el log de auditoría"""
    conn = get_connection()
    cursor = conn.cursor()
    
    detalles_json = json.dumps(detalles) if detalles else None
    
    cursor.execute("""
        INSERT INTO event_log (correlacion_id, mensaje_id, tipo_evento, component, detalles)
        VALUES (?, ?, ?, ?, ?)
    """, (correlacion_id, mensaje_id, tipo_evento, component, detalles_json))
    
    conn.commit()
    conn.close()


# Recupera todos los usuarios y devuelte una lista con sus datos.
def get_all_users():
    """Obtiene todos los usuarios de la base de datos"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios")
    rows = cursor.fetchall()
    conn.close()
    
    usuarios = []
    for row in rows:
        usuarios.append({
            'id': row['id'],
            'nombre': row['nombre'],
            'email': row['email'],
            'role': row['role'],
            'balance': row['balance'],
            'is_active': bool(row['active']),
            'created_at': row['created_at']
        })
    return usuarios

# Recupera sesiones que no tienen end_time e incluye en cada sesión datos del usuario.
def get_sesiones_actividad():
    """Obtiene todas las sesiones activas (sin end_time)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*, u.nombre 
        FROM charging_sesiones s
        JOIN usuarios u ON s.user_id = u.id
        WHERE s.end_time IS NULL
        ORDER BY s.start_time DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    sesiones = []
    for row in rows:
        sesiones.append({
            'id': row['id'],
            'user_id': row['user_id'],
            'nombre': row['nombre'],
            'cp_id': row['cp_id'],
            'start_time': row['start_time'],
            'correlacion_id': row['correlacion_id']
        })
    return sesiones

# Dada una fecha específica en date devuelve las sesiones completadas en ese rango de fechas.
def get_sesiones_by_date(date):
    """Obtiene todas las sesiones completadas en una fecha específica"""
    conn = get_connection()
    cursor = conn.cursor()
    
    start_of_day = datetime.combine(date, datetime.min.time()).timestamp()
    end_of_day = datetime.combine(date, datetime.max.time()).timestamp()
    
    cursor.execute("""
        SELECT * FROM charging_sesiones
        WHERE start_time >= ? AND start_time <= ?
        AND end_time IS NOT NULL
    """, (start_of_day, end_of_day,))
    
    rows = cursor.fetchall()
    conn.close()
    
    sesiones = []
    for row in rows:
        sesiones.append({
            'id': row['id'],
            'user_id': row['user_id'],
            'cp_id': row['cp_id'],
            'start_time': row['start_time'],
            'end_time': row['end_time'],
            'energia_kwh': row['energia_kwh'],
            'total_coste': row['coste'] 
        })
    return sesiones

# Recupera un CP por su cp_id y añade atributos auxiliares como power_output y tariff.
def get_charging_point_by_id(cp_id: str):
    """Obtiene un punto de carga por su ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, cp_id, localizacion, estado, 
               max_kw, tarifa_kwh
        FROM charging_points 
        WHERE cp_id = ?
    """, (cp_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        d = dict(row)
        d['power_output'] = d.get('max_kw')
        d['tariff'] = d.get('tarifa_kwh')
        return d
    return None

#!/usr/bin/env python3
"""
Script para consultar y visualizar datos de la base de datos EV Charging System
"""

# Imprime una línea repetida
def print_separator(char="=", length=80):
    print(char * length)

# Imrpime un separados, el título y otro separador.
def print_header(title):
    print_separator()
    print(f"  {title}")
    print_separator()

# Imprime una tabla con todos los usuarios registrados.
def show_all_users():
    """Muestra todos los usuarios registrados"""
    print_header("USUARIOS REGISTRADOS")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, email, role, balance, active FROM usuarios ORDER BY role, nombre")
    users = cursor.fetchall()
    conn.close()
    
    print(f"{'ID':<5} {'Nombre':<20} {'Email':<30} {'Role':<10} {'Balance':>10} {'Active':<7}")
    print("-" * 80)
    for user in users:
        active_str = "SI" if user['active'] else "NO"
        print(f"{user['id']:<5} {user['nombre']:<20} {user['email']:<30} {user['role']:<10} €{user['balance']:>8.2f} {active_str:<7}")
    print(f"\nTotal usuarios: {len(users)}")

# Muestra todos los puntos de carga.
def show_all_charging_points():
    """Muestra todos los puntos de carga"""
    print_header("PUNTOS DE CARGA")
    cps = get_all_charging_points()
    
    print(f"{'CP ID':<10} {'Localizacion':<35} {'Estado':<12} {'Potencia':>8} {'Tarifa':>10}")
    print("-" * 80)
    for cp in cps:
        estado_emoji = "available" if cp['estado'] == 'available' else "charging" if cp['estado'] == 'charging' else "offline"
        print(f"{cp['cp_id']:<10} {cp['localizacion']:<35} {estado_emoji} {cp['estado']:<10} {cp['max_kw']:>6.1f}kW €{cp['tarifa_kwh']:>5.2f}/kWh")
    print(f"\nTotal puntos de carga: {len(cps)}")

# Muestra las últimas 20 sesiones con nombre de usuario, hora, energía, cote y estado.
def show_all_sessions():
    """Muestra todas las sesiones de carga"""
    print_header("SESIONES DE CARGA (Últimas 20)")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, u.nombre, s.cp_id, s.start_time, s.end_time, 
               s.energia_kwh, s.coste, s.estado
        FROM charging_sesiones s
        JOIN usuarios u ON s.user_id = u.id
        ORDER BY s.start_time DESC
        LIMIT 20
    """)
    sessions = cursor.fetchall()
    conn.close()
    
    print(f"{'ID':<5} {'User':<18} {'CP':<10} {'Start':<20} {'Energy':>10} {'Cost':>10} {'estado':<10}")
    print("-" * 95)
    for session in sessions:
        start_dt = datetime.fromtimestamp(session['start_time']).strftime('%Y-%m-%d %H:%M')
        energy = session['energia_kwh'] if session['energia_kwh'] else 0
        cost = session['coste'] if session['coste'] else 0
        estado_emoji = "COMPLETADA" if session['estado'] == 'completed' else "PENDIENTE"
        print(f"{session['id']:<5} {session['nombre']:<18} {session['cp_id']:<10} {start_dt:<20} {energy:>8.2f}kWh €{cost:>7.2f} {estado_emoji} {session['estado']:<8}")
    print(f"\nTotal sesiones mostradas: {len(sessions)}")

# Muestra el balance y las últimas sesiones de un usuario específico en función de su nombre..
def show_user_history(nombre):
    """Muestra el historial de un usuario específico"""
    user = get_user_by_nombre(nombre)
    if not user:
        print(f"ERROR Usuario '{nombre}' no encontrado")
        return
    
    print_header(f"HISTORIAL DE {nombre.upper()}")
    print(f"Balance actual: €{user['balance']:.2f}")
    print()
    
    sessions = get_user_sesiones(user['id'], limit=10)
    if not sessions:
        print("No hay sesiones registradas para este usuario")
        return
    
    print(f"{'ID':<5} {'CP':<10} {'Inicio':<20} {'Fin':<20} {'Energía':>10} {'Costo':>10}")
    print("-" * 80)
    total_energy = 0
    total_cost = 0
    for session in sessions:
        start_dt = datetime.fromtimestamp(session['start_time']).strftime('%Y-%m-%d %H:%M')
        end_str = "En curso" if not session['end_time'] else datetime.fromtimestamp(session['end_time']).strftime('%Y-%m-%d %H:%M')
        energy = session['energia_kwh'] if session.get('energia_kwh') else 0
        cost = session['coste'] if session.get('coste') else 0
        print(f"{session['id']:<5} {session['cp_id']:<10} {start_dt:<20} {end_str:<20} {energy:>8.2f}kWh €{cost:>7.2f}")
        total_energy += energy
        total_cost += cost
    
    print("-" * 80)
    print(f"{'TOTAL':<57} {total_energy:>8.2f}kWh €{total_cost:>7.2f}")

# Muestra estad´sticas generales que hay en el sistema como número de usuarios, puntos de carga, etc.
def show_statistics():
    """Muestra estadísticas generales del sistema"""
    print_header("ESTADÍSTICAS DEL SISTEMA")
    conn = get_connection()
    cursor = conn.cursor()
    
    # Usuarios
    cursor.execute("SELECT COUNT(*) as total FROM usuarios WHERE role='driver'")
    total_drivers = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM usuarios WHERE role='driver' AND active=1")
    active_drivers = cursor.fetchone()['total']
    
    # Puntos de carga
    cursor.execute("SELECT COUNT(*) as total FROM charging_points")
    total_cps = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM charging_points WHERE estado='available'")
    available_cps = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM charging_points WHERE estado='charging'")
    charging_cps = cursor.fetchone()['total']
    
    # Sesiones
    cursor.execute("SELECT COUNT(*) as total FROM charging_sesiones")
    total_sessions = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM charging_sesiones WHERE estado='active'")
    active_sessions = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM charging_sesiones WHERE estado='completed'")
    completed_sessions = cursor.fetchone()['total']
    
    # Energía y costos
    cursor.execute("SELECT SUM(energia_kwh) as total FROM charging_sesiones WHERE estado='completed'")
    total_energy = cursor.fetchone()['total'] or 0
    
    cursor.execute("SELECT SUM(coste) as total FROM charging_sesiones WHERE estado='completed'")
    total_revenue = cursor.fetchone()['total'] or 0
    
    cursor.execute("SELECT AVG(energia_kwh) as avg FROM charging_sesiones WHERE estado='completed'")
    avg_energy = cursor.fetchone()['avg'] or 0
    
    # Top usuarios
    cursor.execute("""
        SELECT u.nombre, COUNT(s.id) as sessions, SUM(s.energia_kwh) as total_energy, SUM(s.coste) as total_cost
        FROM usuarios u
        LEFT JOIN charging_sesiones s ON u.id = s.user_id AND s.estado='completed'
        WHERE u.role='driver'
        GROUP BY u.id
        ORDER BY total_cost DESC
        LIMIT 5
    """)
    top_users = cursor.fetchall()
    
    conn.close()
    
    # Mostrar estadísticas
    print("\nUSUARIOS")
    print(f"  Total drivers: {total_drivers}")
    print(f"  Drivers activos: {active_drivers}")
    
    print("\nPUNTOS DE CARGA")
    print(f"  Total: {total_cps}")
    print(f"  Disponibles: {available_cps} (available)")
    print(f"  En uso: {charging_cps} (charging)")
    
    print("\nSESIONES DE CARGA")
    print(f"  Total: {total_sessions}")
    print(f"  Activas: {active_sessions}")
    print(f"  Completadas: {completed_sessions}")
    
    print("\nENERGIA Y COSTOS")
    print(f"  Energía total despachada: {total_energy:.2f} kWh")
    print(f"  Energía promedio por sesión: {avg_energy:.2f} kWh")
    print(f"  Ingresos totales: €{total_revenue:.2f}")
    
    print("\nTOP 5 USUARIOS (por gasto)")
    print(f"  {'nombre':<20} {'Sesiones':>10} {'Energía':>12} {'Total Gastado':>15}")
    print("  " + "-" * 60)
    for user in top_users:
        sessions = user['sessions'] or 0
        energy = user['total_energy'] or 0
        cost = user['total_cost'] or 0
        print(f"  {user['nombre']:<20} {sessions:>10} {energy:>10.2f}kWh €{cost:>12.2f}")

# Es el mení interactivo de consola que permite ver usuarios, CPs, sesiones, historial, estadísticas o salir.
def main_menu():
    """Menú interactivo"""
    while True:
        print("\n" + "=" * 80)
        print("  EV CHARGING SYSTEM - CONSULTA DE BASE DE DATOS")
        print("=" * 80)
        print("\n  1. Ver todos los usuarios")
        print("  2. Ver todos los puntos de carga")
        print("  3. Ver sesiones de carga")
        print("  4. Ver historial de usuario")
        print("  5. Ver estadísticas del sistema")
        print("  6. Salir")
        
        choice = input("\n  Selecciona una opción (1-6): ").strip()
        
        if choice == '1':
            print()
            show_all_users()
        elif choice == '2':
            print()
            show_all_charging_points()
        elif choice == '3':
            print()
            show_all_sessions()
        elif choice == '4':
            nombre = input("\n  Introduce el nombre: ").strip()
            print()
            show_user_history(nombre)
        elif choice == '5':
            print()
            show_statistics()
        elif choice == '6':
            print("\n  Hasta luego!")
            break
        else:
            print("\n  ERROR Opcion no valida")
        
        input("\n  Presiona ENTER para continuar...")
    # Inicializa la BD, realiza unas pruebas e imprime un resumen.
    def run_init_db():
        """Inicializa la base de datos y muestra un resumen (migración del init_db.py)."""
        print("=" * 60)
        print("  Inicializando Base de Datos - EV Charging System")
        print("=" * 60)

        # Inicializar esquema y datos de prueba
        init_database()
        seed_test_data()

        # Mostrar resúmenes
        print("\n" + "=" * 60)
        print("  USUARIOS DE PRUEBA CREADOS")
        print("=" * 60)
        print("  Username: driver1         | Password: pass123   | Balance: €150.00")
        print("  Username: driver2         | Password: pass456   | Balance: €200.00")
        print("  Username: driver3         | Password: pass789   | Balance: €75.50")
        print("  Username: driver4         | Password: pass321   | Balance: €300.00")
        print("  Username: driver5         | Password: pass654   | Balance: €25.75")

        print("\n" + "=" * 60)
        print("  PUNTOS DE CARGA REGISTRADOS")
        print("=" * 60)
        cps = get_all_charging_points()
        for cp in cps:
            local = cp.get('localizacion') or ''
            print(f"  {cp['cp_id']:8s} - {local[:30]:30s} - {cp.get('max_kw', 0):6.1f}kW - €{cp.get('tarifa_kwh', 0):.2f}/kWh")

        # Estadísticas
        print("\n" + "=" * 60)
        print("  ESTADÍSTICAS DEL SISTEMA")
        print("=" * 60)
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM usuarios WHERE role='driver'")
        total_drivers = cursor.fetchone()['total']
        print(f"  Total drivers: {total_drivers}")

        cursor.execute("SELECT COUNT(*) as total FROM charging_points")
        total_cps = cursor.fetchone()['total']
        print(f"  Total puntos de carga: {total_cps}")

        cursor.execute("SELECT COUNT(*) as total FROM charging_sesiones WHERE estado='completed'")
        total_sessions = cursor.fetchone()['total']
        print(f"  Sesiones completadas: {total_sessions}")

        cursor.execute("SELECT SUM(energia_kwh) as total FROM charging_sesiones WHERE estado='completed'")
        total_energy = cursor.fetchone()['total'] or 0
        print(f"  Energía total despachada: {total_energy:.2f} kWh")

        cursor.execute("SELECT SUM(coste) as total FROM charging_sesiones WHERE estado='completed'")
        total_revenue = cursor.fetchone()['total'] or 0
        print(f"  Ingresos totales: €{total_revenue:.2f}")

        conn.close()

        print("\n" + "=" * 60)
        print("  OK Base de datos inicializada correctamente")
        print(f"  Ubicacion: {DB_PATH}")
        print("=" * 60)
        print("\n  Puedes ahora ejecutar EV_Central.py")


    if __name__ == "__main__":
        # Si se pasa argumento 'init', inicializar la BD; en caso contrario mostrar menú interactivo
        if len(sys.argv) > 1 and sys.argv[1] in ("init", "--init", "setup"):
            run_init_db()
        else:
            print("\nEV Charging System - Consulta de Base de Datos")
            print(f"Base de datos: {DB_PATH}")
        
            # Verificar si existe la BD
            if not DB_PATH.exists():
                print("\nERROR La base de datos no existe. Ejecuta 'python database.py init' primero.")
            else:
                main_menu()

# get:charging_point_by_id y get_charging_point.
# En esencia, ambas funciones obtienen la misma información base pero la presentan de forma diferente. 
# Parece haber cierta duplicación de código que podría optimizarse - una función podría llamar a la otra y solo 
# transformar el formato si es necesario.
