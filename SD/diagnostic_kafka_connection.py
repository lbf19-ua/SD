#!/usr/bin/env python3
"""
Script de diagnóstico para verificar conexión a Kafka desde PC3 a PC2
Ejecutar este script en PC3 para diagnosticar problemas de conexión
"""

import sys
import os

print("=" * 80)
print("🔍 DIAGNÓSTICO DE CONEXIÓN KAFKA PC3 → PC2")
print("=" * 80)

# 1. Verificar archivo .env
print("\n1️⃣  Verificando archivo .env...")
if os.path.exists('.env'):
    print("✅ Archivo .env existe")
    with open('.env', 'r') as f:
        env_content = f.read()
        print(f"📄 Contenido del .env:")
        for line in env_content.split('\n'):
            if line.strip() and not line.strip().startswith('#'):
                print(f"   {line}")
        
        # Verificar variables
        if 'KAFKA_BROKER=' in env_content:
            kafka_broker = [l for l in env_content.split('\n') if 'KAFKA_BROKER=' in l and not l.strip().startswith('#')]
            if kafka_broker:
                broker_value = kafka_broker[0].split('=')[1].strip()
                if broker_value.startswith('"') or broker_value.startswith("'"):
                    print(f"⚠️  ADVERTENCIA: KAFKA_BROKER tiene comillas: {broker_value}")
                    print("   ❌ Eliminar las comillas del .env")
                else:
                    print(f"✅ KAFKA_BROKER correcto: {broker_value}")
        else:
            print("❌ KAFKA_BROKER no encontrado en .env")
        
        if 'PC2_IP=' in env_content:
            pc2_ip = [l for l in env_content.split('\n') if 'PC2_IP=' in l and not l.strip().startswith('#')]
            if pc2_ip:
                ip_value = pc2_ip[0].split('=')[1].strip()
                if ip_value.startswith('"') or ip_value.startswith("'"):
                    print(f"⚠️  ADVERTENCIA: PC2_IP tiene comillas: {ip_value}")
                    print("   ❌ Eliminar las comillas del .env")
                else:
                    print(f"✅ PC2_IP correcto: {ip_value}")
        else:
            print("❌ PC2_IP no encontrado en .env")
else:
    print("❌ Archivo .env NO existe")
    print("   Crear archivo .env con:")
    print("   PC2_IP=192.168.1.XXX")
    print("   KAFKA_BROKER=192.168.1.XXX:9092")
    sys.exit(1)

# 2. Intentar importar kafka-python
print("\n2️⃣  Verificando dependencias...")
try:
    from kafka import KafkaProducer, KafkaConsumer
    print("✅ kafka-python instalado")
except ImportError:
    print("❌ kafka-python NO está instalado")
    print("   Instalar con: pip install kafka-python")
    sys.exit(1)

# 3. Leer variables de entorno
print("\n3️⃣  Leyendo variables de entorno...")
kafka_broker = os.environ.get('KAFKA_BROKER')
pc2_ip = os.environ.get('PC2_IP')

if kafka_broker:
    print(f"✅ KAFKA_BROKER desde env: {kafka_broker}")
    if kafka_broker.startswith('"') or kafka_broker.startswith("'"):
        print(f"⚠️  ADVERTENCIA: Variable tiene comillas: {kafka_broker}")
else:
    print("⚠️  KAFKA_BROKER no está en variables de entorno")
    # Intentar leer del .env
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                if 'KAFKA_BROKER=' in line and not line.strip().startswith('#'):
                    kafka_broker = line.split('=')[1].strip().strip('"\'')
                    print(f"📖 KAFKA_BROKER desde .env: {kafka_broker}")
                    break

if not kafka_broker:
    print("❌ No se pudo obtener KAFKA_BROKER")
    sys.exit(1)

# 4. Verificar formato del broker
print(f"\n4️⃣  Verificando formato de broker...")
print(f"   Broker: {kafka_broker}")
if ':' not in kafka_broker:
    print("❌ Formato incorrecto: debe ser IP:PUERTO (ej: 192.168.1.100:9092)")
    sys.exit(1)
if kafka_broker.startswith('broker:'):
    print("⚠️  ADVERTENCIA: Usando 'broker:29092' - esto solo funciona dentro de Docker")
    print("   Para conexión externa, usar IP_PC2:9092")
elif kafka_broker.startswith('localhost') or kafka_broker.startswith('127.0.0.1'):
    print("⚠️  ADVERTENCIA: Usando localhost - esto no funcionará desde otro PC")
    print("   Usar IP real de PC2: IP_PC2:9092")
else:
    ip, port = kafka_broker.split(':')
    print(f"   ✅ IP: {ip}")
    print(f"   ✅ Puerto: {port}")

# 5. Intentar conexión
print(f"\n5️⃣  Intentando conectar a Kafka...")
print(f"   Broker: {kafka_broker}")

try:
    print("   📤 Probando Producer...")
    producer = KafkaProducer(
        bootstrap_servers=kafka_broker,
        value_serializer=lambda v: str(v).encode('utf-8'),
        api_version=(0, 10, 1),
        request_timeout_ms=30000,
        retries=1
    )
    
    # Intentar obtener metadata
    metadata = producer.list_topics(timeout=10)
    print(f"   ✅ Producer conectado exitosamente")
    print(f"   📊 Topics disponibles: {len(metadata)}")
    
    producer.close()
    
except Exception as e:
    print(f"   ❌ Error conectando Producer: {e}")
    print(f"   📋 Tipo de error: {type(e).__name__}")
    import traceback
    print(f"   📄 Detalles:")
    traceback.print_exc()
    
    print("\n💡 POSIBLES SOLUCIONES:")
    print("   1. Verificar que Kafka está corriendo en PC2: docker ps | grep kafka")
    print("   2. Verificar firewall en PC2: permitir puerto 9092")
    print("   3. Probar conectividad: Test-NetConnection -ComputerName <IP_PC2> -Port 9092")
    print("   4. Verificar .env en PC2: PC2_IP debe ser la IP real")
    print("   5. Reiniciar Kafka en PC2: docker-compose -f docker-compose.pc2.yml restart")
    sys.exit(1)

print("\n" + "=" * 80)
print("✅ DIAGNÓSTICO COMPLETADO - Conexión a Kafka OK")
print("=" * 80)


