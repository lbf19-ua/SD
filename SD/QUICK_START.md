# 🚀 INICIO RÁPIDO - Interfaces Web

## ⚡ Opción 1: Script Automático (Recomendado)

### Windows PowerShell:

```powershell
# Desde el directorio SD/SD/
.\start_web_interfaces.ps1
```

Esto abrirá **3 ventanas de PowerShell** con cada servidor y mostrará las URLs de acceso.

---

## 🔧 Opción 2: Inicio Manual

### 1. Instalar dependencias

```powershell
pip install -r requirements.txt
```

### 2. Inicializar base de datos (solo la primera vez)

```powershell
python init_db.py
```

### 3. Iniciar cada servidor (en terminales separadas)

**Terminal 1 - Driver Dashboard:**
```powershell
python EV_Driver\EV_Driver_WebSocket.py
```

**Terminal 2 - Admin Dashboard:**
```powershell
python EV_Central\EV_Central_WebSocket.py
```

**Terminal 3 - Monitor Dashboard:**
```powershell
python EV_CP_M\EV_CP_M_WebSocket.py
```

### 4. Abrir en el navegador

- 🚗 **Driver:** http://localhost:8001
- 🏢 **Admin:** http://localhost:8002
- 📊 **Monitor:** http://localhost:8003

---

## 🔐 Credenciales de Prueba

```
driver1 / pass123         (Balance: €150.00)
driver2 / pass456         (Balance: €200.00)
driver3 / pass789         (Balance: €75.50)
maria_garcia / maria2025  (Balance: €180.00)
juan_lopez / juan123      (Balance: €95.25)
admin / admin123          (Administrador)
```

---

## 📊 Flujo de Prueba Completo

### 1. Abrir las 3 interfaces

Abre 3 pestañas en tu navegador:
- Pestaña 1: http://localhost:8001 (Driver)
- Pestaña 2: http://localhost:8002 (Admin)
- Pestaña 3: http://localhost:8003 (Monitor)

### 2. Login como Driver

En la pestaña 1 (Driver):
1. Username: `driver1`
2. Password: `pass123`
3. Click "Iniciar Sesión"

### 3. Solicitar Carga

En la pestaña 1 (Driver):
1. Click en "Solicitar Carga"
2. Observa que aparece el punto de carga asignado
3. La barra de progreso comienza a incrementarse
4. El contador de energía y costo se actualiza en tiempo real

### 4. Observar en Admin Dashboard

En la pestaña 2 (Admin):
1. Verás la nueva sesión en "Sesiones Activas"
2. El punto de carga cambiará a estado "Cargando"
3. El balance del usuario se mostrará
4. Los ingresos se actualizarán

### 5. Observar en Monitor Dashboard

En la pestaña 3 (Monitor):
1. El punto de carga asignado cambiará a estado "🟡 Cargando"
2. Verás la potencia actual activa
3. Una alerta aparecerá: "✅ Carga iniciada en CP_XXX por driver1"
4. Las métricas se actualizarán en tiempo real

### 6. Detener Carga

En la pestaña 1 (Driver):
1. Click en "Detener Carga"
2. Verás el resumen: energía cargada, costo total, nuevo balance
3. El punto de carga se liberará

### 7. Verificar Resultados

- **Admin Dashboard:** Balance actualizado, sesión completada
- **Monitor Dashboard:** CP vuelve a "🟢 Disponible", alerta de carga completada

---

## 🌐 Acceso desde Red Local

Para acceder desde otros PCs en la misma red:

### En el PC que ejecuta los servidores:

1. Averigua tu IP local:
```powershell
ipconfig
```
Busca "IPv4 Address" (ej: 192.168.1.100)

2. Configura el firewall para permitir puertos 8001, 8002, 8003

### Desde otros PCs en la red:

- Driver: `http://192.168.1.100:8001`
- Admin: `http://192.168.1.100:8002`
- Monitor: `http://192.168.1.100:8003`

---

## 🐛 Solución de Problemas

### Error: "ModuleNotFoundError: No module named 'websockets'"

```powershell
pip install websockets aiohttp
```

### Error: "Database not found"

```powershell
python init_db.py
```

### Error: "Address already in use" (Puerto ocupado)

Verifica que no haya otra instancia ejecutándose:
```powershell
netstat -ano | findstr :8001
netstat -ano | findstr :8002
netstat -ano | findstr :8003
```

Mata el proceso si es necesario:
```powershell
taskkill /PID <PID> /F
```

### La interfaz no se conecta (punto rojo)

1. Verifica que el servidor Python esté ejecutándose
2. Revisa la consola del servidor para ver errores
3. Abre la consola del navegador (F12) y revisa errores de WebSocket
4. Asegúrate de que no haya firewall bloqueando la conexión

### Los datos no se actualizan

1. Verifica que la base de datos esté inicializada
2. Comprueba que los servidores estén ejecutándose sin errores
3. Refresca la página (F5)
4. Revisa la consola del navegador (F12)

---

## 📁 Estructura de Archivos

```
SD/
├── database.py                           # Módulo de base de datos
├── init_db.py                            # Inicializar BD
├── ev_charging.db                        # Base de datos SQLite
├── requirements.txt                      # Dependencias
├── start_web_interfaces.ps1              # Script de inicio rápido
├── WEB_INTERFACES_README.md              # Documentación completa
├── QUICK_START.md                        # Este archivo
│
├── EV_Driver/
│   ├── EV_Driver_WebSocket.py            # ⭐ Servidor WebSocket (USAR ESTE)
│   ├── EV_Driver.py                      # Versión original (CLI)
│   └── dashboard.html                    # Interfaz web
│
├── EV_Central/
│   ├── EV_Central_WebSocket.py           # ⭐ Servidor WebSocket (USAR ESTE)
│   ├── EV_Central.py                     # Versión original (CLI)
│   └── admin_dashboard.html              # Interfaz web
│
└── EV_CP_M/
    ├── EV_CP_M_WebSocket.py              # ⭐ Servidor WebSocket (USAR ESTE)
    ├── EV_CP_M.py                        # Versión original (CLI)
    └── monitor_dashboard.html            # Interfaz web
```

---

## 🎓 Para Demostración al Profesor

### Configuración Previa (5 minutos antes):

1. Ejecutar `start_web_interfaces.ps1`
2. Abrir 3 pestañas del navegador con las 3 URLs
3. Tener preparada una cuenta de prueba (ej: driver1/pass123)

### Durante la Demo (5-10 minutos):

1. **Mostrar las 3 interfaces** vacías inicialmente
2. **Login en Driver Dashboard** con credenciales
3. **Solicitar carga** y mostrar:
   - Actualización en tiempo real del progreso
   - Cálculo automático de costo
   - Sincronización entre las 3 interfaces
4. **Mostrar Admin Dashboard**:
   - Sesión activa visible
   - Estadísticas actualizándose
   - Estado de puntos de carga
5. **Mostrar Monitor Dashboard**:
   - Alertas del sistema
   - Métricas de CPs
   - Gráficos de uso
6. **Detener carga** y mostrar:
   - Cálculo final de costo
   - Actualización de balance
   - Liberación del punto de carga
7. **Explicar arquitectura**:
   - WebSockets para comunicación bidireccional
   - Base de datos SQLite para persistencia
   - Actualización en tiempo real sin recargar

### Puntos Clave a Destacar:

✅ **Interfaces responsivas** y profesionales
✅ **Comunicación en tiempo real** vía WebSocket
✅ **Persistencia de datos** en SQLite
✅ **Sincronización** entre componentes
✅ **Cálculo automático** de costos
✅ **Monitoreo** de estado del sistema
✅ **Alertas** en tiempo real

---

## 📞 Ayuda Adicional

Consulta `WEB_INTERFACES_README.md` para:
- Documentación completa del protocolo WebSocket
- Detalles de las funcionalidades de cada interfaz
- Configuración avanzada
- Troubleshooting detallado

---

## ✅ Checklist de Verificación

Antes de demostrar, asegúrate de que:

- [ ] Base de datos inicializada (`ev_charging.db` existe)
- [ ] Dependencias instaladas (`websockets`, `aiohttp`, `kafka-python`)
- [ ] Los 3 servidores WebSocket están ejecutándose
- [ ] Puedes acceder a las 3 URLs en el navegador
- [ ] El indicador de conexión está en verde (🟢 Conectado)
- [ ] Puedes hacer login con las credenciales de prueba
- [ ] La solicitud de carga funciona correctamente
- [ ] Los datos se actualizan en tiempo real

---

¡Listo para demostrar! 🚀
