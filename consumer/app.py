import os, json, time, sys
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
TOPIC = os.getenv("TOPIC", "ev.test")
GROUP = os.getenv("GROUP", "ev-group-1")

def connect_consumer():
    for i in range(30):
        try:
            return KafkaConsumer(
                TOPIC,
                bootstrap_servers=BOOTSTRAP,
                group_id=GROUP,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            )
        except NoBrokersAvailable:
            print("[consumer] Kafka no disponible, reintentando...", i+1, "/30", flush=True)
            time.sleep(1)
    print("[consumer] No fue posible conectar con Kafka", flush=True)
    sys.exit(1)

if __name__ == "__main__":
    c = connect_consumer()
    print(f"[consumer] Escuchando '{TOPIC}' en grupo '{GROUP}'...", flush=True)
    for rec in c:
        print("[consumer] <-", rec.value, flush=True)