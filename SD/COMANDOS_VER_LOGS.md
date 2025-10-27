# 📺 CÓMO VER MENSAJES Y LOGS DEL SISTEMA

## 🎯 Opciones Disponibles

---

## 1. 📡 Kafka UI (Interfaz Web) - RECOMENDADO

**Acceso:**
```
http://<PC2_IP>:8080
```

**Ventajas:**
- ✅ Visualización gráfica de mensajes
- ✅ Ver topics, mensajes en tiempo real
- ✅ No requiere terminal
- ✅ Filtros y búsquedas

**Cómo usar:**
1. Abre en navegador: http://localhost:8080
2. Selecciona el cluster "ev-charging-cluster"
3. Ve a "Topics" → elige un topic (ej: driver-events)
4. Click en "Messages" para ver mensajes en tiempo real
5. Activa "Live Mode" para actualización continua

---

## 2. 🖥️ Terminal de Docker Compose (Por PC)

### PC2 (Central + Kafka)

```powershell
# Ver logs de TODOS los servicios
docker-compose -f docker-compose.pc2.yml logs -f

# Ver solo Kafka
docker-compose -f docker-compose.pc2.yml logs -f kafka-broker

# Ver solo Central
docker-compose -f docker-compose.pc2.yml logs -f ev-central

# Ver última hora de logs
docker-compose -f docker-compose.pc2.yml logs --since 1h -f
```

### PC1 (Driver)

```powershell
# Ver logs del Driver
docker-compose -f docker-compose.pc1.yml logs -f

# Últimas 100 líneas
docker-compose -f docker-compose.pc1.yml logs --tail=100 -f
```

### PC3 (Monitor)

```powershell
# Ver logs del Monitor
docker-compose -f docker-compose.pc3.yml logs -f
```

---

## 3. 🔍 Logs de Contenedores Individuales

### Ver logs de un contenedor específico:

```powershell
# Driver
docker logs ev-driver -f

# Central
docker logs ev-central -f

# Kafka Broker
docker logs ev-kafka-broker -f

# Kafka UI
docker logs ev-kafka-ui -f

# Monitor
docker logs ev-monitor -f
```

### Últimas N líneas:

```powershell
docker logs ev-driver --tail=50
docker logs ev-central --tail=50
```

---

## 4. 📊 Kafka Console (Ver Mensajes Directamente)

### Ver mensajes desde el principio:

```powershell
# Desde PC2
docker exec ev-kafka-broker kafka-console-consumer.sh --bootstrap-server localhost:29092 --topic driver-events --from-beginning

# Ver mensajes nuevos solamente
docker exec ev-kafka-broker kafka-console-consumer.sh --bootstrap-server localhost:29092 --topic driver-events

# Ver mensajes de cp-events
docker exec ev-kafka-broker kafka-console-consumer.sh --bootstrap-server localhost:29092 --topic cp-events --from-beginning

# Ver TODOS los topics
docker exec ev-kafka-broker kafka-console-consumer.sh --bootstrap-server localhost:29092 --topic "#" --from-beginning
```

---

## 5. 🎬 Script Todo-en-Uno

Crear archivo `ver_logs.ps1`:

```powershell
# ver_logs.ps1
param(
    [string]$Service = "all"
)

Write-Host "🔍 Mostrando logs de: $Service" -ForegroundColor Cyan
Write-Host ""

switch ($Service) {
    "kafka" {
        docker logs ev-kafka-broker -f
    }
    "central" {
        docker logs ev-central -f
    }
    "driver" {
        docker logs ev-driver -f
    }
    "monitor" {
        docker logs ev-monitor -f
    }
    "all" {
        # Abrir 4 terminales con los logs
        Start-Process powershell -ArgumentList "-Command", "docker logs ev-driver -f"
        Start-Process powershell -ArgumentList "-Command", "docker logs ev-central -f"
        Start-Process powershell -ArgumentList "-Command", "docker logs ev-monitor -f"
        Start-Process powershell -ArgumentList "-Command", "docker logs ev-kafka-broker -f"
    }
}
```

**Uso:**
```powershell
.\ver_logs.ps1 driver   # Ver solo Driver
.\ver_logs.ps1 all      # Abrir todos
```

---

## 📋 RESUMEN RÁPIDO

### Opción 1: Kafka UI (Más fácil) ✅
```
http://localhost:8080
```
- No necesita terminal
- Visualización gráfica
- Ver mensajes en tiempo real

### Opción 2: Docker Compose Logs
```powershell
docker-compose -f docker-compose.pc2.yml logs -f
```
- Ver TODO en una terminal
- Incluye todas las salidas

### Opción 3: Docker Logs Individual
```powershell
docker logs ev-driver -f
```
- Solo un servicio
- Más limpio y enfocado

### Opción 4: Kafka Console
```powershell
docker exec ev-kafka-broker kafka-console-consumer.sh --bootstrap-server localhost:29092 --topic driver-events --from-beginning
```
- Ver mensajes RAW de Kafka
- Exactamente lo que se publica

---

## 🎯 RECOMENDACIÓN

**Para la corrección:**

1. **Kafka UI:** Para ver flujo de mensajes
   ```
   http://PC2_IP:8080
   ```

2. **Terminal Central:** Para ver procesamiento
   ```powershell
   docker logs ev-central -f
   ```

3. **Terminal Driver:** Para ver solicitudes
   ```powershell
   docker logs ev-driver -f
   ```

**Esto te dará visibilidad completa del sistema.**

