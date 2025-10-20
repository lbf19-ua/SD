# 🌐 Interfaces Web con WebSocket

## 📋 Descripción

Este sistema incluye **3 interfaces web** con comunicación en tiempo real mediante **WebSockets**, una para cada componente del despliegue distribuido:

### 🚗 **1. EV_Driver Dashboard** (Puerto 8001)
**Ubicación**: `EV_Driver/dashboard.html`

**Funcionalidades**:
- 🔐 Login de usuarios (driver1/pass123, driver2/pass456, etc.)
- 💰 Visualización de balance en tiempo real
- ⚡ Solicitar y detener cargas
- 📊 Monitor de energía cargada y costo actual
- 📈 Barra de progreso de carga
- 📋 Log de eventos

**Para usar**:
1. Ejecutar `python EV_Driver/EV_Driver_WebSocket.py` (inicia servidor WebSocket en puerto 8001)
2. Abrir en navegador: `http://localhost:8001`

---

### 🏢 **2. EV_Central Admin Dashboard** (Puerto 8002)
**Ubicación**: `EV_Central/admin_dashboard.html`

**Funcionalidades**:
- 👥 Ver todos los usuarios registrados
- 🔌 Estado de todos los puntos de carga (disponible/cargando/offline)
- ⚡ Sesiones activas con energía y costos en tiempo real
- 💰 Estadísticas del sistema (ingresos, sesiones, usuarios)
- 📡 Stream de eventos del sistema en tiempo real
- 🔄 Auto-actualización cada 5 segundos

**Para usar**:
1. Ejecutar `python EV_Central/EV_Central_WebSocket.py` (inicia servidor WebSocket en puerto 8002)
2. Abrir en navegador: `http://localhost:8002`

---

### 📊 **3. EV_CP Monitor Dashboard** (Puerto 8003)
**Ubicación**: `EV_CP_M/monitor_dashboard.html`

**Funcionalidades**:
- 🔌 Grid visual de todos los puntos de carga
- 🚨 Alertas del sistema (fallos, offline, warnings)
- 📈 Gráfico de uso de puntos de carga (24h)
- 🌡️ Métricas de cada CP (temperatura, eficiencia, uptime)
- ⚡ Potencia actual y máxima
- 🔄 Actualización en tiempo real cada 3 segundos

**Para usar**:
1. Ejecutar `python EV_CP_M/EV_CP_M_WebSocket.py` (inicia servidor WebSocket en puerto 8003)
2. Abrir en navegador: `http://localhost:8003`

---

## 🚀 Instalación de Dependencias

```powershell
# Instalar todas las dependencias necesarias
pip install -r requirements.txt
```

**Dependencias principales**:
- `websockets==12.0` - Servidor WebSocket
- `aiohttp==3.9.1` - Servidor HTTP asíncrono para servir archivos HTML
- `kafka-python==2.0.2` - Cliente Kafka

---

## 🎯 Flujo de Uso Completo

### **Escenario: Conductor solicita carga**

1. **PC1 - Driver abre dashboard** → `http://localhost:8001`
   - Login con `driver1` / `pass123`
   - Click en "Solicitar Carga"

2. **PC2 - Admin ve la solicitud en tiempo real** → `http://localhost:8002`
   - Nueva sesión aparece en "Sesiones Activas"
   - Balance del usuario se actualiza en vivo
   - Punto de carga cambia a estado "Cargando"

3. **PC3 - Monitor detecta la actividad** → `http://localhost:8003`
   - Card del CP cambia a estado "🟡 Cargando"
   - Métricas se actualizan (potencia actual, temperatura)
   - Gráfico de uso se incrementa

4. **Durante la carga**:
   - Driver ve progreso en tiempo real (energía, costo, barra de progreso)
   - Admin ve tabla de sesiones actualizándose
   - Monitor muestra alertas si hay problemas

5. **Al finalizar**:
   - Driver recibe confirmación con costo total
   - Admin actualiza ingresos del día
   - Monitor libera el CP y actualiza estadísticas

---

## 🌐 Despliegue en Red Local

Para acceder desde otros PCs en la red:

### **PC1 (Driver) - IP: 192.168.1.XXX**
```powershell
python EV_Driver/EV_Driver.py
```
Acceder desde cualquier PC: `http://192.168.1.XXX:8001`

### **PC2 (Central) - IP: 192.168.1.227**
```powershell
python EV_Central/EV_Central.py
```
Acceder desde cualquier PC: `http://192.168.1.227:8002`

### **PC3 (Monitor) - IP: 192.168.1.YYY**
```powershell
python EV_CP_M/EV_CP_M.py
```
Acceder desde cualquier PC: `http://192.168.1.YYY:8003`

**NOTA**: Asegúrate de configurar el firewall para permitir conexiones en los puertos 8001, 8002, 8003.

---

## 🎨 Características de las Interfaces

### **Diseño Responsive**
- ✅ Adaptable a diferentes tamaños de pantalla
- ✅ Grid dinámico que se ajusta automáticamente
- ✅ Optimizado para móviles, tablets y escritorio

### **Colores y Temas**
- **Driver**: Gradiente morado/violeta (UX amigable para conductores)
- **Central**: Gradiente azul profesional (dashboard administrativo)
- **Monitor**: Gradiente verde/turquesa (sistema de monitoreo técnico)

### **Indicadores Visuales**
- 🟢 Verde: Disponible / OK / Conectado
- 🟡 Amarillo: Cargando / En proceso
- 🔴 Rojo: Offline / Error / Fallo
- 🔵 Azul: Activo / Información

### **Animaciones**
- Pulsaciones en indicadores de estado
- Transiciones suaves al actualizar datos
- Efectos hover en cards y botones
- Animación de parpadeo en alertas críticas

---

## 📊 Protocolo WebSocket

### **Mensajes del Cliente → Servidor**

#### Driver:
```json
{
  "type": "login",
  "username": "driver1",
  "password": "pass123"
}

{
  "type": "request_charging",
  "username": "driver1"
}

{
  "type": "stop_charging",
  "username": "driver1"
}
```

#### Central:
```json
{
  "type": "get_dashboard_data"
}
```

#### Monitor:
```json
{
  "type": "get_monitor_data"
}
```

### **Mensajes del Servidor → Cliente**

#### Driver:
```json
{
  "type": "login_response",
  "success": true,
  "user": {
    "username": "driver1",
    "balance": 150.0
  }
}

{
  "type": "charging_started",
  "cp_id": "CP_001"
}

{
  "type": "charging_update",
  "energy": 5.2,
  "cost": 1.56
}

{
  "type": "charging_stopped",
  "total_cost": 10.50,
  "new_balance": 139.50
}
```

#### Central:
```json
{
  "type": "dashboard_data",
  "data": {
    "users": [...],
    "charging_points": [...],
    "active_sessions": [...],
    "stats": {
      "total_users": 12,
      "total_cps": 10,
      "active_sessions": 2,
      "today_revenue": 45.80
    }
  }
}

{
  "type": "session_started",
  "username": "driver1",
  "cp_id": "CP_001"
}
```

#### Monitor:
```json
{
  "type": "monitor_data",
  "data": {
    "charging_points": [...],
    "alerts": [...],
    "usage_stats": [...]
  }
}

{
  "type": "fault_detected",
  "cp_id": "CP_002"
}

{
  "type": "cp_offline",
  "cp_id": "CP_003"
}
```

---

## 🔧 Configuración Avanzada

### **Cambiar Puertos**

Edita los archivos Python correspondientes:

**EV_Driver.py**:
```python
WS_PORT = 8001  # Cambia aquí
```

**EV_Central.py**:
```python
WS_PORT = 8002  # Cambia aquí
```

**EV_CP_M.py**:
```python
WS_PORT = 8003  # Cambia aquí
```

### **CORS (Cross-Origin Resource Sharing)**

Si necesitas acceder desde dominios diferentes, habilita CORS en los servidores WebSocket (ya incluido en el código).

---

## 🐛 Troubleshooting

### **Error: "WebSocket connection failed"**
- ✅ Verifica que el servidor Python esté ejecutándose
- ✅ Comprueba que el puerto no esté ocupado: `netstat -ano | findstr :8001`
- ✅ Revisa el firewall

### **Error: "ModuleNotFoundError: No module named 'websockets'"**
```powershell
pip install websockets aiohttp
```

### **La interfaz no se actualiza**
- ✅ Abre la consola del navegador (F12) y revisa errores
- ✅ Verifica que WebSocket esté conectado (punto verde en la interfaz)
- ✅ Comprueba la conectividad de red

### **No veo datos en el dashboard**
- ✅ Asegúrate de que la base de datos esté inicializada (`python init_db.py`)
- ✅ Verifica que Kafka esté ejecutándose
- ✅ Revisa los logs del servidor Python

---

## 📸 Screenshots

### Driver Dashboard
- Vista de login
- Dashboard con sesión activa
- Barra de progreso de carga
- Log de eventos

### Central Dashboard
- Estadísticas principales (cards)
- Tabla de sesiones activas
- Estado de puntos de carga
- Stream de eventos en tiempo real

### Monitor Dashboard
- Grid de puntos de carga con métricas
- Alertas del sistema
- Gráfico de uso (barras)
- Indicadores de estado visual

---

## 🎓 Demo para el Profesor

Para demostrar el sistema completo:

1. **Inicializar BD**: `python init_db.py`
2. **Abrir 3 navegadores** en diferentes ventanas:
   - Ventana 1: `http://localhost:8001` (Driver)
   - Ventana 2: `http://localhost:8002` (Central)
   - Ventana 3: `http://localhost:8003` (Monitor)
3. **Ejecutar los 3 servicios**:
   ```powershell
   # Terminal 1
   python EV_Driver/EV_Driver.py
   
   # Terminal 2
   python EV_Central/EV_Central.py
   
   # Terminal 3
   python EV_CP_M/EV_CP_M.py
   ```
4. **Demostrar flujo**:
   - Login en Driver
   - Solicitar carga
   - Observar actualizaciones en tiempo real en las 3 interfaces
   - Detener carga
   - Mostrar estadísticas finales

---

## 📝 Notas Importantes

- ⚠️ **Las interfaces requieren que los servidores Python estén ejecutándose**
- ⚠️ **La base de datos debe estar inicializada antes de usar las interfaces**
- ⚠️ **Kafka debe estar en ejecución para comunicación entre componentes**
- ✅ **Las interfaces se reconectan automáticamente si se pierde la conexión**
- ✅ **Los datos se actualizan en tiempo real sin recargar la página**
- ✅ **Compatible con Chrome, Firefox, Edge, Safari**

---

## 🔐 Usuarios de Prueba

```
driver1 / pass123
driver2 / pass456
driver3 / pass789
maria_garcia / maria2025
juan_lopez / juan123
admin / admin123
operator1 / oper123
```

¡Listo para demostrar! 🚀
