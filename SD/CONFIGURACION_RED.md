# 🌐 CONFIGURACIÓN DE RED - GUÍA RÁPIDA

## 📋 PASO 1: Obtener las IPs

En **CADA PC**, abre terminal y ejecuta:

```powershell
ipconfig  # Windows
```

Busca esta línea:
```
   IPv4 Address. . . . . . : 192.168.1.50  ← Esta es tu IP
```

Anota las 3 IPs:
- **PC1 (Driver)**: _________________
- **PC2 (Central + Kafka)**: _________________
- **PC3 (Monitor)**: _________________

⚠️ **Las 3 IPs deben estar en la MISMA red** (ejemplo: 192.168.1.xxx)

---

## ✏️ PASO 2: Editar network_config.py

Abre el archivo `network_config.py` con cualquier editor de texto y busca estas líneas:

```python
# ==== CONFIGURACIÓN DE IPS POR PC ====

PC1_IP = "192.168.1.10"  # ⚠️ CAMBIAR por la IP real del PC1
PC2_IP = "192.168.1.20"  # ⚠️ CAMBIAR por la IP real del PC2
PC3_IP = "192.168.1.30"  # ⚠️ CAMBIAR por la IP real del PC3
```

**Reemplaza** los valores con tus IPs reales. Por ejemplo:

```python
PC1_IP = "192.168.1.50"  # IP del PC1 (Driver)
PC2_IP = "192.168.1.51"  # IP del PC2 (Central + Kafka)
PC3_IP = "192.168.1.52"  # IP del PC3 (Monitor)
```

**Guarda el archivo.** ✅

---

## � PASO 3: Iniciar el Sistema

### En PC2 (PRIMERO):

```powershell
# Inicializar base de datos (solo primera vez)
python init_db.py

# Iniciar Docker
docker-compose -f docker-compose.pc2.yml up -d --build
```

### En PC1:

```powershell
# Copiar ev_charging.db desde PC2 a esta carpeta SD/

# Iniciar Docker
docker-compose -f docker-compose.pc1.yml up -d --build
```

### En PC3:

```powershell
# Copiar ev_charging.db desde PC2 a esta carpeta SD/

# Iniciar Docker
docker-compose -f docker-compose.pc3.yml up -d --build
```

---

## ✅ VERIFICACIÓN

Abre un navegador en **CUALQUIER PC** y accede a:

- **Kafka UI**: http://\<PC2_IP\>:8080
- **Admin Dashboard**: http://\<PC2_IP\>:8002
- **Driver Dashboard**: http://\<PC1_IP\>:8001
- **Monitor Dashboard**: http://\<PC3_IP\>:8003

Si todo funciona, **¡listo!** 🎉

---

## 🛠️ TROUBLESHOOTING

### ❌ No puedo conectar entre PCs

```powershell
# Verificar conectividad
ping <IP_del_otro_PC>

# Probar puerto específico
Test-NetConnection <IP_del_PC2> -Port 9092
```

### ❌ Kafka no conecta

1. Verifica que `network_config.py` tiene las IPs correctas
2. Verifica que PC2 esté ejecutándose primero
3. Reinicia contenedores de PC1/PC3

### 🔥 Firewall bloquea conexiones

Si tienes problemas de conectividad, puedes:

**Opción 1: Desactivar temporalmente** (más fácil para pruebas):
```powershell
# Como Administrador
Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled False
```

**Opción 2: Abrir puertos específicos** (más seguro):
```powershell
# Como Administrador
# En PC1:
New-NetFirewallRule -DisplayName "EV Driver" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow

# En PC2:
New-NetFirewallRule -DisplayName "EV Central" -Direction Inbound -LocalPort 5000,8002,8080,9092 -Protocol TCP -Action Allow

# En PC3:
New-NetFirewallRule -DisplayName "EV Monitor" -Direction Inbound -LocalPort 8003 -Protocol TCP -Action Allow
```

---

## 📚 MÁS INFORMACIÓN

Para la guía completa y detallada, ver:
- **[GUIA_COMPLETA_DESPLIEGUE.md](GUIA_COMPLETA_DESPLIEGUE.md)**

---

**¡Eso es todo! Solo 3 pasos simples.** 🚀
