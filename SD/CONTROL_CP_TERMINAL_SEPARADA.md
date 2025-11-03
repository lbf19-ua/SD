# 🎮 Control de CPs desde Terminal Separada

Para usar el menú de control de CPs en una terminal separada (sin mezclar con los logs del Engine), usa el script `cp_control.py`.

---

## 📋 Uso Básico

### **Menú Interactivo en Terminal Separada**

```powershell
# Desde el directorio SD/SD
cd SD/SD
python EV_CP_E/cp_control.py CP_001 --interactive
```

O simplemente:

```powershell
python EV_CP_E/cp_control.py CP_001
```

Esto abrirá un menú interactivo en esa terminal:

```
================================================================================
  🎮 CP CONTROL MENU - CP_001
================================================================================
  📡 Kafka Broker: 192.168.1.235:9092
  📋 Topic: central-events
================================================================================
  Commands available:
    [P] Plug in    - Simulate vehicle connection
    [U] Unplug     - Simulate vehicle disconnection (finishes charging)
    [F] Fault      - Simulate hardware failure
    [R] Recover    - Recover from failure
    [S] Status     - Show current CP status
    [Q] Quit       - Exit control menu
================================================================================

[CP_001] Command (P/U/F/R/S/Q):
```

---

## 🔧 Comandos Disponibles

### **P - Plug in (Enchufar)**
Simula que el conductor enchufa su vehículo al CP.

```powershell
python EV_CP_E/cp_control.py CP_001 plug
# O en el menú interactivo: presiona 'P'
```

### **U - Unplug (Desenchufar)**
Simula que el conductor desenchufa su vehículo. Finaliza la carga y envía el ticket.

```powershell
python EV_CP_E/cp_control.py CP_001 unplug
# O en el menú interactivo: presiona 'U'
```

### **F - Fault (Avería)**
Simula un fallo de hardware. El Monitor detectará el fallo y reportará a Central.

```powershell
python EV_CP_E/cp_control.py CP_001 fault
# O en el menú interactivo: presiona 'F'
```

### **R - Recover (Recuperar)**
Recupera el CP del fallo. Vuelve a estado operativo.

```powershell
python EV_CP_E/cp_control.py CP_001 recover
# O en el menú interactivo: presiona 'R'
```

### **S - Status (Estado)**
Muestra el estado actual del CP (se mostrará en los logs del Engine).

```powershell
python EV_CP_E/cp_control.py CP_001 status
# O en el menú interactivo: presiona 'S'
```

---

## 🌐 Ejemplos de Uso

### **1. Controlar CP desde PC1 o PC3**

```powershell
# Abrir terminal nueva
cd SD/SD
python EV_CP_E/cp_control.py CP_001 --interactive
```

### **2. Comando directo (sin menú)**

```powershell
# Enchufar vehículo
python EV_CP_E/cp_control.py CP_001 plug

# Desenchufar vehículo
python EV_CP_E/cp_control.py CP_001 unplug
```

### **3. Controlar múltiples CPs**

```powershell
# Terminal 1 - Controlar CP_001
python EV_CP_E/cp_control.py CP_001 --interactive

# Terminal 2 - Controlar CP_002
python EV_CP_E/cp_control.py CP_002 --interactive

# Terminal 3 - Controlar CP_003
python EV_CP_E/cp_control.py CP_003 --interactive
```

---

## ⚙️ Configuración

### **Kafka Broker por defecto**

El script usa el broker configurado en `network_config.py`. Para cambiarlo:

```powershell
# Usar variable de entorno
$env:KAFKA_BROKER = "192.168.1.XXX:9092"
python EV_CP_E/cp_control.py CP_001 --interactive

# O usar argumento
python EV_CP_E/cp_control.py CP_001 --interactive --kafka-broker 192.168.1.XXX:9092
```

---

## ✅ Ventajas

1. **Terminal separada**: No mezcla mensajes con los logs del Engine
2. **Control remoto**: Puedes controlar CPs desde cualquier PC que tenga acceso a Kafka
3. **No interfiere**: El Engine sigue funcionando normalmente sin mensajes del menú
4. **Múltiples terminales**: Puedes abrir una terminal por CP si quieres

---

## 📝 Notas

- El Engine en Docker tiene `--no-cli` activado para evitar mensajes en consola
- El menú interactivo usa Kafka para comunicarse con el Engine
- Todos los comandos se envían vía Kafka al topic `central-events`
- El Engine recibe los comandos y los procesa normalmente
