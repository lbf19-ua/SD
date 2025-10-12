# Configuración de IPs para despliegue en red local
# Modifica estas IPs según tu red

# PC1 - EV_Driver (ejemplo)
PC1_IP = "192.168.1.100"

# PC2 - EV_Central (este PC actual)  
PC2_IP = "192.168.1.235"  # IP actual de este PC

# PC3 - EV_CP (Monitor & Engine)
PC3_IP = "192.168.1.101"

# Puerto del servidor central
CENTRAL_PORT = 5000

# Configuración por componente
CENTRAL_CONFIG = {
    'ip': PC2_IP,
    'port': CENTRAL_PORT
}

DRIVER_CONFIG = {
    'central_ip': PC2_IP,
    'central_port': CENTRAL_PORT
}

MONITOR_CONFIG = {
    'central_ip': PC2_IP, 
    'central_port': CENTRAL_PORT
}

ENGINE_CONFIG = {
    'central_ip': PC2_IP,
    'central_port': CENTRAL_PORT
}