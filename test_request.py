import json
import time
from kafka import KafkaProducer

def send_test_request():
    producer = KafkaProducer(
        bootstrap_servers='localhost:9094',  # Puerto externo de Kafka
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    # Solicitud de prueba
    test_request = {
        "cpId": "CP-TEST-001",
        "requestId": "REQ-001",
        "vehicleId": "VEHICLE-123",
        "timestamp": time.time(),
        "requestedPower": 22.0,
        "estimatedDuration": 60
    }
    
    producer.send('ev.supply.request', test_request)
    producer.flush()
    print(f"✅ Solicitud de prueba enviada: {test_request}")

if __name__ == "__main__":
    send_test_request()