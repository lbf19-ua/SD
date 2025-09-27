import os, time, json, sys
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
TOPIC = os.getenv("TOPIC", "ev.test")

def connect_producer():
    for i in range(30):
        try:
            return KafkaProducer(
                bootstrap_servers=BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
        except NoBrokersAvailable:
            print("[producer] Kafka no disponible, reintentando...", i+1, "/30", flush=True)
            time.sleep(1)
    print("[producer] No fue posible conectar con Kafka", flush=True)
    sys.exit(1)

if __name__ == "__main__":
    p = connect_producer()
    i = 0
    print(f"[producer] Enviando a '{TOPIC}'...", flush=True)
    while True:
        msg = {"seq": i, "ts": time.time()}
        p.send(TOPIC, msg)
        p.flush()
        print("[producer] ->", msg, flush=True)
        i += 1
        time.sleep(1)