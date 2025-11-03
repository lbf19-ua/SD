# ✅ Verificación de Cumplimiento de Requisitos

Este documento verifica el cumplimiento de todos los puntos especificados en la práctica.

---

## 1. ✅ Central comprueba puntos de recarga al iniciar

**Requisito**: Al ejecutar o reiniciar, CENTRAL comprobará en su BD si ya tiene puntos de recarga disponibles registrados (con su ubicación) y los mostrará en su panel de monitorización y control en su estado correspondiente. Hasta que un punto de recarga no conecte con CENTRAL, esta no podrá conocer el estado real del punto. En ese caso, lo mostrará con el estado DESCONECTADO.

**Implementación**:
- ✅ `get_dashboard_data()` (línea 411): Obtiene todos los CPs de BD con `db.get_all_charging_points()`
- ✅ `set_all_cps_status_offline()` (línea 2240): Al iniciar, marca todos los CPs como 'offline'
- ✅ El dashboard muestra CPs con estado 'offline' hasta que se conecten
- ✅ Cuando un Engine se registra, Central actualiza su estado a 'available'

**Ubicación en código**: `EV_Central_WebSocket.py` líneas 411-565, 2240-2248

---

## 2. ✅ Central espera registro y autorización

**Requisito**: CENTRAL siempre estará a la espera de:
- a. Recibir peticiones de registro y alta de un nuevo punto de recarga.
- b. Recibir peticiones de autorización de un suministro.

**Implementación**:
- ✅ **a. Registro de CP**: `CP_REGISTRATION` (línea 1529): Central procesa eventos de registro desde Engines
- ✅ **a. Alta manual**: `register_cp` (línea 831): Central acepta registro manual desde dashboard admin
- ✅ **b. Autorización**: `AUTHORIZATION_REQUEST` (línea 1264): Central procesa solicitudes de autorización de Drivers

**Ubicación en código**: `EV_Central_WebSocket.py` líneas 831-1000 (registro), 1264-1330 (autorización)

---

## 3. ✅ Driver lee servicios desde archivo

**Requisito**: Los conductores pueden solicitar un suministro manualmente O leer los servicios de recarga a solicitar desde un archivo con formato:
```
<ID_CP>
<ID_CP>
…
```

**Implementación**:
- ✅ **Solicitud manual**: Función `requestCharging()` en `dashboard.html` (línea 404)
- ✅ **Lectura desde archivo**: Función `processServicesFile()` en `dashboard.html` (línea 446)
- ✅ **Procesamiento**: `batch_charging` en `EV_Driver_WebSocket.py` (línea 828-859)
- ✅ **Archivos de ejemplo**: `servicios.txt`, `servicios2.txt`, `servicios3.txt` en `EV_Driver/`

**Ubicación en código**: 
- `EV_Driver/dashboard.html` líneas 404-501
- `EV_Driver/EV_Driver_WebSocket.py` líneas 828-859

---

## 4. ✅ Central valida y solicita autorización

**Requisito**: CENTRAL procederá a realizar las comprobaciones oportunas para validar que el punto de recarga esté disponible y, en su caso, solicitará autorización al punto de recarga para que proceda al suministro. Todo el proceso requerirá de la notificación al conductor de los pasos que van sucediendo hasta autorizar o denegar el suministro. Dichos mensajes se deben mostrar claramente en pantalla, tanto en la aplicación del cliente como de CENTRAL.

**Implementación**:
- ✅ **Validación**: Central verifica que el CP existe y está 'available' (línea 1270-1313)
- ✅ **Autorización al CP**: Envía `charging_started` vía Kafka (línea 1715-1740)
- ✅ **Notificación al Driver**: Envía `AUTHORIZATION_RESPONSE` con mensajes claros (línea 1285-1330)
- ✅ **Mensajes en pantalla**: Dashboard de Driver muestra mensajes en tiempo real (líneas 507-650 en `dashboard.html`)
- ✅ **Mensajes en Central**: Logs detallados en consola (líneas 1264-1330)

**Ubicación en código**: `EV_Central_WebSocket.py` líneas 1264-1330, 1715-1740

---

## 5. ✅ CPs en estado de reposo esperando solicitudes

**Requisito**: Los puntos de recarga, una vez se han registrado y conectado a la central, estarán en estado de reposo a la espera de que un conductor solicite, bien en el propio interfaz del punto de recarga o a través de su aplicación, un suministro.

**Implementación**:
- ✅ **Estado 'available'**: Después de `CP_REGISTRATION`, el CP queda en estado 'available' (línea 281 en `EV_CP_E.py`)
- ✅ **Espera de comandos**: `listen_for_commands()` espera indefinidamente por mensajes de Kafka (línea 500-716)
- ✅ **Estado de reposo**: El CP no hace nada hasta recibir `charging_started` de Central

**Ubicación en código**: `EV_CP_E/EV_CP_E.py` líneas 281, 500-716

---

## 6. ✅ Notificación y enchufe del vehículo

**Requisito**: Realizadas todas las comprobaciones por la CENTRAL y enviada la notificación tanto al CP como a la aplicación del conductor (que lo verá en pantalla) para que procedan al suministro, el conductor enchufará su vehículo al CP.

**Implementación**:
- ✅ **Notificación al CP**: Central envía `charging_started` vía Kafka (línea 1715-1740)
- ✅ **Notificación al Driver**: Central envía `AUTHORIZATION_RESPONSE` con `authorized: true` (línea 1285-1330)
- ✅ **Mensajes en pantalla**: Dashboard de Driver muestra "Autorización concedida" (línea 507-650 en `dashboard.html`)
- ✅ **El conductor enchufa**: Se simula con menú del CP (requisito 7)

**Ubicación en código**: `EV_Central_WebSocket.py` líneas 1285-1330, 1715-1740

---

## 7. ✅ Menú CP para simular enchufe

**Requisito**: Para simular este acto en el cual un conductor enchufa su vehículo a un CP, el CP dispondrá de una opción de menú. Al ejecutar esta opción se entenderá que la conexión ha sido exitosa y empezará el suministro.

**Implementación**:
- ✅ **Método 1 - Menú CLI en terminal separada** (recomendado):
  - Script `cp_control.py` permite controlar CPs desde terminal separada
  - Ejecutar: `python EV_CP_E/cp_control.py CP_XXX --interactive`
  - Envía comandos vía Kafka, no genera mensajes en consola del Engine
  - Menú interactivo con comandos P/U/F/R/S/Q
  
- ✅ **Método 2 - Menú CLI integrado** (opcional, desactivado en Docker):
  - `start_cli_menu()` (línea 798-887 en `EV_CP_E.py`)
  - Comando 'P' (Plug in) en menú interactivo dentro del Engine
  - Se puede activar con `enable_cli` (pero no recomendado en Docker)
  - Se desactiva con `--no-cli` (usado en Docker por defecto)
  
- ✅ **Método 3 - Comando remoto vía Kafka** (automático):
  - Central puede enviar `CP_PLUG_IN` vía Kafka (línea 684-689 en `EV_CP_E.py`)
  - El Engine recibe el comando y ejecuta `simulate_plug_in()` (línea 689)
  - Se usa automáticamente cuando Central autoriza una carga
  
- ✅ **Inicio de suministro**: Cuando se ejecuta `simulate_plug_in()`, el CP cambia a 'charging' y envía `cp_status_change` (línea 727-750)

**Nota**: 
- En Docker se usa `--no-cli` para evitar que el menú CLI integrado genere mensajes en la consola del Engine.
- **Recomendado**: Usar `cp_control.py` en una terminal separada para controlar CPs sin interferir con los logs.
- El enchufe se simula automáticamente cuando Central autoriza una carga, o manualmente con `cp_control.py`.

**Ubicación en código**: 
- `EV_CP_E/cp_control.py` (menú en terminal separada - RECOMENDADO)
- `EV_CP_E/EV_CP_E.py` líneas 798-887 (menú CLI integrado), 682-689 (comando remoto), 727-750 (simulate_plug_in)
- `docker-compose.pc3.yml` línea 86 (`--no-cli` para desactivar CLI integrado)

---

## 8. ✅ Información constante durante suministro (cada segundo)

**Requisito**: Durante el suministro, el punto de recarga estará enviando información constante (cada segundo) a CENTRAL, la cual mostrará en su panel de monitorización el consumo e importes que va teniendo lugar en cada CP tal como se indicó en apartados anteriores. La aplicación del conductor igualmente mostrará esos estados del CP que le está suministrando.

**Implementación**:
- ✅ **Envío cada segundo**: `start_charging_simulation()` envía `charging_progress` cada segundo (línea 456, 469-477 en `EV_CP_E.py`)
- ✅ **Central recibe**: `charging_progress` procesado en `broadcast_kafka_event()` (línea 1995-2039)
- ✅ **Dashboard Central**: Muestra consumo e importes en tiempo real (línea 411-565 en `get_dashboard_data()`)
- ✅ **Dashboard Driver**: Muestra estados del CP que está suministrando (línea 507-650 en `dashboard.html`)

**Ubicación en código**: 
- `EV_CP_E/EV_CP_E.py` líneas 438-485 (simulación de carga)
- `EV_Central_WebSocket.py` líneas 1995-2039 (procesamiento)

---

## 9. ✅ Desenchufe y ticket final

**Requisito**: Finalizado el suministro mediante una opción de menú en el CP que simula el desenchufado del vehículo del CP, este lo notificará a CENTRAL quien a su vez enviará el "ticket" final al conductor. El CP volverá al estado de reposo a la espera de una nueva petición de suministro.

**Implementación**:
- ✅ **Menú desenchufe**: Comando 'U' (Unplug) en menú CLI (línea 817-819, 731-796 en `EV_CP_E.py`)
- ✅ **Notificación a Central**: `simulate_unplug()` envía `charging_completed` (línea 778-786)
- ✅ **Ticket al Driver**: Central procesa `charging_completed` y envía `CHARGING_TICKET` al Driver (línea 1867-1900)
- ✅ **Estado de reposo**: CP vuelve a 'available' después de desenchufe (línea 793)
- ✅ **Ticket visible**: Dashboard de Driver muestra el ticket final (línea 507-650 en `dashboard.html`)

**Ubicación en código**: 
- `EV_CP_E/EV_CP_E.py` líneas 731-796 (unplug)
- `EV_Central_WebSocket.py` líneas 1867-1900 (procesamiento y ticket)

---

## 10. ✅ Monitor comprueba salud y notifica averías

**Requisito**: Durante todo el funcionamiento del sistema, el punto de recarga, desde su módulo de monitorización estará comprobando el estado de salud del punto de recarga. En caso de avería, notificará a CENTRAL dicha situación. En caso de que la contingencia se resuelva, el monitor enviarán un nuevo mensaje a CENTRAL y el punto de recarga volverá a estar disponible. Si la avería se produjera durante un suministro, este debe finalizar inmediatamente informando a todos los módulos y aplicaciones de dicha situación. Toda la información tiene que ser claramente visible en pantalla tanto de CENTRAL como del monitor del punto de recarga.

**Implementación**:
- ✅ **Health checks cada segundo**: `tcp_health_check()` ejecuta health checks cada segundo (línea 929-1136 en `EV_CP_M_WebSocket.py`)
- ✅ **Detección de avería**: 3+ fallos consecutivos → `ENGINE_FAILURE` (línea 1039-1055)
- ✅ **Notificación a Central**: Monitor envía `ENGINE_FAILURE` o `ENGINE_OFFLINE` (línea 1041-1052)
- ✅ **Recuperación**: Monitor detecta cuando Engine vuelve a responder y envía notificación (línea 1072-1136)
- ✅ **Finalización durante suministro**: Central cancela sesión activa si hay avería (línea 2132-2210)
- ✅ **Notificación a todos**: Central notifica a Driver, Monitor y actualiza dashboards (línea 2193-2208)
- ✅ **Dashboard Monitor**: Muestra estado de salud y alertas (línea 693-715 en `monitor_dashboard.html`)
- ✅ **Dashboard Central**: Muestra estados de CPs y alertas (línea 411-565)

**Ubicación en código**: 
- `EV_CP_M/EV_CP_M_WebSocket.py` líneas 929-1136 (health checks)
- `EV_Central/EV_Central_WebSocket.py` líneas 2132-2210 (procesamiento de fallos)

---

## 11. ✅ Central recibe todo, Drivers solo su CP

**Requisito**: CENTRAL recibirá todos los estados y suministros de todos los CPs. Los conductores solo recibirán los mensajes del CP específico que les esté proporcionando un servicio pero también podrán ver todos los CPs que estén disponibles para suministrar.

**Implementación**:
- ✅ **Central recibe todo**: Central escucha todos los topics (`cp-events`, `driver-events`, `monitor-events`) (línea 32)
- ✅ **Driver solo su CP**: Driver filtra mensajes por `cp_id` en su sesión (línea 507-650 en `dashboard.html`)
- ✅ **Lista de CPs disponibles**: Dashboard de Driver muestra todos los CPs disponibles (línea 507-650 en `dashboard.html`)
- ✅ **Filtrado por cp_id**: Driver solo muestra detalles del CP que le está suministrando (línea 507-650)

**Ubicación en código**: 
- `EV_Central_WebSocket.py` línea 32 (topics)
- `EV_Driver/dashboard.html` líneas 507-650 (filtrado)

---

## 12. ✅ Espera 4 segundos entre servicios

**Requisito**: Cuando un suministro concluya, si dicho conductor precisa de otro servicio (tiene más registros en su fichero) el sistema esperará 4 segundos y procederá a solicitar un nuevo servicio.

**Implementación**:
- ✅ **Espera de 4 segundos**: `await asyncio.sleep(4)` después de completar un servicio (línea 1222, 1253, 1326, 1351 en `EV_Driver_WebSocket.py`)
- ✅ **Verificación de más servicios**: Comprueba si hay más CPs en el archivo (línea 1220-1223)
- ✅ **Solicitud automática**: Procede a solicitar el siguiente servicio automáticamente

**Ubicación en código**: `EV_Driver/EV_Driver_WebSocket.py` líneas 1220-1223, 1250-1253, 1324-1326, 1349-1351

---

## 13. ✅ Central puede parar/reanudar CPs

**Requisito**: CENTRAL permanecerá siempre en funcionamiento a la espera de nuevas peticiones de suministros. Adicionalmente dispondrá de opciones para, de forma arbitraria, poder enviar a uno o todos los CPs cualquiera de estas opciones:
- a. Parar: El CP finalizará cualquier suministro si estuviera en ejecución y pondrá su estado en ROJO mostrando el mensaje de "Fuera de Servicio".
- b. Reanudar: El CP volverá a estado ACTIVADO y pondrá su color en VERDE.

**Implementación**:
- ✅ **Central siempre funcionando**: Loop infinito de Kafka consumer (línea 1079-1428)
- ✅ **a. Parar CP**: `stop_cp` en dashboard admin (línea 789-855)
  - ✅ Finaliza suministro activo si existe (línea 814-821)
  - ✅ Cambia estado a 'out_of_service' (línea 826)
  - ✅ Envía `CP_STOP` vía Kafka (línea 829-834)
  - ✅ CP muestra "Fuera de Servicio" (línea 664-665 en `EV_CP_E.py`)
- ✅ **b. Reanudar CP**: `resume_cp` en dashboard admin (línea 857-920)
  - ✅ Cambia estado a 'available' (línea 895)
  - ✅ Envía `CP_RESUME` vía Kafka (línea 898-903)
  - ✅ CP vuelve a estado 'available' (línea 678-679 en `EV_CP_E.py`)
- ✅ **Uno o todos**: Soporta tanto CP individual como "todos los CPs" (línea 792-808, 864-889)

**Ubicación en código**: 
- `EV_Central/EV_Central_WebSocket.py` líneas 789-920 (parar/reanudar)
- `EV_CP_E/EV_CP_E.py` líneas 644-680 (procesamiento de comandos)

---

## ✅ Resumen de Cumplimiento

| Requisito | Estado | Ubicación en Código |
|-----------|--------|---------------------|
| 1. Central comprueba CPs al iniciar | ✅ | `EV_Central_WebSocket.py` líneas 411-565, 2240-2248 |
| 2. Central espera registro y autorización | ✅ | `EV_Central_WebSocket.py` líneas 831-1000, 1264-1330 |
| 3. Driver lee servicios desde archivo | ✅ | `EV_Driver/dashboard.html` líneas 404-501, `EV_Driver_WebSocket.py` líneas 828-859 |
| 4. Central valida y solicita autorización | ✅ | `EV_Central_WebSocket.py` líneas 1264-1330, 1715-1740 |
| 5. CPs en reposo esperando solicitudes | ✅ | `EV_CP_E/EV_CP_E.py` líneas 281, 500-716 |
| 6. Notificación y enchufe | ✅ | `EV_Central_WebSocket.py` líneas 1285-1330, 1715-1740 |
| 7. Menú CP para simular enchufe | ✅ | `EV_CP_E/EV_CP_E.py` líneas 682-689 (remoto vía Kafka), 798-887 (CLI opcional), 727-750 (simulate_plug_in) |
| 8. Información cada segundo durante suministro | ✅ | `EV_CP_E/EV_CP_E.py` líneas 438-485, `EV_Central_WebSocket.py` líneas 1995-2039 |
| 9. Desenchufe y ticket final | ✅ | `EV_CP_E/EV_CP_E.py` líneas 731-796, `EV_Central_WebSocket.py` líneas 1867-1900 |
| 10. Monitor comprueba salud y notifica | ✅ | `EV_CP_M/EV_CP_M_WebSocket.py` líneas 929-1136, `EV_Central_WebSocket.py` líneas 2132-2210 |
| 11. Central recibe todo, Drivers solo su CP | ✅ | `EV_Central_WebSocket.py` línea 32, `EV_Driver/dashboard.html` líneas 507-650 |
| 12. Espera 4 segundos entre servicios | ✅ | `EV_Driver/EV_Driver_WebSocket.py` líneas 1220-1223, 1250-1253 |
| 13. Central puede parar/reanudar CPs | ✅ | `EV_Central_WebSocket.py` líneas 789-920 |

---

## ✅ CONCLUSIÓN

**Todos los requisitos están implementados y funcionando correctamente.**

El sistema cumple con todos los puntos especificados:
- ✅ Central comprueba y muestra CPs al iniciar
- ✅ Central acepta registro y autorización
- ✅ Driver puede leer servicios desde archivo
- ✅ Central valida y autoriza suministros
- ✅ CPs esperan en reposo
- ✅ Notificaciones claras en pantalla
- ✅ Menú para simular enchufe/desenchufe
- ✅ Información constante cada segundo
- ✅ Ticket final al conductor
- ✅ Monitor comprueba salud y notifica averías
- ✅ Central recibe todo, Drivers solo su CP
- ✅ Espera 4 segundos entre servicios
- ✅ Central puede parar/reanudar CPs arbitrariamente

