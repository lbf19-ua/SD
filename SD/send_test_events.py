#!/usr/bin/env python3
"""
Script para enviar eventos de prueba a Kafka desde dentro del contenedor
Se ejecuta con: docker exec ev-driver python /app/send_test_events.py
"""
from kafka import KafkaProducer
import json
import time
import sys

KAFKA_BROKER = 'kafka-broker:29092'

def send_event(producer, topic, event):
    """Envía un evento y muestra confirmación"""
    try:
        result = producer.send(topic, value=event).get(timeout=5)
        print(f"✅ Enviado: {event['event_type']} -> Offset: {result.offset}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("="*70)
    print("  📤 ENVIANDO EVENTOS DE PRUEBA A KAFKA")
    print("="*70)
    print(f"Broker: {KAFKA_BROKER}")
    print(f"Verifica el dashboard: http://localhost:8002")
    print("="*70)
    
    # Crear productor
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    # Lista de eventos de prueba
    events = [
        {
            'topic': 'driver-events',
            'event': {
                'event_type': 'DRIVER_LOGIN',
                'event_id': f'LOGIN_{int(time.time())}',
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'action': 'user_login',
                'username': 'driver1',
                'data': {'ip': '172.19.0.6', 'device': 'web'}
            }
        },
        {
            'topic': 'driver-events',
            'event': {
                'event_type': 'CHARGING_REQUEST',
                'event_id': f'REQ_{int(time.time())}',
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'action': 'charging_request',
                'username': 'driver1',
                'cp_id': 'CP001',
                'data': {'requested_power': 50, 'duration': 30}
            }
        },
        {
            'topic': 'driver-events',
            'event': {
                'event_type': 'CHARGING_STARTED',
                'event_id': f'START_{int(time.time())}',
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'action': 'charging_started',
                'username': 'driver1',
                'cp_id': 'CP001',
                'requested_power': 50,
                'data': {'start_time': time.strftime('%Y-%m-%d %H:%M:%S')}
            }
        },
        {
            'topic': 'cp-events',
            'event': {
                'event_type': 'CP_STATUS_UPDATE',
                'event_id': f'STATUS_{int(time.time())}',
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'action': 'status_update',
                'cp_id': 'CP001',
                'status': 'charging',
                'data': {'power': 48.5, 'current_user': 'driver1'}
            }
        },
        {
            'topic': 'driver-events',
            'event': {
                'event_type': 'CHARGING_STOPPED',
                'event_id': f'STOP_{int(time.time())}',
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'action': 'charging_stopped',
                'username': 'driver1',
                'cp_id': 'CP001',
                'energy_kwh': 15.5,
                'cost': 7.75,
                'data': {'duration_minutes': 30, 'end_time': time.strftime('%Y-%m-%d %H:%M:%S')}
            }
        }
    ]
    
    # Enviar cada evento con un pequeño delay
    for i, item in enumerate(events, 1):
        print(f"\n[{i}/{len(events)}] Enviando al topic '{item['topic']}'...")
        print(f"    Tipo: {item['event']['event_type']}")
        send_event(producer, item['topic'], item['event'])
        time.sleep(1)  # Esperar 1 segundo entre eventos
    
    producer.close()
    
    print("\n" + "="*70)
    print("✅ TODOS LOS EVENTOS ENVIADOS")
    print("="*70)
    print("📊 Revisa el dashboard de Central para ver los eventos")
    print("   URL: http://localhost:8002")
    print("="*70)

if __name__ == "__main__":
    main()
