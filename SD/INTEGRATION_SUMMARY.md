# ✅ Integración Completada - Base de Datos con EV_Central

## 📊 Resumen de la Integración

La base de datos SQLite (`database.py`) ha sido **completamente integrada** con el sistema EV_Central.

## 🔗 Funcionalidades Integradas

### 1. Autenticación de Usuarios
**Ubicación**: `EV_Central.py` línea 124  
**Función BD**: `db.authenticate_user(username, password)`

```python
user = db.authenticate_user(username.strip(), password.strip())
if user:
    self.authenticated_users[addr] = user
```

**Qué hace**:
- Verifica credenciales con hash SHA256
- Carga información del usuario (id, balance, role)
- Mantiene sesión autenticada en memoria

### 2. Verificación de Balance
**Ubicación**: `EV_Central.py` línea 156  
**Función BD**: Lee `user['balance']`

```python
if user['balance'] < 5.0:
    return f"Central: INSUFFICIENT_BALANCE balance={user['balance']:.2f}"
```

**Qué hace**:
- Verifica que el usuario tenga créditos suficientes (mínimo €5)
- Rechaza solicitudes si no hay fondos

### 3. Búsqueda de Puntos de Carga Disponibles
**Ubicación**: `EV_Central.py` línea 160  
**Función BD**: `db.get_available_charging_points()`

```python
available_cps = db.get_available_charging_points()
if not available_cps:
    return "Central: NO_CP_AVAILABLE"
cp = available_cps[0]  # Asignar primer CP disponible
```

**Qué hace**:
- Consulta en BD los CPs con `status='available'`
- Retorna lista con ubicación, potencia y tarifa

### 4. Creación de Sesión de Carga
**Ubicación**: `EV_Central.py` línea 172  
**Función BD**: `db.create_charging_session(user_id, cp_id, correlation_id)`

```python
session_id = db.create_charging_session(user['id'], cp['cp_id'], corr_id)
print(f"[CENTRAL] Created session {session_id} for user '{user['username']}'")
```

**Qué hace**:
- Inserta nueva fila en tabla `charging_sessions`
- Marca CP como ocupado (`status='charging'`)
- Guarda correlation_id para trazabilidad
- Retorna session_id

### 5. Finalización de Sesión con Cálculo de Costo
**Ubicación**: `EV_Central.py` línea 179  
**Función BD**: `db.end_charging_session(session_id, energy_kwh)`

```python
result = db.end_charging_session(active_session['id'], energy_kwh)
if result:
    # Actualiza balance en memoria
    self.authenticated_users[addr]['balance'] = result['updated_balance']
    return f"Central: SESSION_COMPLETE cost={result['cost']:.2f} balance={result['updated_balance']:.2f}"
```

**Qué hace**:
- Calcula costo: `energy_kwh * tariff_per_kwh`
- Descuenta del balance del usuario
- Marca sesión como completada
- Libera el punto de carga (`status='available'`)
- Retorna costo y nuevo balance

### 6. Registro Dinámico de Puntos de Carga
**Ubicación**: `EV_Central.py` línea 85  
**Función BD**: `db.register_or_update_charging_point(cp_id, location)`

```python
db.register_or_update_charging_point(cp_id, location, status='available')
print(f"[CENTRAL] Registered charging point {cp_id} at {location}")
```

**Qué hace**:
- Registra nuevos CPs cuando se conectan por primera vez
- Actualiza ubicación y estado de CPs existentes
- Permite escalabilidad dinámica del sistema

### 7. Consulta de Sesión Activa
**Ubicación**: `EV_Central.py` línea 149  
**Función BD**: `db.get_active_session_for_user(user_id)`

```python
active_session = db.get_active_session_for_user(user['id'])
if active_session:
    return f"Central: ALREADY_CHARGING session_id={active_session['id']}"
```

**Qué hace**:
- Verifica si el usuario ya tiene una sesión activa
- Previene solicitudes duplicadas
- Retorna información de la sesión en curso

## 📁 Archivos Modificados/Creados

### Nuevos Archivos
1. **`database.py`** - Módulo completo de base de datos
2. **`init_db.py`** - Script de inicialización
3. **`README.md`** - Documentación completa
4. **`INTEGRATION_SUMMARY.md`** - Este archivo

### Archivos Modificados
1. **`EV_Central/EV_Central.py`** 
   - Integración completa con database.py
   - Importa módulo db
   - Usa funciones de BD en lugar de JSON

2. **`DEPLOYMENT_GUIDE.md`**
   - Añadido paso de inicialización de BD

## 🗃️ Esquema de Base de Datos

### Tabla `users`
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT,
    role TEXT DEFAULT 'driver',
    balance REAL DEFAULT 100.0,
    active INTEGER DEFAULT 1,
    created_at REAL DEFAULT (julianday('now'))
)
```

### Tabla `charging_points`
```sql
CREATE TABLE charging_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cp_id TEXT UNIQUE NOT NULL,
    location TEXT,
    status TEXT DEFAULT 'available',
    max_power_kw REAL DEFAULT 22.0,
    tariff_per_kwh REAL DEFAULT 0.30,
    last_maintenance REAL,
    active INTEGER DEFAULT 1
)
```

### Tabla `charging_sessions`
```sql
CREATE TABLE charging_sessions (
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
```

### Tabla `event_log`
```sql
CREATE TABLE event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    correlation_id TEXT,
    message_id TEXT,
    event_type TEXT,
    component TEXT,
    details TEXT,
    timestamp REAL DEFAULT (julianday('now'))
)
```

## ✅ Cumplimiento de Requisitos

| Requisito PDF | Estado | Implementación |
|---------------|--------|----------------|
| Persistencia de datos (BD) | ✅ | SQLite con database.py |
| Autenticación de usuarios | ✅ | Hash SHA256, función authenticate_user() |
| Gestión de sesiones | ✅ | Tabla charging_sessions |
| Cálculo de costos | ✅ | energy_kwh * tariff_per_kwh |
| Log de eventos | ✅ | Tabla event_log |
| Correlation IDs | ✅ | Guardados en sessions y event_log |
| Registro de CPs | ✅ | Función register_or_update_charging_point() |

## 🚀 Cómo Usar

### 1. Inicializar BD (primera vez)
```bash
python init_db.py
```

### 2. Ejecutar Central
```bash
python EV_Central/EV_Central.py
```

### 3. Conectar Drivers/CPs
Los clientes se autenticarán y el sistema usará la BD automáticamente.

## 📊 Consultas Útiles

### Ver usuarios
```python
import database as db
users = db.get_connection().execute("SELECT * FROM users").fetchall()
```

### Ver sesiones activas
```python
sessions = db.get_connection().execute(
    "SELECT * FROM charging_sessions WHERE status='active'"
).fetchall()
```

### Ver historial de un usuario
```python
history = db.get_user_sessions(user_id=1, limit=10)
```

---

**✅ La integración está completa y lista para usarse en la práctica.**
