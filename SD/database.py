"""
Database module for EV Charging System
SQLite database with users, charging points, sessions, and event logs
"""
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
import json

# Ruta de la base de datos (en la carpeta SD)
DB_PATH = Path(__file__).parent / "ev_charging.db"


def get_connection():
    """Obtiene una conexión a la base de datos"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permite acceder a columnas por nombre
    return conn


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
            nombre_completo TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            rol TEXT DEFAULT 'driver',
            saldo REAL DEFAULT 100.0,
            activo INTEGER DEFAULT 1,
            created_at REAL DEFAULT (julianday('now'))
        )
    """)
    
    # Tabla de puntos de carga
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS charging_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cp_id TEXT UNIQUE NOT NULL,
            location TEXT,
            status TEXT DEFAULT 'available',
            max_power_kw REAL DEFAULT 22.0,
            tariff_per_kwh REAL DEFAULT 0.30,
            last_maintenance REAL,
            active INTEGER DEFAULT 1
        )
    """)
    
    # Tabla de sesiones de carga
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS charging_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            cp_id TEXT NOT NULL,
            correlation_id TEXT,
            start_time REAL NOT NULL,
            end_time REAL,
            energy_kwh REAL DEFAULT 0.0,
            cost REAL DEFAULT 0.0,
            status TEXT DEFAULT 'active',
            payment_status TEXT DEFAULT 'pending',
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(cp_id) REFERENCES charging_points(cp_id)
        )
    """)
    
    # Tabla de log de eventos (opcional, para auditoría)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correlation_id TEXT,
            message_id TEXT,
            event_type TEXT,
            component TEXT,
            details TEXT,
            timestamp REAL DEFAULT (julianday('now'))
        )
    """)
    
    # Índices para mejorar rendimiento
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON charging_sessions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_cp ON charging_sessions(cp_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON charging_sessions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_correlation ON event_log(correlation_id)")
    
    conn.commit()
    conn.close()
    print(f"[DB] Database initialized at {DB_PATH}")


def hash_password(password: str) -> str:
    """Genera hash SHA256 de una contraseña"""
    return hashlib.sha256(password.encode()).hexdigest()


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
        ('admin', 'admin123', 'admin@ev.com', 'admin', 0.0),
    ]
    
    for username, password, email, role, balance in test_users:
        try:
            cursor.execute("""
                INSERT INTO users (username, password_hash, email, role, balance)
                VALUES (?, ?, ?, ?, ?)
            """, (username, hash_password(password), email, role, balance))
        except sqlite3.IntegrityError:
            pass  # Usuario ya existe
    
    # Puntos de carga de prueba
    test_cps = [
        ('CP_001', 'Campus Norte', 'available', 22.0, 0.30),
        ('CP_002', 'Campus Sur', 'available', 50.0, 0.35),
        ('CP_003', 'Biblioteca', 'available', 11.0, 0.25),
    ]
    
    for cp_id, location, status, max_power, tariff in test_cps:
        try:
            cursor.execute("""
                INSERT INTO charging_points (cp_id, location, status, max_power_kw, tariff_per_kwh)
                VALUES (?, ?, ?, ?, ?)
            """, (cp_id, location, status, max_power, tariff))
        except sqlite3.IntegrityError:
            pass  # CP ya existe
    
    conn.commit()
    conn.close()
    print(f"[DB] Test data seeded successfully")


# === Funciones de autenticación ===

def authenticate_user(username: str, password: str) -> dict | None:
    """
    Autentica un usuario.
    Retorna dict con datos del usuario si es válido, None si no.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    password_hash = hash_password(password)
    cursor.execute("""
        SELECT id, username, email, role, balance, active
        FROM users
        WHERE username = ? AND password_hash = ? AND active = 1
    """, (username, password_hash))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row['id'],
            'username': row['username'],
            'email': row['email'],
            'role': row['role'],
            'balance': row['balance'],
            'active': row['active']
        }
    return None


def get_user_by_id(user_id: int) -> dict | None:
    """Obtiene datos de un usuario por ID"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, username, email, role, balance, active
        FROM users
        WHERE id = ?
    """, (user_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def get_user_by_username(username: str) -> dict | None:
    """Obtiene datos de un usuario por username"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, username, email, role, balance, active
        FROM users
        WHERE username = ?
    """, (username,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


# === Funciones de puntos de carga ===

def get_charging_point(cp_id: str) -> dict | None:
    """Obtiene información de un punto de carga"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, cp_id, location, status, max_power_kw, tariff_per_kwh, active
        FROM charging_points
        WHERE cp_id = ?
    """, (cp_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def update_cp_status(cp_id: str, status: str):
    """Actualiza el estado de un punto de carga"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE charging_points
        SET status = ?
        WHERE cp_id = ?
    """, (status, cp_id))
    
    conn.commit()
    conn.close()


def get_available_charging_points():
    """Obtiene lista de puntos de carga disponibles"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT cp_id, location, max_power_kw, tariff_per_kwh
        FROM charging_points
        WHERE status = 'available' AND active = 1
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


# === Funciones de sesiones de carga ===

def create_charging_session(user_id: int, cp_id: str, correlation_id: str = None) -> int:
    """
    Crea una nueva sesión de carga.
    Retorna el ID de la sesión creada.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    start_time = datetime.now().timestamp()
    
    cursor.execute("""
        INSERT INTO charging_sessions (user_id, cp_id, correlation_id, start_time, status)
        VALUES (?, ?, ?, ?, 'active')
    """, (user_id, cp_id, correlation_id, start_time))
    
    session_id = cursor.lastrowid
    
    # Marcar el CP como ocupado
    cursor.execute("""
        UPDATE charging_points
        SET status = 'charging'
        WHERE cp_id = ?
    """, (cp_id,))
    
    conn.commit()
    conn.close()
    
    return session_id


def end_charging_session(session_id: int, energy_kwh: float) -> dict:
    """
    Finaliza una sesión de carga, calcula el costo y actualiza el balance del usuario.
    Retorna dict con session_id, cost, y updated_balance.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Obtener datos de la sesión
    cursor.execute("""
        SELECT s.id, s.user_id, s.cp_id, s.start_time, cp.tariff_per_kwh
        FROM charging_sessions s
        JOIN charging_points cp ON s.cp_id = cp.cp_id
        WHERE s.id = ? AND s.status = 'active'
    """, (session_id,))
    
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    
    session = dict(row)
    end_time = datetime.now().timestamp()
    cost = energy_kwh * session['tariff_per_kwh']
    
    # Actualizar sesión
    cursor.execute("""
        UPDATE charging_sessions
        SET end_time = ?, energy_kwh = ?, cost = ?, status = 'completed'
        WHERE id = ?
    """, (end_time, energy_kwh, cost, session_id))
    
    # Descontar del balance del usuario
    cursor.execute("""
        UPDATE users
        SET balance = balance - ?
        WHERE id = ?
    """, (cost, session['user_id']))
    
    # Liberar el punto de carga
    cursor.execute("""
        UPDATE charging_points
        SET status = 'available'
        WHERE cp_id = ?
    """, (session['cp_id'],))
    
    # Obtener balance actualizado
    cursor.execute("SELECT balance FROM users WHERE id = ?", (session['user_id'],))
    new_balance = cursor.fetchone()['balance']
    
    conn.commit()
    conn.close()
    
    return {
        'session_id': session_id,
        'cost': cost,
        'energy_kwh': energy_kwh,
        'updated_balance': new_balance
    }


def get_active_session_for_user(user_id: int) -> dict | None:
    """Obtiene la sesión activa de un usuario, si existe"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, user_id, cp_id, correlation_id, start_time, status
        FROM charging_sessions
        WHERE user_id = ? AND status = 'active'
        ORDER BY start_time DESC
        LIMIT 1
    """, (user_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def get_user_sessions(user_id: int, limit: int = 10):
    """Obtiene el historial de sesiones de un usuario"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, cp_id, start_time, end_time, energy_kwh, cost, status
        FROM charging_sessions
        WHERE user_id = ?
        ORDER BY start_time DESC
        LIMIT ?
    """, (user_id, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


# === Funciones de log de eventos ===

def log_event(correlation_id: str, message_id: str, event_type: str, 
              component: str, details: dict = None):
    """Registra un evento en el log de auditoría"""
    conn = get_connection()
    cursor = conn.cursor()
    
    details_json = json.dumps(details) if details else None
    
    cursor.execute("""
        INSERT INTO event_log (correlation_id, message_id, event_type, component, details)
        VALUES (?, ?, ?, ?, ?)
    """, (correlation_id, message_id, event_type, component, details_json))
    
    conn.commit()
    conn.close()


if __name__ == "__main__":
    print("=== Inicializando base de datos EV Charging ===")
    init_database()
    seed_test_data()
    
    print("\n=== Usuarios de prueba ===")
    print("username: driver1, password: pass123, balance: 150.0")
    print("username: driver2, password: pass456, balance: 200.0")
    print("username: admin, password: admin123")
    
    print("\n=== Puntos de carga disponibles ===")
    cps = get_available_charging_points()
    for cp in cps:
        print(f"  {cp['cp_id']} - {cp['location']} - {cp['max_power_kw']}kW - €{cp['tariff_per_kwh']}/kWh")
    
    print(f"\n✅ Base de datos lista en: {DB_PATH}")
