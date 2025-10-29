# 🎓 GUÍA PARA LA CORRECCIÓN

## 📋 PREPARACIÓN ANTES DE LA CORRECCIÓN

### 1. Verificar que todo está funcionando

**PC2 (Central):**
```powershell
docker ps | Select-String "zookeeper\|kafka\|central"
# ✅ Deben aparecer 3 contenedores
```

**PC3 (CPs):**
```powershell
docker ps | Select-String "ev-cp"
# ✅ Deben aparecer 6 contenedores (3 engines + 3 monitors)
```

**PC1 (Driver):**
```powershell
docker ps | Select-String "ev-driver"
# ✅ Debe aparecer 1 contenedor
```

---

### 2. Preparar ventanas/terminales

**Abrir 4 terminales visibles:**

**Terminal 1 - Logs Central (PC2):**
```powershell
docker logs -f ev-central
```

**Terminal 2 - Logs Engine CP_001 (PC3):**
```powershell
docker logs -f ev-cp-engine-001
```

**Terminal 3 - Logs Monitor CP_001 (PC3):**
```powershell
docker logs -f ev-cp-monitor-001
```

**Terminal 4 - Logs Driver (PC1):**
```powershell
docker logs -f ev-driver
```

---

### 3. Abrir Dashboards en navegador

**Preparar pestañas del navegador:**
1. http://192.168.1.235:8002 → Central
2. http://192.168.1.100:8001 → Driver
3. http://192.168.1.150:5500 → Monitor CP_001

---

## 🎬 DEMOSTRACIÓN DURANTE LA CORRECCIÓN

### DEMO 1: Sistema Autónomo (Sin Interacción)

**Objetivo:** Mostrar que el sistema funciona sin intervención humana

**Ejecutar:**
```powershell
# En PC1
docker exec -it ev-driver bash
python EV_Driver/procesar_archivos.py EV_Driver/servicios.txt Juan
exit
```

**Señalar en las 4 terminales:**

1. **Terminal Driver:**
   ```
   [1/10] Solicitando carga en CP_001...
   ✅ Carga autorizada
   🔋 Progreso: X.X kWh, €X.XX
   ⏳ Esperando 4 segundos...
   [2/10] Solicitando carga en CP_002...
   ```

2. **Terminal Central:**
   ```
   [KAFKA] 📨 Received: AUTHORIZATION_REQUEST
   [CENTRAL] ✅ Autorización APROBADA para Juan → CP_001
   [CENTRAL] 📤 Comando charging_started enviado
   ```

3. **Terminal Engine:**
   ```
   [CP_001] ⚡ Iniciando carga para usuario: Juan
   [CP_001] 🔋 Progreso: 1.2 kWh, €0.36
   [CP_001] 🔋 Progreso: 2.5 kWh, €0.75
   ```

4. **Terminal Monitor:**
   ```
   [MONITOR-CP_001] ✅ Health check: Engine OK
   [MONITOR-CP_001] ✅ Health check: Engine OK
   (cada segundo)
   ```

**Señalar en Dashboards:**
- Dashboard Central: CP cambia de verde a amarillo (charging)
- Dashboard Driver: Progreso animado en tiempo real
- Dashboard Monitor: Sesión activa visible

**⏱️ Duración:** 2-3 minutos (procesando servicios)

**✅ PUNTO DEMOSTRADO:** Sistema completamente autónomo, observable sin interacción

---

### DEMO 2: Detección Automática de Fallos

**Objetivo:** Mostrar que Monitor detecta fallos automáticamente

**Preparación:**
```powershell
# En PC3, terminal aparte (Terminal 5)
docker attach ev-cp-engine-001
```

**Durante una carga activa, pulsar:**
```
[F] + Enter
```

**Señalar cascada de eventos (en 1-2 segundos):**

1. **Terminal Engine:**
   ```
   [CP_001] 🚨 SIMULATING HARDWARE FAILURE
   [CP_001] ⚠️  Health status set to KO
   [CP_001] 🛑 Sesión finalizada por fallo
   ```

2. **Terminal Monitor (1 segundo después):**
   ```
   [MONITOR-CP_001] ❌ Health check FAILED: Engine returned KO
   [MONITOR-CP_001] 📢 Reporting INCIDENT to Central
   [MONITOR-CP_001] 🚨 Engine Status: CRITICAL
   ```

3. **Terminal Central (inmediatamente):**
   ```
   [KAFKA] 📨 Received: INCIDENT
   [CENTRAL] ⚠️  INCIDENTE: CP_001 - Fallo de Engine (KO)
   [CENTRAL] 🔴 CP_001 marcado como 'fault'
   [CENTRAL] 📢 Notificando a conductor
   ```

4. **Terminal Driver:**
   ```
   [DRIVER] ⚠️  Carga interrumpida: Fallo de hardware
   [DRIVER] 🎫 Ticket parcial: X.X kWh, €X.XX
   ```

**Señalar en Dashboards:**
- Dashboard Central: CP_001 se pone 🔴 ROJO inmediatamente
- Dashboard Driver: Mensaje de interrupción
- Dashboard Monitor: Alerta roja de fallo

**Recuperar:**
```
[R] + Enter
```

**Señalar recuperación:**
- Monitor detecta OK en 1 segundo
- Central marca CP como AVAILABLE
- CP vuelve a verde en dashboards

**Salir del CLI:**
```
Ctrl+P, luego Ctrl+Q
```

**⏱️ Duración:** 1-2 minutos

**✅ PUNTOS DEMOSTRADOS:**
- Monitor supervisa cada segundo vía TCP
- Detección instantánea de fallos
- Reporte automático a Central
- Notificación a Driver
- Todo observable en terminales y dashboards

---

### DEMO 3: Despliegue Dinámico

**Objetivo:** Añadir un CP nuevo durante la ejecución

**Ejecutar en PC3:**

```powershell
# Definir nuevo CP
$CP_ID="CP_004"; $PORT=5103; $MPORT=5503

# Lanzar Engine
docker run -d --name ev-cp-engine-004 --network ev-network-pc3 -p "${PORT}:${PORT}" -v "${PWD}\ev_charging.db:/app/ev_charging.db" -v "${PWD}\network_config.py:/app/network_config.py" -v "${PWD}\database.py:/app/database.py" -v "${PWD}\event_utils.py:/app/event_utils.py" -it ev-cp-engine:latest python -u EV_CP_E.py --cp-id $CP_ID --location "Corrección Demo" --health-port $PORT --kafka-broker 192.168.1.235:9092

# Lanzar Monitor
docker run -d --name ev-cp-monitor-004 --network ev-network-pc3 -p "${MPORT}:${MPORT}" -v "${PWD}\ev_charging.db:/app/ev_charging.db:ro" -v "${PWD}\network_config.py:/app/network_config.py:ro" -v "${PWD}\database.py:/app/database.py:ro" -v "${PWD}\event_utils.py:/app/event_utils.py:ro" -v "${PWD}\EV_CP_M\monitor_dashboard.html:/app/monitor_dashboard.html:ro" ev-cp-monitor:latest python -u EV_CP_M_WebSocket.py --cp-id $CP_ID --engine-host ev-cp-engine-004 --engine-port $PORT --monitor-port $MPORT --kafka-broker 192.168.1.235:9092
```

**Señalar en Terminal Central (5 segundos después):**
```
[KAFKA] 📨 Received: CP_REGISTRATION
[CENTRAL] 💾 CP registrado: CP_004
[KAFKA] 📨 Received: MONITOR_AUTH
[CENTRAL] ✅ Monitor MONITOR-CP_004 authenticated
```

**Señalar en Dashboard Central:**
- CP_004 aparece inmediatamente en la lista
- Estado: 🟢 AVAILABLE

**Probar el nuevo CP desde Dashboard Driver:**
- Refrescar página
- Ver CP_004 en lista
- Solicitar carga en CP_004
- Funciona inmediatamente

**⏱️ Duración:** 30 segundos

**✅ PUNTOS DEMOSTRADOS:**
- Despliegue en caliente sin reiniciar sistema
- Auto-registro automático
- Parametrización total (CP_ID, puerto, ubicación)
- Sin editar código

---

### DEMO 4: Parametrización

**Objetivo:** Mostrar que NO hay valores hardcodeados

**Mostrar comandos usados anteriormente:**

```powershell
# Engine con parámetros personalizados
python EV_CP_E.py \
  --cp-id CP_005 \
  --location "Barcelona Centro" \
  --max-power 50 \
  --tariff 0.40 \
  --health-port 5200 \
  --kafka-broker 192.168.1.235:9092
```

**Señalar:**
- ✅ CP_ID parametrizable
- ✅ Ubicación parametrizable
- ✅ Potencia parametrizable
- ✅ Tarifa parametrizable
- ✅ Puerto parametrizable
- ✅ IP Kafka parametrizable

**Mostrar que funciona con cualquier valor:**
```powershell
# Central en otro puerto
python EV_Central_WebSocket.py --port 9000 --kafka-broker 192.168.1.235:9092

# Driver en otro puerto
python EV_Driver_WebSocket.py --port 8005 --kafka-broker 192.168.1.235:9092
```

**⏱️ Duración:** 1 minuto

**✅ PUNTO DEMOSTRADO:** Parametrización completa, sin recompilar

---

## 🎯 RESPUESTAS A PREGUNTAS FRECUENTES

### P: ¿Cómo se registra un CP nuevo?

**R:** Auto-registro al arrancar. Mostrar:
1. Engine arranca
2. Envía `CP_REGISTRATION` a Kafka automáticamente
3. Central lo recibe y registra en BD
4. Visible en logs y dashboard inmediatamente

---

### P: ¿Cómo detecta fallos el Monitor?

**R:** Health checks TCP cada segundo. Mostrar:
1. Monitor envía "STATUS?" vía TCP al Engine cada 1 segundo
2. Engine responde "OK" si funciona, "KO" si falla
3. Si no responde o responde KO → Monitor reporta incidente a Central
4. Central actualiza estado y notifica al Driver si hay carga activa

---

### P: ¿Cómo se autoriza una carga?

**R:** Validación multi-nivel en Central. Mostrar en logs:
```
[CENTRAL] 🔐 Validando solicitud...
[CENTRAL]   Usuario: Juan ✅ Existe
[CENTRAL]   Balance: €25.50 ✅ Suficiente (≥€5)
[CENTRAL]   Sesión activa: No ✅
[CENTRAL]   CP_001: available ✅
[CENTRAL] ✅ Autorización APROBADA
[CENTRAL] 📤 Comando charging_started enviado a CP_001
```

---

### P: ¿Dónde están los parámetros configurables?

**R:** Argumentos de línea de comandos. Mostrar:
```powershell
python EV_CP_E.py --help
python EV_Central_WebSocket.py --help
python EV_Driver_WebSocket.py --help
python EV_CP_M_WebSocket.py --help
```

Cada uno muestra todos sus parámetros configurables.

---

### P: ¿Cómo se observa el sistema sin interactuar?

**R:** Señalar las 4 terminales + 3 dashboards abiertos. Todo visible en tiempo real sin tocar nada.

---

## 📊 COMANDOS DE EMERGENCIA

### Si algo falla durante la demo:

**Reiniciar Central:**
```powershell
docker restart ev-central
```

**Reiniciar un CP:**
```powershell
docker restart ev-cp-engine-001 ev-cp-monitor-001
```

**Reiniciar Driver:**
```powershell
docker restart ev-driver
```

**Ver últimos logs:**
```powershell
docker logs --tail 50 ev-central
docker logs --tail 50 ev-cp-engine-001
```

**Limpiar y reiniciar todo:**
```powershell
# PC2
docker-compose -f docker-compose.pc2.yml restart

# PC3
docker-compose -f docker-compose.pc3.yml restart

# PC1
docker-compose -f docker-compose.pc1.yml restart
```

---

## ✅ CHECKLIST PRE-CORRECCIÓN

**Día anterior:**
- [ ] Verificar que Docker funciona en los 3 PCs
- [ ] Verificar IPs en `network_config.py`
- [ ] Construir todas las imágenes
- [ ] Probar despliegue completo al menos 1 vez
- [ ] Verificar que `servicios.txt` tiene 10 servicios
- [ ] Verificar que firewall permite puertos

**30 minutos antes:**
- [ ] Desplegar sistema completo (PC2 → PC3 → PC1)
- [ ] Verificar 3 CPs en Dashboard Central (verde)
- [ ] Probar una carga manual (Driver → CP_001)
- [ ] Probar fallo/recuperación con [F]/[R]
- [ ] Preparar 4 terminales + 3 pestañas navegador

**5 minutos antes:**
- [ ] Todos los contenedores activos (docker ps)
- [ ] Todas las terminales mostrando logs en tiempo real
- [ ] Todos los dashboards abiertos en navegador
- [ ] Tener preparado el comando de procesamiento por lotes

---

## 🎓 ORDEN RECOMENDADO DE DEMOS

1. **Sistema Autónomo** (2-3 min) → Impresiona más
2. **Detección de Fallos** (1-2 min) → Muestra robustez
3. **Despliegue Dinámico** (30 seg) → Muestra flexibilidad
4. **Parametrización** (1 min) → Cumple requisito técnico

**Tiempo total:** ~5 minutos

**Tiempo con explicaciones:** ~10 minutos

---

## 💡 TIPS PARA LA PRESENTACIÓN

1. **Preparar las 4 terminales en pantalla dividida** para que todo sea visible simultáneamente

2. **Usar Dashboard Central como "panel de control"** para mostrar estados en tiempo real

3. **Enfatizar el auto-registro y auto-detección** → "Sin intervención manual"

4. **Mostrar los logs mientras ocurren** → Más impactante que explicar después

5. **Si el profesor pide añadir un CP con ID específico:**
   ```powershell
   # Cambiar solo CP_ID y PORT
   $CP_ID="CP_PROFESOR"; $PORT=5999
   # Ejecutar comandos de DEMO 3
   ```

6. **Si algo falla, mantener la calma:**
   - Ver logs
   - Reiniciar contenedor específico
   - NO reiniciar todo el sistema

---

## 🎬 SCRIPT EJEMPLO

**"Voy a mostrar el sistema funcionando autónomamente. Ejecuto UN solo comando y observamos las 4 terminales simultáneamente:"**

```powershell
docker exec -it ev-driver python EV_Driver/procesar_archivos.py EV_Driver/servicios.txt Juan
```

**"Como pueden ver en las terminales:**
- **[Señalar Terminal Driver]** El Driver procesa 10 servicios secuencialmente
- **[Señalar Terminal Central]** Central autoriza cada solicitud automáticamente
- **[Señalar Terminal Engine]** El Engine reporta progreso cada segundo
- **[Señalar Terminal Monitor]** El Monitor supervisa el Engine cada segundo

**Y en los dashboards:**
- **[Señalar Dashboard Central]** El CP cambia de verde a amarillo (charging)
- **[Señalar Dashboard Driver]** El progreso se actualiza en tiempo real
- **[Señalar Dashboard Monitor]** La sesión activa es visible

**Todo esto sin ninguna otra interacción. El sistema se auto-gestiona completamente."**

---

**🎉 ¡Buena suerte en la corrección!**

