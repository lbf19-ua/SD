# 🔧 Demostración de Parametrización en Central

Este documento explica cómo comprobar que **Central está completamente parametrizado** y **NO requiere recompilación** para cambiar parámetros.

## ✅ Parámetros Configurables en Central

Central permite configurar los siguientes parámetros **SIN MODIFICAR EL CÓDIGO**:

### 1. **Puerto del Servidor WebSocket** (`SERVER_PORT`)
- **Variable de entorno**: `CENTRAL_PORT`
- **Argumento de línea de comandos**: `--port`
- **Valor por defecto**: `8002` (desde `network_config.py`)

### 2. **Kafka Broker** (`KAFKA_BROKER`)
- **Variable de entorno**: `KAFKA_BROKER`
- **Argumento de línea de comandos**: `--kafka-broker`
- **Valor por defecto**: IP de PC2 desde `network_config.py`

### 3. **Topics de Kafka**
- Configurados en `network_config.py` (se pueden modificar sin tocar código)

---

## 📋 Cómo Comprobar la Parametrización

### **Prueba 1: Cambiar Puerto usando Variable de Entorno**

**Antes de ejecutar:**
```powershell
# Verificar que Central NO está corriendo
docker ps | Select-String "ev-central"

# Si está corriendo, detenerlo
docker stop ev-central
```

**Cambiar puerto sin modificar código:**
```powershell
# Establecer variable de entorno con nuevo puerto
$env:CENTRAL_PORT = "9000"

# Iniciar Central (usará el puerto 9000)
cd SD/SD
python EV_Central/EV_Central_WebSocket.py
```

**Verificar que funciona:**
- Abrir navegador en: `http://localhost:9000`
- Debe mostrar el dashboard admin
- **NO se modificó ningún archivo de código**

**Detener y volver al puerto por defecto:**
```powershell
# Ctrl+C para detener
# Eliminar variable de entorno
Remove-Item Env:\CENTRAL_PORT

# Iniciar de nuevo (usará puerto por defecto 8002)
python EV_Central/EV_Central_WebSocket.py
```

---

### **Prueba 2: Cambiar Puerto usando Argumento de Línea de Comandos**

```powershell
# Iniciar Central en puerto 7000 directamente
python EV_Central/EV_Central_WebSocket.py --port 7000
```

**Verificar:**
- Dashboard debe estar en: `http://localhost:7000`
- **NO se modificó ningún archivo de código**

---

### **Prueba 3: Cambiar Kafka Broker usando Variable de Entorno**

```powershell
# Supongamos que Kafka está en otra IP
$env:KAFKA_BROKER = "192.168.1.100:9092"

# Iniciar Central
python EV_Central/EV_Central_WebSocket.py
```

**Verificar en los logs:**
```
[CENTRAL] ✅ Kafka producer initialized
[CENTRAL] 🔌 Consumer configured and ready. Entering message loop...
  📡 Kafka Broker:     192.168.1.100:9092
```

**NO se modificó ningún archivo de código**

---

### **Prueba 4: Cambiar Kafka Broker usando Argumento de Línea de Comandos**

```powershell
# Iniciar Central con Kafka en otra IP
python EV_Central/EV_Central_WebSocket.py --kafka-broker 192.168.1.200:9092
```

**Verificar en los logs:**
```
  📡 Kafka Broker:     192.168.1.200:9092
```

---

### **Prueba 5: Cambiar Ambos Parámetros Simultáneamente**

```powershell
# Cambiar puerto y Kafka broker al mismo tiempo
python EV_Central/EV_Central_WebSocket.py --port 6000 --kafka-broker 192.168.1.150:9092
```

**Verificar en los logs:**
```
================================================================================
  🏢 EV CENTRAL - Sistema Central de Gestión
================================================================================
  WebSocket Port:  6000
  Kafka Broker:    192.168.1.150:9092
  Dashboard:       http://localhost:6000
================================================================================
```

---

### **Prueba 6: Usar Docker con Variables de Entorno**

**Modificar `docker-compose.pc2.yml` temporalmente:**

```yaml
  ev-central:
    # ... otras configuraciones ...
    ports:
      - "9000:9000"  # Cambiar puerto expuesto
    environment:
      - CENTRAL_PORT=9000  # Cambiar puerto interno
      - KAFKA_BROKER=broker:29092
      - PYTHONUNBUFFERED=1
```

**Reiniciar:**
```powershell
docker-compose -f docker-compose.pc2.yml up -d ev-central
```

**Verificar:**
- Dashboard debe estar en: `http://localhost:9000`
- **Solo se modificó docker-compose.yml, NO el código Python**

---

## 🎯 Verificación para la Evaluación

### **Secuencia de Demostración Recomendada:**

1. **Mostrar el código fuente** (líneas 31, 34, 2455-2465):
   ```python
   # Línea 31: Kafka Broker desde variable de entorno
   KAFKA_BROKER = os.environ.get('KAFKA_BROKER', KAFKA_BROKER_DEFAULT)
   
   # Línea 34: Puerto desde variable de entorno
   SERVER_PORT = int(os.environ.get('CENTRAL_PORT', CENTRAL_CONFIG['ws_port']))
   
   # Líneas 2455-2465: Argumentos de línea de comandos
   parser.add_argument('--port', ...)
   parser.add_argument('--kafka-broker', ...)
   ```

2. **Ejecutar Central con parámetros por defecto:**
   ```powershell
   python EV_Central/EV_Central_WebSocket.py
   ```
   - Mostrar que funciona en puerto 8002

3. **Detener Central** (Ctrl+C)

4. **Cambiar puerto SIN modificar código:**
   ```powershell
   python EV_Central/EV_Central_WebSocket.py --port 9000
   ```
   - Mostrar que funciona en puerto 9000
   - **No se modificó ningún archivo**

5. **Cambiar Kafka Broker SIN modificar código:**
   ```powershell
   python EV_Central/EV_Central_WebSocket.py --kafka-broker 192.168.1.XXX:9092
   ```
   - Mostrar en logs que usa el nuevo broker
   - **No se modificó ningún archivo**

6. **Demostrar que funciona con Docker:**
   ```powershell
   # Mostrar docker-compose.pc2.yml
   # Mostrar que las variables de entorno están configuradas
   docker-compose -f docker-compose.pc2.yml config
   ```

---

## ✅ Checklist de Verificación

- [ ] **Puerto configurable**: Cambiar `--port` o `CENTRAL_PORT` funciona sin modificar código
- [ ] **Kafka Broker configurable**: Cambiar `--kafka-broker` o `KAFKA_BROKER` funciona sin modificar código
- [ ] **Valores por defecto**: Si no se especifican parámetros, usa valores de `network_config.py`
- [ ] **Prioridad correcta**: Argumentos de línea de comandos > Variables de entorno > Valores por defecto
- [ ] **Sin hardcodeos**: No hay valores fijos como `localhost:9092` o `8002` directamente en el código de inicialización
- [ ] **Funciona en Docker**: Las variables de entorno en `docker-compose.yml` funcionan correctamente

---

## 📝 Notas Importantes

1. **No hay valores hardcodeados críticos**: Los únicos valores fijos son defaults que se pueden sobrescribir
2. **network_config.py es configurable**: Se puede modificar sin tocar el código principal
3. **Docker permite parametrización**: Las variables de entorno en docker-compose funcionan perfectamente
4. **Sin recompilación**: Python es interpretado, no necesita compilación, pero el requisito es que NO se modifique el código fuente

---

## 🔍 Puntos Clave para el Evaluador

1. **Muestre el código fuente** (líneas 31, 34, 2455-2465) para demostrar que usa `os.environ.get()` y `argparse`
2. **Ejecute Central con diferentes parámetros** sin modificar archivos
3. **Muestre que los cambios funcionan** accediendo al dashboard en el nuevo puerto
4. **Demuestre que Kafka funciona** con diferentes brokers configurados
5. **Explique la prioridad**: Argumentos CLI > Variables de entorno > Valores por defecto

---

## 🚀 Comandos Rápidos para la Demostración

```powershell
# 1. Puerto por defecto
python EV_Central/EV_Central_WebSocket.py

# 2. Cambiar puerto
python EV_Central/EV_Central_WebSocket.py --port 9000

# 3. Cambiar Kafka broker
python EV_Central/EV_Central_WebSocket.py --kafka-broker 192.168.1.XXX:9092

# 4. Cambiar ambos
python EV_Central/EV_Central_WebSocket.py --port 7000 --kafka-broker 192.168.1.XXX:9092

# 5. Con variables de entorno
$env:CENTRAL_PORT = "6000"
$env:KAFKA_BROKER = "192.168.1.XXX:9092"
python EV_Central/EV_Central_WebSocket.py
```

---

**✅ CONCLUSIÓN**: Central está **completamente parametrizado** y **NO requiere modificar el código fuente** para cambiar puertos, IPs de Kafka, o cualquier otro parámetro de configuración.

