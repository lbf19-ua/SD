# 🔋 EV CHARGING SYSTEM - GUÍA DE DESPLIEGUE EN RED LOCAL

## 📋 Configuración de Red

### Paso 1: Identificar IPs de cada PC
En cada PC, ejecuta en PowerShell:
```bash
ipconfig
```

### Paso 2: Modificar network_config.py
Edita el archivo `network_config.py` con las IPs reales:

```python
# PC1 - EV_Driver 
PC1_IP = "192.168.1.XXX"  # IP del PC donde estará EV_Driver

# PC2 - EV_Central (servidor principal)
PC2_IP = "192.168.1.227"  # IP donde ejecutarás EV_Central  

# PC3 - EV_CP (Monitor & Engine)
PC3_IP = "192.168.1.XXX"  # IP del PC donde estarán Monitor y Engine
```

## 🚀 Despliegue por PC

### **PC2 (Servidor Central) - IP: 192.168.1.227**
```bash
cd c:\Users\luisb\Desktop\SD\SD
python EV_Central/EV_Central.py
```
**IMPORTANTE**: Este PC debe ejecutarse PRIMERO

### **PC1 (Driver)**
1. Copiar toda la carpeta del proyecto a PC1
2. Modificar `network_config.py` con las IPs correctas
3. Ejecutar:
```bash
python EV_Driver/EV_Driver.py
```

### **PC3 (Charging Point)**
1. Copiar toda la carpeta del proyecto a PC3
2. Modificar `network_config.py` con las IPs correctas
3. Ejecutar Monitor:
```bash
python EV_CP_M/EV_CP_M.py
```
4. Ejecutar Engine (en otra terminal):
```bash
python EV_CP_E/EV_CP_E.py
```

## 🔧 Configuración de Firewall

**EN TODOS LOS PCs**, asegúrate de que el puerto 5000 esté abierto:

### Windows Defender Firewall:
1. Panel de Control → Sistema y seguridad → Firewall de Windows Defender
2. Configuración avanzada → Reglas de entrada → Nueva regla
3. Puerto → TCP → Puerto específico: 5000
4. Permitir la conexión
5. Aplicar a todos los perfiles

## 🧪 Pruebas

### Prueba de Conectividad:
Desde PC1 y PC3, prueba si puedes hacer ping al servidor:
```bash
ping 192.168.1.227
```

### Orden de Ejecución:
1. **PC2**: Ejecutar EV_Central
2. **PC1**: Ejecutar EV_Driver  
3. **PC3**: Ejecutar EV_CP_M y EV_CP_E

## 📱 Contacto entre Componentes

- **EV_Driver** (PC1) → **EV_Central** (PC2)
- **EV_CP_M** (PC3) → **EV_Central** (PC2)  
- **EV_CP_E** (PC3) → **EV_Central** (PC2)

## 🐛 Solución de Problemas

### Error "Connection Refused":
- Verificar que EV_Central está ejecutándose
- Comprobar IPs en network_config.py
- Verificar firewall/puertos

### Error "Network Unreachable":
- Verificar que todos los PCs están en la misma red
- Probar conectividad con ping

### Error "Import network_config":
- Verificar que network_config.py está en la carpeta raíz del proyecto
- Verificar que las IPs están configuradas correctamente