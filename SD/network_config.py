# PC1
PC1_IP = "192.168.1.235"

# PC2
PC2_IP = "192.168.1.235"

# PC3
PC3_IP = "192.168.1.230"

CENTRAL_PORT = 5000
KAFKA_PORT = 9092
KAFKA_BROKER_IP = PC2_IP
KAFKA_BROKER = f"{KAFKA_BROKER_IP}:{KAFKA_PORT}"

# Topics de Kafka
KAFKA_TOPICS = {
    'driver_events': 'driver-events',      # Eventos del Driver
    'cp_events': 'cp-events',              # Eventos de Charging Points (Monitor + Engine)
    'central_events': 'central-events',    # Eventos del Central
    'monitor_events': 'monitor-events'     # Eventos del Monitor
}

# EV_Central
CENTRAL_CONFIG = {
    'ip': '0.0.0.0',  # Escuchar en todas las interfaces
    'port': CENTRAL_PORT,
    'kafka_broker': KAFKA_BROKER,
    'ws_port': 8002  # Puerto para WebSocket del dashboard admin
}

# EV_Driver
DRIVER_CONFIG = {
    'central_ip': PC2_IP,  # Conecta al Central en PC2
    'central_port': CENTRAL_PORT,
    'kafka_broker': KAFKA_BROKER,  # Conecta a Kafka en PC2
    'ws_port': 8001  # Puerto para WebSocket del dashboard driver
}

# EV_CP_M
MONITOR_CONFIG = {
    'central_ip': PC2_IP,  # Conecta al Central en PC2
    'central_port': CENTRAL_PORT,
    'kafka_broker': KAFKA_BROKER,  # Conecta a Kafka en PC2
    'ws_port': 8003  # Puerto para WebSocket del dashboard monitor
}

# EV_CP_E
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

REQUIRED_PORTS = {
    'PC1': [8001],  # WebSocket Driver
    'PC2': [8002, 9092],  # WebSocket Admin Central, Kafka
    'PC3': [5100, 5101, 5102, 5500, 5501, 5502]  # Health ports Engines, Monitor Dashboards
}