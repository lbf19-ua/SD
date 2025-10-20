# 📥 DESCARGAS NECESARIAS - Sistema EV Charging

## 🔗 Enlaces de Descarga Directa

---

## 🐍 Python 3.11+
**Versión requerida**: Python 3.11 o superior

### Windows
- **Descarga**: https://www.python.org/downloads/
- **Recomendado**: Python 3.11.9 o 3.12.x
- **Tamaño**: ~25 MB

**⚠️ IMPORTANTE**: Durante la instalación:
1. Marcar la opción: **"Add Python to PATH"**
2. Seleccionar "Install Now"

**Verificar instalación:**
```powershell
python --version
pip --version
```

---

## ☕ Java JDK 11+ (Solo PC2)
**Versión requerida**: OpenJDK 11 o superior (para Kafka)

### Windows
- **Descarga**: https://adoptium.net/temurin/releases/
- **Seleccionar**:
  - Operating System: Windows
  - Architecture: x64
  - Package Type: JDK
  - Version: 11 (LTS) o superior
- **Tamaño**: ~180 MB

**Verificar instalación:**
```powershell
java -version
```

---

## 📨 Apache Kafka 3.6+ (Solo PC2)
**Versión requerida**: Kafka 3.6.1 o superior

### Descarga
- **Sitio oficial**: https://kafka.apache.org/downloads
- **Archivo recomendado**: kafka_2.13-3.6.1.tgz (Scala 2.13)
- **Tamaño**: ~100 MB

### Extracción en Windows
1. Descargar 7-Zip: https://www.7-zip.org/download.html
2. Extraer archivo .tgz con 7-Zip
3. Mover carpeta a: `C:\kafka\`

**Estructura final:**
```
C:\kafka\
├── bin\
│   └── windows\
├── config\
│   ├── kraft\
│   └── server.properties
└── libs\
```

---

## 📦 Dependencias Python
**Archivo**: `requirements.txt` (incluido en el proyecto)

### Instalación
```powershell
cd C:\SD
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Paquetes incluidos:
- **kafka-python** (2.0.2) - Cliente Kafka para Python
- **websockets** (12.0) - Servidor WebSocket
- **aiohttp** (3.9.1) - Servidor HTTP asíncrono
- **colorama** (0.4.6) - Colores en terminal (opcional)

**Tamaño total**: ~15 MB

---

## 🛠️ Herramientas Opcionales

### NSSM - Instalador de Servicios Windows (Opcional)
**Uso**: Para ejecutar Kafka como servicio de Windows

- **Descarga**: https://nssm.cc/download
- **Versión**: 2.24
- **Tamaño**: ~500 KB

**Instalación:**
1. Descargar nssm-2.24.zip
2. Extraer en: `C:\nssm\`
3. Usar: `C:\nssm\win64\nssm.exe`

### 7-Zip - Extractor de archivos
**Uso**: Para extraer archivos .tgz de Kafka

- **Descarga**: https://www.7-zip.org/download.html
- **Tamaño**: ~2 MB

---

## 📋 Resumen de Descargas por PC

### PC1 - EV_Driver
- ✅ Python 3.11+ (~25 MB)
- ✅ Proyecto EV_Charging (copiar desde PC original)

**Total**: ~25 MB + archivos del proyecto

### PC2 - EV_Central + Kafka
- ✅ Python 3.11+ (~25 MB)
- ✅ Java JDK 11+ (~180 MB)
- ✅ Apache Kafka 3.6+ (~100 MB)
- ✅ 7-Zip (~2 MB) - para extraer Kafka
- ⚪ NSSM (~500 KB) - opcional
- ✅ Proyecto EV_Charging (copiar desde PC original)

**Total**: ~307 MB + archivos del proyecto

### PC3 - EV_CP_M + EV_CP_E
- ✅ Python 3.11+ (~25 MB)
- ✅ Proyecto EV_Charging (copiar desde PC original)

**Total**: ~25 MB + archivos del proyecto

---

## 🔍 Verificación Post-Instalación

### En PC1 y PC3:
```powershell
# Verificar Python
python --version
# Salida esperada: Python 3.11.x o superior

# Verificar pip
pip --version
# Salida esperada: pip 23.x o superior
```

### En PC2 (adicional):
```powershell
# Verificar Java
java -version
# Salida esperada: openjdk version "11" o superior

# Verificar estructura de Kafka
dir C:\kafka\bin\windows
# Debe mostrar: kafka-server-start.bat, kafka-topics.bat, etc.
```

---

## 🌐 Enlaces Alternativos de Descarga

### Python (espejo)
- https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe

### Java OpenJDK (alternativas)
- **AdoptOpenJDK**: https://adoptopenjdk.net/
- **Oracle JDK**: https://www.oracle.com/java/technologies/downloads/

### Apache Kafka (espejo)
- https://archive.apache.org/dist/kafka/3.6.1/kafka_2.13-3.6.1.tgz
- https://dlcdn.apache.org/kafka/3.6.1/kafka_2.13-3.6.1.tgz

---

## 📄 Archivos del Proyecto a Copiar

### Desde PC Original a TODOS los PCs:
```
C:\SD\
├── database.py
├── event_utils.py
├── network_config.py
├── requirements.txt
└── ev_charging.db (después de inicializar en PC2)
```

### Específico para PC1:
```
EV_Driver\
├── EV_Driver.py
├── EV_Driver_WebSocket.py
└── dashboard.html
```

### Específico para PC2:
```
EV_Central\
├── EV_Central.py
├── EV_Central_WebSocket.py
└── admin_dashboard.html
init_db.py
```

### Específico para PC3:
```
EV_CP_M\
├── EV_CP_M.py
├── EV_CP_M_WebSocket.py
└── monitor_dashboard.html
EV_CP_E\
└── EV_CP_E.py
```

---

## 🎯 Orden de Instalación Recomendado

### 1️⃣ Instalar Software Base
1. **Python** en los 3 PCs (15 min)
2. **Java** solo en PC2 (10 min)
3. **7-Zip** en PC2 (2 min)

### 2️⃣ Instalar Kafka en PC2
1. Descargar Kafka (10 min)
2. Extraer en `C:\kafka\` (5 min)
3. Configurar y formatear (5 min)

### 3️⃣ Preparar Entornos Python
1. Copiar archivos del proyecto a cada PC (10 min)
2. Crear entornos virtuales (5 min por PC)
3. Instalar dependencias (5 min por PC)

### 4️⃣ Configurar Red
1. Obtener IPs (5 min)
2. Editar `network_config.py` (10 min)
3. Editar archivos HTML (5 min)
4. Configurar firewall (10 min)

**Tiempo total estimado**: 2-3 horas (según experiencia)

---

## 💾 Tamaños de Archivos

| Componente | Tamaño | PC1 | PC2 | PC3 |
|------------|--------|-----|-----|-----|
| Python 3.11 | 25 MB | ✅ | ✅ | ✅ |
| Java JDK 11 | 180 MB | ❌ | ✅ | ❌ |
| Apache Kafka | 100 MB | ❌ | ✅ | ❌ |
| 7-Zip | 2 MB | ❌ | ✅ | ❌ |
| Deps Python | 15 MB | ✅ | ✅ | ✅ |
| Proyecto | ~5 MB | ✅ | ✅ | ✅ |
| **TOTAL** | | **45 MB** | **327 MB** | **45 MB** |

---

## 🔒 Checksums (Opcional)

### Python 3.11.9 - Windows AMD64
- **SHA256**: `9c9e22af56d261787b41641048bcbce03a0fb8ded3b85f2e1cfee3ee57959e04`

### Kafka 3.6.1 - Scala 2.13
- **SHA512** (disponible en sitio oficial de Apache)

---

## 📞 Soporte

Si algún enlace no funciona:
1. Verificar la fecha de este documento
2. Buscar versiones actualizadas en sitios oficiales
3. Usar versiones compatibles (Python 3.11+, Java 11+, Kafka 3.6+)

---

**Última actualización**: 2024
**Versiones probadas**: Python 3.11.9, Java 11, Kafka 3.6.1
