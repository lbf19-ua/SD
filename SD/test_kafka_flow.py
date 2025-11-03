#!/usr/bin/env python3
"""
Script de prueba para verificar el flujo completo de Kafka:
1. Engine publica evento CP_REGISTRATION
2. Central recibe y procesa el evento

Ejecutar este script para diagnosticar problemas de comunicación Kafka
"""

import sys
import os
import time
import json

# Añadir el directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kafka import KafkaProducer, KafkaConsumer
from network_config import KAFKA_TOPICS, KAFKA_BROKER

def test_engine_to_central():
    """Prueba el flujo Engine → Central"""
    print("=" * 80)
    print("🧪 TEST: Engine → Central (Kafka)")
    print("=" * 80)
    
    kafka_broker = os.environ.get('KAFKA_BROKER', KAFKA_BROKER)
    print(f"\n📡 Kafka Broker: {kafka_broker}")
    print(f"📤 Topic de publicación (cp-events): {KAFKA_TOPICS['cp_events']}")
    print(f"📥 Topic de consumo (Central debe escuchar): {KAFKA_TOPICS['cp_events']}")
    
    # 1. Crear producer (como Engine)
    print("\n1️⃣  Creando Producer (simulando Engine)...")
    try:
        producer = KafkaProducer(
            bootstrap_servers=kafka_broker,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            api_version=(0, 10, 1),
            request_timeout_ms=30000
        )
        print("   ✅ Producer creado")
    except Exception as e:
        print(f"   ❌ Error creando producer: {e}")
        return False
    
    # 2. Publicar evento CP_REGISTRATION (como Engine)
    print("\n2️⃣  Publicando evento CP_REGISTRATION...")
    test_event = {
        'message_id': f'test-{int(time.time())}',
        'event_type': 'CP_REGISTRATION',
        'cp_id': 'CP_TEST_001',
        'engine_id': 'CP_TEST_001',
        'action': 'connect',
        'timestamp': time.time(),
        'data': {
            'location': 'Test Location',
            'localizacion': 'Test Location',
            'max_kw': 22.0,
            'max_power_kw': 22.0,
            'tarifa_kwh': 0.30,
            'tariff_per_kwh': 0.30,
            'price_eur_kwh': 0.30
        }
    }
    
    try:
        future = producer.send(KAFKA_TOPICS['cp_events'], test_event)
        producer.flush(timeout=10)
        print(f"   ✅ Evento publicado: {json.dumps(test_event, indent=2)}")
    except Exception as e:
        print(f"   ❌ Error publicando evento: {e}")
        return False
    
    # 3. Crear consumer (simulando Central)
    print("\n3️⃣  Creando Consumer (simulando Central)...")
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPICS['cp_events'],
            bootstrap_servers=kafka_broker,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            group_id='test_central_group',
            api_version=(0, 10, 1),
            request_timeout_ms=30000,
            consumer_timeout_ms=10000  # Esperar máximo 10 segundos
        )
        print("   ✅ Consumer creado")
    except Exception as e:
        print(f"   ❌ Error creando consumer: {e}")
        return False
    
    # 4. Intentar consumir el mensaje
    print("\n4️⃣  Intentando consumir mensaje...")
    print("   ⏳ Esperando hasta 10 segundos...")
    
    try:
        message_count = 0
        for message in consumer:
            message_count += 1
            event = message.value
            print(f"\n   ✅ Mensaje recibido #{message_count}:")
            print(f"      Topic: {message.topic}")
            print(f"      Event Type: {event.get('event_type')}")
            print(f"      CP ID: {event.get('cp_id')}")
            print(f"      Action: {event.get('action')}")
            print(f"      Data: {json.dumps(event.get('data', {}), indent=6)}")
            
            # Verificar si es nuestro mensaje de prueba
            if event.get('cp_id') == 'CP_TEST_001':
                print("\n   🎯 ¡Mensaje de prueba encontrado!")
                consumer.close()
                producer.close()
                print("\n✅ TEST EXITOSO: Engine puede comunicarse con Central")
                return True
            
            # Solo leer un mensaje para la prueba
            if message_count >= 5:
                break
                
    except Exception as e:
        print(f"   ❌ Error consumiendo mensaje: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        consumer.close()
        producer.close()
    
    print("\n⚠️  TEST INCOMPLETO: No se recibió el mensaje de prueba")
    return False

if __name__ == "__main__":
    print("\n🔍 Verificando configuración...")
    print(f"KAFKA_BROKER: {os.environ.get('KAFKA_BROKER', KAFKA_BROKER)}")
    print(f"Topics: {KAFKA_TOPICS}\n")
    
    success = test_engine_to_central()
    
    print("\n" + "=" * 80)
    if success:
        print("✅ TEST COMPLETADO EXITOSAMENTE")
    else:
        print("❌ TEST FALLÓ - Revisar configuración de Kafka")
    print("=" * 80)


