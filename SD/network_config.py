# ============================================================================
# Configuración de Red para Despliegue Multi-PC con Kafka
# ============================================================================
# 📝 INSTRUCCIONES:
#
# 1. Obtén las IPs de tus 3 PCs:
#    Windows: ipconfig
#    Linux/Mac: ifconfig
#
# 2. Edita las 3 variables PC1_IP, PC2_IP y PC3_IP con tus IPs reales
#
# 3. Guarda este archivo
#
# ⚠️  Las 3 IPs deben estar en la MISMA red local (ej: 192.168.1.xxx)
# ============================================================================

# ==== CONFIGURACIÓN DE IPS POR PC ====

# PC1 - EV_Driver (Interfaz de conductor)
PC1_IP = "192.168.1.42"  # ⚠️ CAMBIAR por la IP real del PC1

# PC2 - EV_Central (Servidor central + Kafka Broker)
PC2_IP = "192.168.1.42"  # ⚠️ CAMBIAR por la IP real del PC2 (donde corre Kafka)

# PC3 - EV_CP (Monitor & Engine - Punto de carga)
PC3_IP = "192.168.1.42"  # ⚠️ CAMBIAR por la IP real del PC3

# ==== CONFIGURACIÓN DE PUERTOS ====
CENTRAL_PORT = 5000
KAFKA_PORT = 9092

# ==== CONFIGURACIÓN DE KAFKA ====
# El broker de Kafka debe estar en PC2 (Central)
KAFKA_BROKER_IP = PC2_IP
KAFKA_BROKER = f"{KAFKA_BROKER_IP}:{KAFKA_PORT}"

# Topics de Kafka
KAFKA_TOPICS = {
    'driver_events': 'driver-events',      # Eventos del Driver
    'cp_events': 'cp-events',              # Eventos de Charging Points (Monitor + Engine)
    'central_events': 'central-events',    # Eventos del Central
    'monitor_events': 'monitor-events'     # Eventos del Monitor
}

# ==== CONFIGURACIÓN POR COMPONENTE ====

# EV_Central - Servidor Central (PC2)
CENTRAL_CONFIG = {
    'ip': '0.0.0.0',  # Escuchar en todas las interfaces
    'port': CENTRAL_PORT,
    'kafka_broker': KAFKA_BROKER,
    'ws_port': 8002  # Puerto para WebSocket del dashboard admin
}

# EV_Driver - Cliente Driver (PC1)
DRIVER_CONFIG = {
    'central_ip': PC2_IP,  # Conecta al Central en PC2
    'central_port': CENTRAL_PORT,
    'kafka_broker': KAFKA_BROKER,  # Conecta a Kafka en PC2
    'ws_port': 8001  # Puerto para WebSocket del dashboard driver
}

# EV_CP_M - Monitor del Punto de Carga (PC3)
MONITOR_CONFIG = {
    'central_ip': PC2_IP,  # Conecta al Central en PC2
    'central_port': CENTRAL_PORT,
    'kafka_broker': KAFKA_BROKER,  # Conecta a Kafka en PC2
    'ws_port': 8003  # Puerto para WebSocket del dashboard monitor
}

# EV_CP_E - Engine del Punto de Carga (PC3)
ENGINE_CONFIG = {
    'central_ip': PC2_IP,  # Conecta al Central en PC2
    'central_port': CENTRAL_PORT,
    'engine_id': 'CP01',
    'engine_ip': '0.0.0.0',
    'engine_port': 5100,
    'location': 'Alicante-Campus-01',
    'price_eur_kwh': 0.35,
    'kafka_broker': KAFKA_BROKER  # Conecta a Kafka en PC2
}

# ==== CONFIGURACIÓN DE FIREWALL ====
# Asegúrate de abrir estos puertos en el firewall:
REQUIRED_PORTS = {
    'PC1': [8001],  # WebSocket Driver
    'PC2': [5000, 8002, 9092, 2181],  # Central, WebSocket Admin, Kafka, Zookeeper
    'PC3': [8003, 5100]  # WebSocket Monitor, Engine
}

# ==== INSTRUCCIONES DE DESPLIEGUE ====
"""
1. PC2 (Central + Kafka):
   - Ejecutar: docker-compose up -d (para iniciar Kafka)
   - Ejecutar: python EV_Central/EV_Central_WebSocket.py
   - Acceder: http://PC2_IP:8002 (Dashboard Admin)

2. PC1 (Driver):
   - Asegurarse de que PC2_IP apunta al PC2
   - Ejecutar: python EV_Driver/EV_Driver_WebSocket.py
   - Acceder: http://PC1_IP:8001 (Dashboard Driver)

3. PC3 (Monitor + Engine):
   - Asegurarse de que PC2_IP apunta al PC2
   - Ejecutar: python EV_CP_M/EV_CP_M_WebSocket.py
   - Acceder: http://PC3_IP:8003 (Dashboard Monitor)

4. Verificar conectividad:
   - Desde PC1: ping PC2_IP
   - Desde PC3: ping PC2_IP
   - Verificar firewall y puertos abiertos
"""
