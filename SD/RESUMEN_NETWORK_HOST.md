# 📚 Explicación: `network_mode: "host"`

## ¿Qué hace?

**Por defecto (sin `network_mode: "host"`):**
- Docker crea una red virtual aislada
- El contenedor tiene su propia IP (ej: `172.17.0.2`)
- Solo puede conectar a otros contenedores en la misma red Docker
- Para conectar al exterior, usa port mapping (ej: `8001:8001`)

**Con `network_mode: "host"`:**
- El contenedor usa DIRECTAMENTE la red del host
- Comparte la IP del PC físico
- Puede conectar directamente a IPs de la red local
- No necesita port mapping, expone puertos directamente

## Ejemplo Visual

### ❌ Sin network_mode: host
```
┌─────────────────────────────────────┐
│  PC del Usuario                     │
│  ┌───────────────────────────────┐  │
│  │ Red Docker (172.17.0.x)       │  │
│  │  ┌──────────────┐             │  │
│  │  │ Contenedor   │             │  │
│  │  │ IP: 172.17.0.2│             │  │
│  │  └──────────────┘             │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ Red Host (192.168.1.x)        │  │
│  │  IP: 192.168.1.235             │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
         ↓
   Kafka en 192.168.1.235:9092
   
   El contenedor NO puede conectar porque está en la red Docker
   (necesitaría salir por el gateway del contenedor)
```

### ✅ Con network_mode: host
```
┌─────────────────────────────────────┐
│  PC del Usuario                     │
│  ┌───────────────────────────────┐  │
│  │ Red Host (192.168.1.x)        │  │
│  │  IP: 192.168.1.235             │  │
│  │  ┌──────────────┐             │  │
│  │  │ Contenedor   │             │  │
│  │  │ (misma IP    │             │  │
│  │  │  del host)   │             │  │
│  │  └──────────────┘             │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
         ↓
   Kafka en 192.168.1.235:9092
   
   El contenedor SÍ puede conectar porque está en la misma red
```

## ¿Dónde Funciona?

- ✅ **Linux**: Funciona perfectamente
- ✅ **macOS**: Funciona, pero con algunas limitaciones
- ❌ **Windows**: NO funciona (ignorado por Docker Desktop)

## Solución para Windows

En Windows, `network_mode: "host"` es ignorado. Usamos:

1. **Port mapping normal** (`8001:8001`)
2. **Variables de entorno** para la configuración:
   ```yaml
   environment:
     - KAFKA_BROKER=192.168.1.235:9092
   ```

3. **El contenedor conecta usando la IP del otro PC directamente**

## Comparación

| Aspecto | Sin network_mode: host | Con network_mode: host |
|---------|----------------------|------------------------|
| IP del contenedor | `172.17.0.2` (privada) | `192.168.1.235` (misma que host) |
| Conectar a otro PC | ❌ Necesita routing especial | ✅ Directo |
| Exponer puertos | Mapear `8001:8001` | Directo (mismo que host) |
| Aislamiento | Total (más seguro) | Mínimo (mismo que host) |
| Uso típico | Desarrollo local | Networking avanzado |

## En Tu Caso

**Problema**: Driver en Windows no puede conectar a Kafka en `192.168.1.235:9092`

**Solución**: Configurar `KAFKA_BROKER=192.168.1.235:9092` en variables de entorno

**Archivo**: `docker-compose.pc1.yml` (líneas 39-43)

