#!/usr/bin/env python3
"""
Script de prueba de conexión a Kafka
Verifica si el Driver puede conectarse al broker de Kafka en PC2
"""

import socket
import sys

def test_tcp_connection(host, port):
    """Test basic TCP connectivity"""
    print(f"\n🔌 Probando conexión TCP a {host}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ Conexión TCP OK")
            return True
        else:
            print(f"❌ No se puede conectar (código: {result})")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_kafka_producer(host, port):
    """Test Kafka producer connection"""
    print(f"\n📡 Probando conexión Kafka Producer a {host}:{port}...")
    try:
        from kafka import KafkaProducer
        import json
        
        bootstrap_servers = f"{host}:{port}"
        print(f"   Conectando a: {bootstrap_servers}")
        
        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            request_timeout_ms=5000
        )
        
        # Intentar enviar un mensaje de prueba
        test_message = {
            'test': True,
            'timestamp': '2025-01-01T00:00:00'
        }
        producer.send('test-topic', test_message)
        producer.flush()
        producer.close()
        
        print(f"✅ Kafka Producer OK")
        return True
    except Exception as e:
        print(f"❌ Error en Kafka Producer: {e}")
        return False

def test_kafka_consumer(host, port):
    """Test Kafka consumer connection"""
    print(f"\n📥 Probando conexión Kafka Consumer a {host}:{port}...")
    try:
        from kafka import KafkaConsumer
        
        bootstrap_servers = f"{host}:{port}"
        print(f"   Conectando a: {bootstrap_servers}")
        
        consumer = KafkaConsumer(
            'test-topic',
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            consumer_timeout_ms=5000
        )
        
        # Intentar leer (timeout de 5 segundos)
        print(f"   Intentando leer mensajes...")
        for message in consumer:
            print(f"   ✅ Mensaje recibido: {message.value}")
            break
        
        consumer.close()
        print(f"✅ Kafka Consumer OK")
        return True
    except Exception as e:
        print(f"❌ Error en Kafka Consumer: {e}")
        return False

def main():
    print("=" * 80)
    print(" " * 20 + "🧪 TEST DE CONEXIÓN KAFKA")
    print("=" * 80)
    
    # Importar configuración
    try:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from network_config import PC2_IP, KAFKA_PORT, KAFKA_BROKER
        
        print(f"\n📋 Configuración actual:")
        print(f"   PC2_IP: {PC2_IP}")
        print(f"   KAFKA_PORT: {KAFKA_PORT}")
        print(f"   KAFKA_BROKER: {KAFKA_BROKER}")
        print()
    except Exception as e:
        print(f"⚠️ No se pudo cargar network_config.py: {e}")
        PC2_IP = "172.20.10.8"  # Default
        KAFKA_PORT = 9092
    
    # Test 1: TCP connection
    tcp_ok = test_tcp_connection(PC2_IP, KAFKA_PORT)
    
    if not tcp_ok:
        print("\n" + "=" * 80)
        print("❌ DIAGNÓSTICO:")
        print("   El PC no puede conectarse a Kafka en PC2.")
        print("\n   Posibles causas:")
        print("   1. Kafka no está corriendo en PC2")
        print("   2. Firewall bloquea el puerto 9092")
        print("   3. IP incorrecta en network_config.py")
        print("   4. PC2 y PC1 no están en la misma red")
        print("\n   Soluciones:")
        print("   1. Ejecutar en PC2: docker-compose -f docker-compose.pc2.yml up -d")
        print("   2. Verificar IP de PC2: ping 172.20.10.8")
        print("   3. Abrir firewall en PC2 (puerto 9092)")
        print("=" * 80)
        return
    
    # Test 2: Kafka Producer
    try:
        producer_ok = test_kafka_producer(PC2_IP, KAFKA_PORT)
    except ImportError:
        print("⚠️ kafka-python no instalado. Instala con: pip install kafka-python")
        producer_ok = False
    except Exception as e:
        print(f"⚠️ Error inesperado: {e}")
        producer_ok = False
    
    # Test 3: Kafka Consumer
    try:
        import json
        consumer_ok = test_kafka_consumer(PC2_IP, KAFKA_PORT)
    except Exception as e:
        print(f"⚠️ Error en consumer: {e}")
        consumer_ok = False
    
    # Resumen
    print("\n" + "=" * 80)
    print("📊 RESUMEN:")
    print("=" * 80)
    print(f"  TCP Connection:    {'✅ OK' if tcp_ok else '❌ FAIL'}")
    print(f"  Kafka Producer:    {'✅ OK' if producer_ok else '❌ FAIL'}")
    print(f"  Kafka Consumer:    {'✅ OK' if consumer_ok else '❌ FAIL'}")
    print("=" * 80)
    
    if tcp_ok and producer_ok and consumer_ok:
        print("\n🎉 ¡CONEXIÓN A KAFKA OK! El Driver puede conectarse al broker.")
    else:
        print("\n❌ Hay problemas con la conexión a Kafka.")
        print("   Revisa los errores anteriores y aplica las soluciones sugeridas.")

if __name__ == "__main__":
    main()


