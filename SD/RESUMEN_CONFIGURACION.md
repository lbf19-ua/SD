# 📋 Resumen de Configuración para Despliegue 2 PCs

## 🖥️ ESTE PC (PC2 - Central)

### Información:
- **IP:** `192.168.1.235`
- **Estado:** ✅ Central ya está desplegado
- **Interfaces accesibles:**
  - http://localhost:8002 → Admin Dashboard
  - http://localhost:8080 → Kafka UI
  - http://localhost:5000 → Central Server API

### Servicios corriendo:
```powershell
# Verificar estado
docker ps

# Deberías ver:
# - ev-central (puerto 8002)
# - ev-kafka-broker (puerto 9092)
# - ev-kafka-ui (puerto 8080)
```

### Próximos pasos:
1. ✅ Firewall configurado (script ejecutado)
2. ⏳ Esperar a que el otro PC se conecte

---

## 🖥️ OTRO PC (PC1/PC3 - Driver + Monitor)

### Instrucciones para el otro PC:

#### 1️⃣ Obtener su IP
```powershell
ipconfig
# Cópiala: ejemplo 192.168.1.228
```

#### 2️⃣ Editar `SD/network_config.py`

```python
# Cambiar estas líneas:
PC2_IP = "192.168.1.235"  # ✅ IP del PC Central (ESTE PC)

PC1_IP = "192.168.1.228"  # ⚠️ IP del otro PC (cambiar)
PC3_IP = "192.168.1.228"  # ⚠️ Mismo que PC1
```

#### 3️⃣ Desplegar contenedores
```powershell
cd SD
docker-compose -f docker-compose.pc1.yml up -d --build
docker-compose -f docker-compose.pc3.yml up -d --build
```

#### 4️⃣ Verificar logs
```powershell
docker logs ev-driver --tail=30
docker logs ev-monitor --tail=30
```

---

## 🧪 Verificar Conectividad

### En el otro PC, ejecuta:
```powershell
# Ping al PC Central
ping 192.168.1.235

# Si funciona: ✅ Red OK
# Si no funciona: ⚠️ Verificar que están en la misma red Wi-Fi/LAN
```

---

## 🌐 URLs de Acceso

### En ESTE PC:
- **Admin Dashboard:** http://localhost:8002
- **Kafka UI:** http://localhost:8080

### En el OTRO PC:
- **Driver Dashboard:** http://localhost:8001
- **Monitor Dashboard:** http://localhost:8003
- **Admin Dashboard (remoto):** http://192.168.1.235:8002
- **Kafka UI (remoto):** http://192.168.1.235:8080

---

## 📊 Flujo de Mensajes

```
OTRO PC                      ESTE PC (Central)
┌─────────┐                  ┌─────────────┐
│ Driver  │ ───Kafka──>     │   Kafka     │
│         │ <──events───    │   Broker    │
└─────────┘                  │             │
                             │   Central   │
┌─────────┐                  │   (Admin)   │
│ Monitor │ <──events───    │             │
│         │ ───Kafka──>     └─────────────┘
└─────────┘
```

---

## ✅ Checklist de Verificación

### En ESTE PC (Central):
- [x] Docker instalado
- [x] Contenedores corriendo
- [x] Base de datos inicializada
- [x] Firewall configurado
- [ ] Esperando conexión del otro PC

### En el OTRO PC (Driver + Monitor):
- [ ] Obtuvo su IP
- [ ] Editó `network_config.py`
- [ ] Desplegó contenedores
- [ ] Logs sin errores
- [ ] Puede ver Admin Dashboard remoto

---

## 🐛 Troubleshooting

### Error: "NoBrokersAvailable" (otro PC)
**Solución:** Verificar que el firewall está abierto en ESTE PC:
```powershell
# En ESTE PC, ejecutar como Admin:
.\configurar_firewall.ps1
```

### Contenedores reiniciándose (otro PC)
**Solución:** Verificar que la IP en `network_config.py` es correcta

### No se ven mensajes en Kafka UI
**Solución:** Verificar que Kafka está corriendo:
```powershell
docker logs ev-kafka-broker
```

---

## 🎯 Prueba Completa

1. Abrir **Monitor Dashboard** en otro PC → Registrar CP
2. Abrir **Admin Dashboard** en ESTE PC → Ver CP aparecer
3. Abrir **Driver Dashboard** en otro PC → Solicitar servicio
4. Abrir **Kafka UI** en ESTE PC → Ver mensajes fluir
5. ✅ Sistema funcionando!

---

## 📞 Archivos de Ayuda

- `INSTRUCCIONES_DESPLIEGUE_2_PCS.md` → Guía completa
- `PASOS_RAPIDOS_OTRO_PC.md` → Instrucciones paso a paso
- `GUIA_DESPLIEGUE_2_PCS.md` → Guía anterior

---

¡Listo para el despliegue! 🚀

