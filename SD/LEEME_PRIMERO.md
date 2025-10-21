# 🚀 SISTEMA EV CHARGING - LEE ESTO PRIMERO

## 📖 GUÍA ÚNICA Y DEFINITIVA

**Todo lo que necesitas saber está en UN SOLO archivo:**

👉 **[GUIA_COMPLETA_DESPLIEGUE.md](GUIA_COMPLETA_DESPLIEGUE.md)** 👈

Esta guía contiene:

✅ **Requisitos previos**: Hardware, software y red
✅ **Arquitectura completa**: Qué hace cada PC
✅ **Preparación inicial**: Obtener IPs y configurar
✅ **Despliegue paso a paso**: PC por PC con comandos exactos
✅ **Verificación**: Cómo confirmar que todo funciona
✅ **Uso del sistema**: Acceder a dashboards y probar
✅ **Comandos útiles**: Docker, Kafka, logs, etc.
✅ **Troubleshooting**: Solución a problemas comunes
✅ **Mantenimiento**: Actualizar, backup, monitorear

---

## 🎯 INICIO ULTRA-RÁPIDO (2 Pasos)

Si quieres empezar YA, ejecuta esto **EN CADA PC**:

```powershell
# 1. Editar network_config.py con tus IPs (solo primera vez)

# 2. Iniciar Docker
.\docker_manager.ps1 up -Build
```

---

## 📦 ¿QUÉ NECESITAS TENER ANTES?

### Software Obligatorio (en TODOS los PCs):
- ✅ **Docker Desktop** - https://www.docker.com/products/docker-desktop
- ✅ **PowerShell** - Ya incluido en Windows

### Software Adicional (solo PC2):
- ✅ **Python 3.10+** - https://www.python.org/downloads/

### Red:
- ✅ Los 3 PCs en la **misma red local**
- ✅ Saber la **IP de cada PC** (usa `ipconfig`)

---

## 🏗️ ARQUITECTURA SIMPLE

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ PC1: DRIVER │◄────►│ PC2: CENTRAL│◄────►│ PC3: MONITOR│
│   :8001     │      │ Kafka :9092 │      │   :8003     │
└─────────────┘      │ Admin :8002 │      └─────────────┘
                     │ UI    :8080 │
                     └─────────────┘
```

**PC2 es el corazón** - Debe iniciarse PRIMERO.

---

## 🌐 URLs DEL SISTEMA

Después de desplegar, accede a:

| Dashboard | URL | Descripción |
|-----------|-----|-------------|
| **Driver** | http://\<PC1_IP\>:8001 | Conductores solicitan carga |
| **Admin** | http://\<PC2_IP\>:8002 | Administración del sistema |
| **Monitor** | http://\<PC3_IP\>:8003 | Monitorización de CPs |
| **Kafka UI** | http://\<PC2_IP\>:8080 | Ver mensajes de Kafka |

---

## 📚 ¿NECESITAS MÁS DETALLES?

� Abre **[GUIA_COMPLETA_DESPLIEGUE.md](GUIA_COMPLETA_DESPLIEGUE.md)**

Es la **ÚNICA guía** que necesitas. Contiene todo explicado paso a paso con:
- 📋 Requisitos detallados
- 🛠️ Instrucciones precisas
- 🖼️ Diagramas de arquitectura
- 🔧 Comandos completos
- 🐛 Solución a problemas
- ✅ Checklists de verificación

---

## 🔥 SOLUCIÓN RÁPIDA A PROBLEMAS COMUNES

### ❌ Docker no arranca
```powershell
# Verifica que Docker Desktop está corriendo
docker --version
docker ps
```

### ❌ No conecta a Kafka
```powershell
# En PC2, verifica que Kafka está up
docker-compose -f docker-compose.pc2.yml ps

# En PC1/PC3, prueba conectividad
Test-NetConnection <PC2_IP> -Port 9092
```

### ❌ Puerto ocupado
```powershell
# Ver qué usa el puerto
netstat -ano | findstr :8001

# Matar el proceso
taskkill /PID <PID> /F
```

**Más soluciones** → [GUIA_COMPLETA_DESPLIEGUE.md#troubleshooting](GUIA_COMPLETA_DESPLIEGUE.md#troubleshooting)

---

## 🛠️ SCRIPTS DISPONIBLES

| Script | Función | Admin? |
|--------|---------|--------|
| `docker_manager.ps1` | Gestionar contenedores Docker | ❌ |

---

## ✅ CHECKLIST ANTES DE EMPEZAR

- [ ] Docker Desktop instalado en los 3 PCs
- [ ] Docker Desktop está **corriendo** (ver icono en bandeja)
- [ ] Tienes las IPs de los 3 PCs (usa `ipconfig`)
- [ ] Los 3 PCs están en la misma red
- [ ] Python instalado en PC2 (para inicializar BD)

**¿Listo?** → Abre **[GUIA_COMPLETA_DESPLIEGUE.md](GUIA_COMPLETA_DESPLIEGUE.md)** y sigue los pasos.

---

## 🎓 PARA DESARROLLO/TESTING EN 1 SOLO PC

Si solo quieres probar sin 3 PCs:

```powershell
# Usa el docker-compose completo
docker-compose up -d --build

# Accede a:
# http://localhost:8001 (Driver)
# http://localhost:8002 (Admin)
# http://localhost:8003 (Monitor)
# http://localhost:8080 (Kafka UI)
```

---

**� RECUERDA: Todo está en [GUIA_COMPLETA_DESPLIEGUE.md](GUIA_COMPLETA_DESPLIEGUE.md)**

**¡Buena suerte con el despliegue! 🚀**


### 📝 PASO 1: Verificar que tienes todo

```powershell
# Navegar al directorio
cd C:\Users\luisb\Desktop\SD\SD

# Verificar que existe la base de datos
dir ev_charging.db

# Si NO existe, crearla:
python init_db.py
```

### 📦 PASO 2: Instalar dependencias (ya hecho ✅)

Las dependencias ya están instaladas en tu entorno virtual:
- ✅ websockets
- ✅ aiohttp
- ✅ kafka-python

### 🎬 PASO 3: Iniciar los servidores

**OPCIÓN A - Script Automático (Recomendado):**

```powershell
.\start_web_interfaces.ps1
```

Esto abrirá 3 ventanas de PowerShell automáticamente.

**OPCIÓN B - Manual (3 terminales):**

Terminal 1:
```powershell
python EV_Driver\EV_Driver_WebSocket.py
```

Terminal 2:
```powershell
python EV_Central\EV_Central_WebSocket.py
```

Terminal 3:
```powershell
python EV_CP_M\EV_CP_M_WebSocket.py
```

### 🌐 PASO 4: Abrir en el navegador

Abre 3 pestañas:
1. http://localhost:8001 (Driver)
2. http://localhost:8002 (Admin)  
3. http://localhost:8003 (Monitor)

---

## 🧪 PRUEBA RÁPIDA (2 minutos)

### 1. Login como conductor

En **http://localhost:8001**:
- Usuario: `driver1`
- Contraseña: `pass123`
- Click "Iniciar Sesión"

✅ Deberías ver tu balance: €150.00

### 2. Solicitar carga

- Click en "Solicitar Carga"
- Observa:
  - ✅ Aparece el punto de carga asignado (ej: CP_001)
  - ✅ La barra de progreso comienza a moverse
  - ✅ El contador de energía sube (0.01 kWh, 0.02 kWh...)
  - ✅ El costo se calcula automáticamente

### 3. Ver en Admin Dashboard

En **http://localhost:8002**:
- ✅ Verás la sesión en "Sesiones Activas"
- ✅ El punto de carga aparece como "Cargando"
- ✅ Las estadísticas se actualizan

### 4. Ver en Monitor Dashboard

En **http://localhost:8003**:
- ✅ El CP cambia a estado "🟡 Cargando"
- ✅ Aparece una alerta: "✅ Carga iniciada..."
- ✅ Las métricas se actualizan

### 5. Detener carga

Vuelve a **http://localhost:8001**:
- Click en "Detener Carga"
- Observa:
  - ✅ Resumen de la carga (energía total, costo)
  - ✅ Tu nuevo balance
  - ✅ El CP se libera en las otras interfaces

---

## 🔐 USUARIOS DISPONIBLES

```
driver1 / pass123         Balance: €150.00
driver2 / pass456         Balance: €200.00
driver3 / pass789         Balance: €75.50
driver4 / pass321         Balance: €300.00
driver5 / pass654         Balance: €25.75
maria_garcia / maria2025  Balance: €180.00
juan_lopez / juan123      Balance: €95.25
ana_martinez / ana456     Balance: €220.00
pedro_sanchez / pedro789  Balance: €45.00
laura_fernandez / laura321 Balance: €165.50
admin / admin123          Rol: Administrador
operator1 / oper123       Rol: Operador
```

---

## 📊 PUNTOS DE CARGA EN LA BD

```
CP_001 - Campus Norte               22.0 kW - €0.30/kWh
CP_002 - Campus Sur                 50.0 kW - €0.35/kWh
CP_003 - Biblioteca                 11.0 kW - €0.25/kWh
CP_004 - Estacionamiento Principal  22.0 kW - €0.28/kWh
CP_005 - Edificio Deportes           7.4 kW - €0.22/kWh
CP_006 - Centro Comercial Plaza     43.0 kW - €0.38/kWh
CP_007 - Hospital San Juan          50.0 kW - €0.32/kWh
CP_008 - Estación de Tren          150.0 kW - €0.45/kWh
CP_009 - Aeropuerto Terminal 1     120.0 kW - €0.42/kWh
CP_010 - Parking Residencial Sur    11.0 kW - €0.26/kWh
```

---

## 🐛 SOLUCIÓN DE PROBLEMAS

### ❌ "Address already in use" (Puerto ocupado)

**Causa:** Ya hay un servidor ejecutándose en ese puerto.

**Solución 1 - Cerrar el proceso existente:**
```powershell
# Ver qué proceso usa el puerto 8001
netstat -ano | findstr :8001

# Matar el proceso (reemplaza PID con el número que salió arriba)
taskkill /PID <PID> /F
```

**Solución 2 - Usar diferentes puertos:**
Edita los archivos *_WebSocket.py y cambia:
```python
WS_PORT = 8004  # En lugar de 8001
HTTP_PORT = 8004
```

### ❌ "Database not found"

**Solución:**
```powershell
python init_db.py
```

### ❌ "ModuleNotFoundError: No module named 'websockets'"

**Solución:**
```powershell
pip install websockets aiohttp
```

### ❌ La interfaz no se conecta (punto rojo 🔴)

**Verificar:**
1. ✅ El servidor Python está ejecutándose
2. ✅ No hay errores en la terminal del servidor
3. ✅ La URL es correcta (localhost, no 127.0.0.1)
4. ✅ El firewall no bloquea el puerto

**Solución:**
- Abre la consola del navegador (F12) → Pestaña "Console"
- Busca errores de WebSocket
- Refresca la página (Ctrl+F5)

### ❌ Los datos no se actualizan

**Solución:**
1. Refresca la página (F5)
2. Verifica que el indicador está verde 🟢
3. Revisa la consola del navegador (F12)
4. Revisa que la base de datos tiene datos (python query_db.py)

---

## 📚 DOCUMENTACIÓN COMPLETA

Tienes 3 archivos de documentación:

1. **`QUICK_START.md`** → Inicio rápido y demo al profesor
2. **`WEB_INTERFACES_README.md`** → Documentación técnica completa
3. **`IMPLEMENTATION_SUMMARY.md`** → Resumen de la implementación

---

## 🎓 PARA DEMOSTRAR AL PROFESOR

### Preparación (5 min antes):

1. ✅ Ejecutar `start_web_interfaces.ps1`
2. ✅ Abrir 3 pestañas del navegador con las 3 URLs
3. ✅ Verificar que todo está conectado (indicador verde 🟢)

### Durante la Demo (5-10 min):

1. **Mostrar las 3 interfaces** en paralelo
2. **Login** con driver1/pass123
3. **Solicitar carga** y mostrar actualización en tiempo real
4. **Mostrar sincronización** entre las 3 interfaces
5. **Destacar características**:
   - WebSocket bidireccional
   - Actualización sin recargar
   - Base de datos SQLite
   - Cálculo automático de costos
   - Diseño responsive
6. **Detener carga** y mostrar resultado final

### Puntos a destacar:

- ✅ **3 interfaces** profesionales y funcionales
- ✅ **Comunicación en tiempo real** vía WebSocket
- ✅ **Persistencia** en SQLite
- ✅ **Sincronización** automática entre componentes
- ✅ **Cálculo correcto** de costos basado en tarifas
- ✅ **Monitoreo** completo del sistema

---

## ✅ CHECKLIST FINAL

Antes de demostrar:

- [x] Base de datos inicializada (`ev_charging.db` existe)
- [x] Dependencias instaladas (websockets, aiohttp)
- [x] 3 servidores WebSocket creados
- [x] 3 interfaces HTML creadas
- [x] Script de inicio automático creado
- [x] Documentación completa
- [ ] Los 3 servidores están ejecutándose SIN ERRORES
- [ ] Puedes acceder a las 3 URLs en el navegador
- [ ] El indicador de conexión está en verde (🟢)
- [ ] Puedes hacer login con las credenciales
- [ ] La solicitud de carga funciona
- [ ] Los datos se actualizan en tiempo real

---

## 🎯 SIGUIENTE PASO

**¡PROBARLO!**

```powershell
# Navega al directorio
cd C:\Users\luisb\Desktop\SD\SD

# Ejecuta el script de inicio
.\start_web_interfaces.ps1

# Abre el navegador en:
# http://localhost:8001
# http://localhost:8002
# http://localhost:8003
```

---

## 📞 ¿NECESITAS AYUDA?

1. Revisa `QUICK_START.md` para instrucciones paso a paso
2. Revisa `WEB_INTERFACES_README.md` para detalles técnicos
3. Ejecuta `python query_db.py` para explorar la base de datos
4. Abre la consola del navegador (F12) para ver errores JavaScript

---

## 🏆 ¡FELICIDADES!

Has implementado un sistema completo con:
- ✅ 3 interfaces web profesionales
- ✅ Comunicación WebSocket bidireccional
- ✅ Base de datos SQLite persistente
- ✅ Actualización en tiempo real
- ✅ Sincronización multi-componente
- ✅ Documentación completa

**¡TODO LISTO PARA DEMOSTRAR! 🚀**

---

*Creado: 20 de Octubre de 2025*
*Versión: 1.0.0*
*¡Disfruta tu sistema de carga de vehículos eléctricos!* ⚡🚗
