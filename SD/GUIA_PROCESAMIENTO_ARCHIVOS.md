# 📄 GUÍA: Procesamiento de Archivos de Servicios

## ✅ Funcionalidad Implementada

El sistema **SÍ CUMPLE** con el procesamiento de archivos de servicios para automatizar las pruebas.

---

## 📋 Formato de Archivos

Los archivos de servicios tienen el siguiente formato:

```
CP_001
CP_002
CP_003
CP_004
CP_005
```

**Una CP por línea**, sin comas ni espacios adicionales.

---

## 🎯 Cómo Usar

### Opción 1: Desde el Dashboard (Interfaz Web)

1. **Acceder al dashboard:**
   ```
   http://localhost:8001
   ```

2. **Login con un usuario:**
   - Usuario: `driver1`
   - Contraseña: `pass123`

3. **Seleccionar archivo:**
   - Click en "📄 Seleccionar archivo .txt"
   - Buscar `servicios.txt` (o `servicios2.txt`, `servicios3.txt`)
   - Seleccionar

4. **Configurar duración:**
   - Duración por CP (segundos): `2` (o el tiempo deseado)

5. **Procesar:**
   - Click en "Procesar archivo"

**Resultado:** El Driver procesará automáticamente cada CP:
- Inicia carga en CP_001
- Espera 2 segundos
- Detiene carga
- Inicia carga en CP_002
- Espera 2 segundos
- ... y así sucesivamente

### Opción 2: Desde Terminal (Script Auxiliar)

```bash
# Ver qué archivos hay disponibles
python EV_Driver/procesar_archivos.py

# Cargar un archivo específico
python EV_Driver/procesar_archivos.py servicios.txt user1
python EV_Driver/procesar_archivos.py servicios2.txt user2
```

---

## 📂 Archivos de Servicios Incluidos

El proyecto incluye 3 archivos con 10 servicios cada uno:

| Archivo | Descripción |
|---------|-------------|
| `servicios.txt` | 10 CPs (CP_001 a CP_010) |
| `servicios2.txt` | 10 CPs alternativos |
| `servicios3.txt` | 10 CPs adicionales |

**Total: 30 servicios disponibles para pruebas**

---

## 🔍 Ubicación del Código

### Frontend (HTML)

**Archivo:** `EV_Driver/dashboard.html`  
**Líneas:** 429-484

```javascript
function processServicesFile() {
    // Leer archivo
    const file = input.files[0];
    const reader = new FileReader();
    reader.onload = () => {
        const lines = String(reader.result).split(/\r?\n/);
        const cpIds = lines.map(cpIdFromLine).filter(Boolean);
        
        // Enviar a servidor
        ws.send(JSON.stringify({
            type: 'batch_charging',
            username: currentUser,
            cp_ids: cpIds,
            duration_sec: duration
        }));
    };
    reader.readAsText(file, 'utf-8');
}
```

### Backend (Python)

**Archivo:** `EV_Driver/EV_Driver_WebSocket.py`  
**Líneas:** 703-753

```python
elif msg_type == 'batch_charging':
    # Procesa una lista de CPs secuencialmente
    username = data.get('username')
    cp_ids = data.get('cp_ids') or []
    duration_sec = int(data.get('duration_sec') or 2)
    
    for cp_id in cp_ids:
        # Iniciar carga
        start_res = driver_instance.request_charging_at_cp(username, cp_id)
        
        # Esperar duración
        await asyncio.sleep(max(0, duration_sec))
        
        # Detener carga
        stop_res = driver_instance.stop_charging(username)
```

---

## ✅ Verificación del Punto 3

### Requisito:
> El archivo de servicios contendrá al menos 10 servicios para que se puedan hacer distintas pruebas durante la corrección sin interrupciones.

### Estado: ✅ CUMPLE

- ✅ Archivos con 10 servicios cada uno: `servicios.txt`, `servicios2.txt`, `servicios3.txt`
- ✅ Total: 30 servicios disponibles
- ✅ Interfaz funcional para cargar archivos
- ✅ Procesamiento automático implementado
- ✅ Sin interrupciones entre servicios

---

## 🧪 Prueba Rápida

1. **Iniciar el sistema:**
   ```powershell
   # En PC2
   docker-compose -f docker-compose.pc2.yml up -d
   
   # En PC1
   docker-compose -f docker-compose.pc1.yml up -d
   ```

2. **Acceder al dashboard:**
   ```
   http://<PC1_IP>:8001
   ```

3. **Login:**
   - Usuario: `driver1`
   - Contraseña: `pass123`

4. **Procesar archivo:**
   - Seleccionar `servicios.txt`
   - Duración: 2 segundos
   - Click "Procesar archivo"

5. **Observar:**
   - Consola del Driver muestra progreso
   - Cada CP se procesa secuencialmente
   - Sin interrupciones

---

## 📊 Output Esperado

En la terminal del Driver verás:

```
[DRIVER] 📄 Batch charging request: user=driver1, CPs=['CP_001', 'CP_002', ...], duration=2s
[DRIVER] ✅ Autorización recibida para CP_001
[DRIVER] 🔌 Carga iniciada en CP_001
[DRIVER] ⏹️  Carga detenida en CP_001: 0.25 kWh, €0.08
[DRIVER] 🔌 Carga iniciada en CP_002
[DRIVER] ⏹️  Carga detenida en CP_002: 0.50 kWh, €0.18
...
```

---

## ✅ CONCLUSIÓN

**El punto 3 SÍ está correctamente implementado:**

- ✅ Archivos con al menos 10 servicios
- ✅ Interfaz funcional para cargar archivos
- ✅ Procesamiento automático
- ✅ Sin interrupciones
- ✅ Múltiples archivos disponibles

**El sistema está listo para la corrección automatizada.**

---

*Documentación creada: 2025*  
*Archivos: servicios.txt, servicios2.txt, servicios3.txt*  
*Funcionalidad: Líneas 429-484 (HTML), 703-753 (Python)*

