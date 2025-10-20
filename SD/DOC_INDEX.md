# 📖 ÍNDICE DE DOCUMENTACIÓN - Sistema EV Charging

## 🎯 ¿Qué estás buscando?

---

## 🚀 QUIERO INSTALAR EL SISTEMA

### Si es tu primera vez:
1. **[QUICK_DEPLOY_10_STEPS.md](QUICK_DEPLOY_10_STEPS.md)** ⭐⭐⭐  
   → Guía rápida de 10 pasos, ideal para empezar

### Si quieres instrucciones detalladas:
2. **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** 📖  
   → Guía completa paso a paso con todos los detalles técnicos

### Si quieres una lista de verificación:
3. **[INSTALLATION_CHECKLIST.md](INSTALLATION_CHECKLIST.md)** ✅  
   → Checklist para marcar cada paso en cada PC

### Si necesitas descargar software:
4. **[DOWNLOADS_GUIDE.md](DOWNLOADS_GUIDE.md)** 📥  
   → Enlaces directos a Python, Java, Kafka, etc.

---

## 🌐 QUIERO USAR LAS INTERFACES WEB

### Para entender las interfaces:
1. **[WEB_INTERFACES_README.md](WEB_INTERFACES_README.md)** 🖥️  
   → Documentación técnica completa de las 3 interfaces

### Para iniciar rápidamente:
2. **[QUICK_START.md](QUICK_START.md)** ⚡  
   → Cómo iniciar los servidores WebSocket y acceder

### Para un resumen ejecutivo:
3. **[README_INTERFACES.md](README_INTERFACES.md)** 📄  
   → Resumen de características y funcionalidades

---

## 📊 QUIERO VER EL ESTADO DEL PROYECTO

### Estado general:
1. **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** 📦  
   → Resumen completo del sistema (arquitectura, tecnologías, métricas)

### Estado de implementación:
2. **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** 📊  
   → Qué está completado y qué falta

3. **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** 📋  
   → Resumen de la implementación realizada

---

## 🔧 TENGO UN PROBLEMA

### Problemas de instalación:
→ Ver sección "Resolución de Problemas" en **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#resolución-de-problemas)**

### Problemas con interfaces web:
→ Ver sección "Troubleshooting" en **[WEB_INTERFACES_README.md](WEB_INTERFACES_README.md#troubleshooting)**

### Errores comunes:
→ Ver tabla en **[QUICK_DEPLOY_10_STEPS.md](QUICK_DEPLOY_10_STEPS.md#solución-de-problemas-rápida)**

---

## 📚 DOCUMENTACIÓN TÉCNICA

### Arquitectura general:
→ **[README.md](README.md)** - Documentación principal del proyecto

### Base de datos:
→ Ver archivo `database.py` y función `init_db.py`

### Configuración de red:
→ Ver `network_config.py` y sección en **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#configuración-de-red)**

---

## 🗺️ MAPA DE ARCHIVOS DEL PROYECTO

```
📁 SD/
│
├── 📖 DOCUMENTACIÓN (LÉEME)
│   ├── 📄 README.md ................................. Documentación principal
│   ├── 📄 DOC_INDEX.md .............................. Este archivo (índice)
│   ├── 📄 PROJECT_SUMMARY.md ........................ Resumen completo
│   │
│   ├── 🚀 INSTALACIÓN
│   │   ├── QUICK_DEPLOY_10_STEPS.md ................. ⭐ Guía rápida 10 pasos
│   │   ├── DEPLOYMENT_GUIDE.md ...................... Guía completa
│   │   ├── INSTALLATION_CHECKLIST.md ................ Checklist detallado
│   │   └── DOWNLOADS_GUIDE.md ....................... Enlaces de descarga
│   │
│   ├── 🌐 INTERFACES WEB
│   │   ├── WEB_INTERFACES_README.md ................. Doc completa
│   │   ├── QUICK_START.md ........................... Inicio rápido
│   │   └── README_INTERFACES.md ..................... Resumen ejecutivo
│   │
│   └── 📊 ESTADO
│       ├── IMPLEMENTATION_STATUS.md ................. Estado implementación
│       ├── IMPLEMENTATION_SUMMARY.md ................ Resumen implementación
│       └── INTEGRATION_SUMMARY.md ................... Resumen integración
│
├── 🔧 CONFIGURACIÓN
│   ├── requirements.txt ............................. Dependencias Python
│   ├── network_config.py ............................ IPs y puertos
│   ├── database.py .................................. Módulo BD SQLite
│   ├── event_utils.py ............................... Utilidades Kafka
│   ├── init_db.py ................................... Inicializador BD
│   ├── test_connections.py .......................... Pruebas conectividad
│   └── ev_charging.db ............................... Base de datos
│
├── 🚗 PC1 - EV_DRIVER (Interfaz Conductores)
│   └── EV_Driver/
│       ├── EV_Driver.py ............................. Cliente CLI
│       ├── EV_Driver_WebSocket.py ................... Servidor WS (8001)
│       └── dashboard.html ........................... Dashboard web
│
├── 🏢 PC2 - EV_CENTRAL (Servidor Central)
│   └── EV_Central/
│       ├── EV_Central.py ............................ Servidor CLI
│       ├── EV_Central_WebSocket.py .................. Servidor WS (8002)
│       └── admin_dashboard.html ..................... Dashboard admin
│
├── 📊 PC3 - EV_CP_M (Monitor)
│   └── EV_CP_M/
│       ├── EV_CP_M.py ............................... Monitor CLI
│       ├── EV_CP_M_WebSocket.py ..................... Servidor WS (8003)
│       └── monitor_dashboard.html ................... Dashboard monitor
│
└── ⚙️ PC3 - EV_CP_E (Motor Simulación)
    └── EV_CP_E/
        └── EV_CP_E.py ............................... Motor simulación
```

---

## 🎯 RUTAS RÁPIDAS POR TAREA

### Primera instalación en 3 PCs:
1. Leer: **[QUICK_DEPLOY_10_STEPS.md](QUICK_DEPLOY_10_STEPS.md)**
2. Descargar: **[DOWNLOADS_GUIDE.md](DOWNLOADS_GUIDE.md)**
3. Verificar: **[INSTALLATION_CHECKLIST.md](INSTALLATION_CHECKLIST.md)**

### Configurar red local:
1. Ver: **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#configuración-de-red)**
2. Editar: `network_config.py`
3. Verificar: Ejecutar `test_connections.py`

### Iniciar interfaces web:
1. Leer: **[QUICK_START.md](QUICK_START.md)**
2. Ejecutar: Servidores *_WebSocket.py
3. Acceder: http://IP:800X en navegador

### Resolver problemas:
1. Ver: **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#resolución-de-problemas)**
2. Verificar: Firewall, puertos, IPs
3. Debug: Logs en consola de cada servidor

---

## 📊 DOCUMENTACIÓN POR COMPONENTE

### EV_Driver (PC1)
- **CLI**: Ver código en `EV_Driver/EV_Driver.py`
- **WebSocket**: Ver `EV_Driver/EV_Driver_WebSocket.py`
- **Dashboard**: Ver `EV_Driver/dashboard.html`
- **Doc**: [WEB_INTERFACES_README.md](WEB_INTERFACES_README.md#1-driver-dashboard-puerto-8001)

### EV_Central (PC2)
- **CLI**: Ver código en `EV_Central/EV_Central.py`
- **WebSocket**: Ver `EV_Central/EV_Central_WebSocket.py`
- **Dashboard**: Ver `EV_Central/admin_dashboard.html`
- **Doc**: [WEB_INTERFACES_README.md](WEB_INTERFACES_README.md#2-admin-dashboard-puerto-8002)

### EV_CP_M (PC3)
- **CLI**: Ver código en `EV_CP_M/EV_CP_M.py`
- **WebSocket**: Ver `EV_CP_M/EV_CP_M_WebSocket.py`
- **Dashboard**: Ver `EV_CP_M/monitor_dashboard.html`
- **Doc**: [WEB_INTERFACES_README.md](WEB_INTERFACES_README.md#3-monitor-dashboard-puerto-8003)

### EV_CP_E (PC3)
- **Motor**: Ver código en `EV_CP_E/EV_CP_E.py`
- **Doc**: [README.md](README.md#charging-points-ev_cp_e-y-ev_cp_m)

---

## 🔍 BUSCAR POR TEMA

### Apache Kafka
- Instalación: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#paso-4-instalar-y-configurar-apache-kafka)
- Configuración: Ver sección 4.3 en DEPLOYMENT_GUIDE.md
- Topics: Ver sección 4.4 en DEPLOYMENT_GUIDE.md

### Base de Datos
- Estructura: Ver `database.py`
- Inicialización: Ver `init_db.py`
- Usuarios de prueba: [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md#usuarios-de-prueba)

### WebSockets
- Implementación: Ver archivos `*_WebSocket.py`
- Configuración: [WEB_INTERFACES_README.md](WEB_INTERFACES_README.md)
- Troubleshooting: Ver sección en WEB_INTERFACES_README.md

### Red y Conectividad
- IPs y puertos: Ver `network_config.py`
- Configuración: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#configuración-de-red)
- Firewall: Ver sección en DEPLOYMENT_GUIDE.md
- Pruebas: Ver `test_connections.py`

### Python y Dependencias
- Requisitos: Ver `requirements.txt`
- Instalación: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#paso-4-instalar-dependencias)
- Entorno virtual: Ver paso 3 en cualquier guía de instalación

---

## 📞 AYUDA Y SOPORTE

### Necesito ayuda con...

#### ...la instalación
→ **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** sección "Resolución de Problemas"

#### ...las interfaces web
→ **[WEB_INTERFACES_README.md](WEB_INTERFACES_README.md)** sección "Troubleshooting"

#### ...la configuración de red
→ **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#configuración-de-red)**

#### ...Kafka
→ **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#paso-4-instalar-y-configurar-apache-kafka)**

#### ...errores específicos
→ Ver tabla de errores en **[QUICK_DEPLOY_10_STEPS.md](QUICK_DEPLOY_10_STEPS.md#solución-de-problemas-rápida)**

---

## 🎓 GUÍAS POR NIVEL DE EXPERIENCIA

### 🟢 Principiante (primera vez con el sistema)
1. **[QUICK_DEPLOY_10_STEPS.md](QUICK_DEPLOY_10_STEPS.md)** - Sigue los 10 pasos
2. **[INSTALLATION_CHECKLIST.md](INSTALLATION_CHECKLIST.md)** - Marca cada item
3. Pide ayuda si te atascas en la sección de Problemas

### 🟡 Intermedio (tienes experiencia con Python/redes)
1. **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Guía completa
2. `network_config.py` - Edita configuración directamente
3. **[WEB_INTERFACES_README.md](WEB_INTERFACES_README.md)** - Entiende la arquitectura

### 🔴 Avanzado (desarrollador/administrador de sistemas)
1. **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - Arquitectura completa
2. Lee el código fuente directamente
3. **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** - Amplía el sistema

---

## 📈 ROADMAP DE LECTURA RECOMENDADO

### Para instalar el sistema:
```
START
  ↓
QUICK_DEPLOY_10_STEPS.md (20 min lectura)
  ↓
DOWNLOADS_GUIDE.md (descargar software)
  ↓
DEPLOYMENT_GUIDE.md (referencia durante instalación)
  ↓
INSTALLATION_CHECKLIST.md (verificar cada paso)
  ↓
test_connections.py (probar conectividad)
  ↓
END - Sistema instalado ✅
```

### Para entender el sistema:
```
START
  ↓
README.md (visión general)
  ↓
PROJECT_SUMMARY.md (arquitectura y tecnologías)
  ↓
WEB_INTERFACES_README.md (interfaces web)
  ↓
Código fuente (*.py files)
  ↓
END - Sistema comprendido ✅
```

---

## 🎯 OBJETIVOS DE CADA DOCUMENTO

| Documento | Objetivo | Tiempo Lectura |
|-----------|----------|----------------|
| **README.md** | Visión general del proyecto | 10 min |
| **DOC_INDEX.md** | Navegación (este archivo) | 5 min |
| **PROJECT_SUMMARY.md** | Resumen completo | 15 min |
| **QUICK_DEPLOY_10_STEPS.md** | Instalación rápida | 20 min |
| **DEPLOYMENT_GUIDE.md** | Instalación detallada | 45 min |
| **INSTALLATION_CHECKLIST.md** | Verificación | 30 min |
| **DOWNLOADS_GUIDE.md** | Obtener software | 10 min |
| **WEB_INTERFACES_README.md** | Doc técnica interfaces | 25 min |
| **QUICK_START.md** | Inicio rápido interfaces | 10 min |
| **README_INTERFACES.md** | Resumen interfaces | 5 min |

**Tiempo total de lectura completa**: ~3 horas  
**Tiempo mínimo para empezar**: 30 minutos (QUICK_DEPLOY + DOWNLOADS)

---

## ✅ CHECKLIST PRE-DEMOSTRACIÓN

### 📚 Documentación leída:
- [ ] QUICK_DEPLOY_10_STEPS.md
- [ ] DEPLOYMENT_GUIDE.md (sección de mi PC)
- [ ] INSTALLATION_CHECKLIST.md

### 💻 Software instalado:
- [ ] Python 3.11+ (todos los PCs)
- [ ] Java 11+ (solo PC2)
- [ ] Apache Kafka (solo PC2)

### 🔧 Sistema configurado:
- [ ] Archivos copiados a cada PC
- [ ] Entornos virtuales creados
- [ ] Dependencias instaladas
- [ ] network_config.py editado
- [ ] Archivos HTML editados
- [ ] Firewall configurado

### ✅ Sistema probado:
- [ ] Kafka inicia correctamente
- [ ] Todos los servidores arrancan
- [ ] Interfaces web accesibles
- [ ] WebSockets conectados
- [ ] Login funciona
- [ ] Carga funciona

---

## 🏁 ¡LISTO PARA EMPEZAR!

### Nueva instalación:
👉 **Comienza aquí**: [QUICK_DEPLOY_10_STEPS.md](QUICK_DEPLOY_10_STEPS.md)

### Entender el proyecto:
👉 **Comienza aquí**: [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)

### Problema específico:
👉 **Busca aquí**: Usa la sección "🔍 BUSCAR POR TEMA" arriba

---

**¿Perdido?** → Vuelve a este archivo (DOC_INDEX.md) y busca lo que necesitas.

**¿Todo claro?** → ¡Adelante con la instalación! 🚀
