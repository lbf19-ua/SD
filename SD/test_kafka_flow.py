#!/usr/bin/env python3
"""
Script de prueba para verificar el flujo de mensajes en Kafka
Envía un evento de prueba al topic driver-events
"""
import json
from kafka import KafkaProducer
import time

# Configuración
KAFKA_BROKER = 'localhost:9092'  # Desde fuera de Docker
TOPIC = 'driver-events'

def send_test_event():
    """Envía un evento de prueba al topic de driver"""
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
        
        # Crear evento de prueba
        test_event = {
            "event_type": "TEST_EVENT",
            "event_id": f"TEST_{int(time.time())}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "driver_id": "driver1",
            "data": {
                "message": "🧪 Evento de prueba desde test_kafka_flow.py",
                "purpose": "Verificar flujo de Kafka"
            }
        }
        
        print(f"📤 Enviando evento de prueba a Kafka...")
        print(f"   Topic: {TOPIC}")
        print(f"   Broker: {KAFKA_BROKER}")
        print(f"   Evento: {json.dumps(test_event, indent=2)}")
        
        future = producer.send(TOPIC, key='test', value=test_event)
        result = future.get(timeout=10)
        
        print(f"\n✅ Evento enviado exitosamente!")
        print(f"   Partition: {result.partition}")
        print(f"   Offset: {result.offset}")
        print(f"\n📊 Ahora deberías ver este evento en:")
        print(f"   - Dashboard de Central: http://localhost:8002")
        print(f"   - Kafka UI: http://localhost:8080/ui/clusters/ev-charging-cluster/topics/{TOPIC}")
        
        producer.close()
        
    except Exception as e:
        print(f"❌ Error al enviar evento: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("="*70)
    print("  🧪 TEST DE FLUJO DE KAFKA")
    print("="*70)
    send_test_event()
    print("="*70)
