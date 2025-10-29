# ⚡ GUÍA RÁPIDA DE DESPLIEGUE

## 📋 REQUISITOS PREVIOS

- ✅ Docker instalado en los 3 PCs
- ✅ Proyecto clonado en los 3 PCs
- ✅ Firewall configurado (puertos: 9092, 8000, 8001, 5500-5502)

---

## 🔧 PASO 1: CONFIGURAR IPs

**En los 3 PCs, editar `SD/network_config.py`:**

```python
PC1_IP = "192.168.1.XXX"  # IP de PC1 (Driver)
PC2_IP = "192.168.1.XXX"  # IP de PC2 (Kafka/Central)
PC3_IP = "192.168.1.XXX"  # IP de PC3 (CPs)
```

**Guardar el archivo.**

---

## 🚀 PASO 2: DESPLEGAR

### PC2 - Kafka + Central

```powershell
cd C:\Users\TU_USUARIO\Desktop\SD\SD
docker-compose -f docker-compose.pc2.yml build
docker-compose -f docker-compose.pc2.yml up -d
```

**Verificar:**
```powershell
docker ps
# Deben aparecer: zookeeper, kafka, ev-central
```

**Ver logs:**
```powershell
docker logs -f ev-central
# Buscar: "✅ Connected to Kafka successfully!"
```

---

### PC3 - CPs (Engines + Monitors)

```powershell
cd C:\Users\TU_USUARIO\Desktop\SD\SD
docker-compose -f docker-compose.pc3.yml build
docker-compose -f docker-compose.pc3.yml up -d
```

**Verificar:**
```powershell
docker ps
# Deben aparecer: 3 engines + 3 monitors (6 contenedores)
```

**Ver logs de un Engine:**
```powershell
docker logs ev-cp-engine-001
# Buscar: "✅ Auto-registro enviado a Central"
```

---

### PC1 - Driver

```powershell
cd C:\Users\TU_USUARIO\Desktop\SD\SD
docker-compose -f docker-compose.pc1.yml build
docker-compose -f docker-compose.pc1.yml up -d
```

**Verificar:**
```powershell
docker ps
# Debe aparecer: ev-driver
```

---

## ✅ PASO 3: VERIFICAR

### Abrir Dashboards:

```
http://192.168.1.235:8002  → Central (cambiar por tu IP de PC2)
http://192.168.1.100:8001  → Driver (cambiar por tu IP de PC1)
http://192.168.1.150:5500  → Monitor CP_001 (cambiar por tu IP de PC3)
```

### Dashboard Central debe mostrar:
- ✅ 3 CPs en verde (CP_001, CP_002, CP_003)
- ✅ Estado: AVAILABLE

### Dashboard Driver debe mostrar:
- ✅ Login de usuario
- ✅ Lista de 3 CPs disponibles

**Si ves esto, el sistema está funcionando correctamente.**

---

## 🧪 PASO 4: PROBAR

### Prueba 1: Solicitar carga

1. Abrir http://192.168.1.100:8001
2. Login con usuario "Juan"
3. Seleccionar CP_001
4. Clic en "Solicitar carga"
5. Resultado esperado: ✅ "Carga autorizada"
6. Ver progreso en tiempo real
7. Clic en "Detener carga"
8. Resultado: 🎫 Ticket con total

---

### Prueba 2: Observar en Central

- Abrir http://192.168.1.235:8002 mientras hay carga
- Ver CP en estado 🟡 CHARGING
- Ver sesión activa con kWh y € en tiempo real

---

### Prueba 3: CLI interactivo

```powershell
# En PC3
docker attach ev-cp-engine-001

# Dentro del CLI:
# [F] - Simular fallo
# [R] - Recuperar
# [S] - Ver estado
# Ctrl+P, Ctrl+Q - Salir sin detener
```

---

### Prueba 4: Procesamiento por lotes

```powershell
# En PC1
docker exec -it ev-driver bash
python EV_Driver/procesar_archivos.py EV_Driver/servicios.txt Juan

# Resultado: Procesa 10 servicios automáticamente
```

---

## 📊 COMANDOS ÚTILES

### Ver logs:
```powershell
docker logs -f ev-central
docker logs -f ev-cp-engine-001
docker logs -f ev-cp-monitor-001
docker logs -f ev-driver
```

### Ver estado:
```powershell
docker ps
docker ps -a
```

### Reiniciar:
```powershell
docker restart ev-central
docker restart ev-cp-engine-001 ev-cp-monitor-001
docker restart ev-driver
```

### Detener todo:
```powershell
# PC2
docker-compose -f docker-compose.pc2.yml down

# PC3
docker-compose -f docker-compose.pc3.yml down

# PC1
docker-compose -f docker-compose.pc1.yml down
```

---

## 🔥 TROUBLESHOOTING RÁPIDO

### CPs no aparecen en Central:
```powershell
# Ver logs de Engine
docker logs ev-cp-engine-001

# Ver logs de Central
docker logs ev-central | Select-String "CP_REGISTRATION"

# Reiniciar Engine
docker restart ev-cp-engine-001
```

### Driver no puede solicitar carga:
```powershell
# Ver razón en logs de Central
docker logs ev-central --tail 50 | Select-String "AUTHORIZATION"

# Razones comunes:
# - Usuario sin balance (necesita ≥ €5.00)
# - CP no disponible
# - Sesión activa previa
```

### Dashboard no carga:
```powershell
# Verificar contenedor está activo
docker ps | Select-String "central\|driver\|monitor"

# Verificar desde localhost primero
# En el mismo PC, abrir: http://localhost:8002

# Verificar firewall
Test-NetConnection -ComputerName 192.168.1.235 -Port 8000
```

---

## 📞 ORDEN DE ARRANQUE

**Siempre arrancar en este orden:**
1. **PC2** (Kafka + Central) → Esperar 10-15 segundos
2. **PC3** (CPs) → Esperar 5-10 segundos
3. **PC1** (Driver) → Listo

**Esperar entre cada paso para que Kafka esté disponible.**

---

## ✅ CHECKLIST FINAL

- [ ] PC2: 3 contenedores activos (zookeeper, kafka, ev-central)
- [ ] PC3: 6 contenedores activos (3 engines + 3 monitors)
- [ ] PC1: 1 contenedor activo (ev-driver)
- [ ] Dashboard Central muestra 3 CPs en verde
- [ ] Dashboard Driver muestra login y lista de CPs
- [ ] Logs de Central muestran "CP registrado" x3
- [ ] Logs de Central muestran "Monitor authenticated" x3
- [ ] Puedo solicitar y detener una carga correctamente

**Si todos los checks están OK, el sistema está desplegado correctamente.**

---

## 📄 DOCUMENTACIÓN COMPLETA

Para más detalles, ver: `GUIA_DESPLIEGUE_COMPLETA.md`

---

**🎉 ¡Sistema EV Charging desplegado en 3 PCs!**

