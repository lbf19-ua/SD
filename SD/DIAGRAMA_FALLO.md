# 📊 DIAGRAMA DEL FALLO

## 🔴 Escenario: Driver arranca ANTES de Kafka

```
┌─────────────────────────────────────────────────────────────────────┐
│ FASE 1: Inicialización                                             │
└─────────────────────────────────────────────────────────────────────┘

Driver arranca
    │
    ├─> initialize_kafka()
    │     │
    │     ├─> Intenta conectar a Kafka
    │     │     │
    │     │     └─> ❌ FALLA (Kafka no está listo)
    │     │
    │     └─> self.producer = None  ❌
    │         self.consumer = None  ❌
    │
    └─> kafka_listener() en thread separado
          │
          ├─> Loop infinito
          │     │
          │     ├─> Excepción: self.consumer is None
          │     │
          │     └─> RECONEXIÓN AUTOMÁTICA
          │           │
          │           └─> self.consumer = KafkaConsumer(...)  ✅
          │
          └─> Ahora self.consumer funciona ✅
              Pero self.producer sigue None ❌

┌─────────────────────────────────────────────────────────────────────┐
│ FASE 2: Usuario solicita carga                                     │
└─────────────────────────────────────────────────────────────────────┘

Usuario click "Solicitar Carga"
    │
    ├─> request_charging()
    │     │
    │     ├─> if self.producer:  ← self.producer es None
    │     │     │
    │     │     └─> NO entra
    │     │
    │     └─> return {
    │           'success': False,
    │           'message': 'Sistema de mensajería no disponible'  ❌
    │         }
    │
    └─> FLUJO SE DETIENE AQUÍ
        El usuario ve el error

┌─────────────────────────────────────────────────────────────────────┐
│ ESCENARIO ALTERNATIVO: Producer se inicializa por suerte           │
└─────────────────────────────────────────────────────────────────────┘

Usuario click "Solicitar Carga"
    │
    ├─> request_charging()
    │     │
    │     ├─> if self.producer:  ← self.producer OK ✅
    │     │     │
    │     │     └─> self.producer.send(AUTHORIZATION_REQUEST)
    │     │
    │     └─> return {'success': True, 'pending': True}
    │
    ├─> Central recibe AUTHORIZATION_REQUEST
    │     │
    │     ├─> Busca CP disponible
    │     │
    │     ├─> CP_001 encontrado
    │     │
    │     ├─> UPDATE charging_points
    │     │   SET estado = 'reserved'
    │     │   WHERE cp_id = 'CP_001'
    │     │
    │     └─> Envía AUTHORIZATION_RESPONSE
    │           └─> {authorized: True, cp_id: 'CP_001'}
    │
    ├─> Driver recibe AUTHORIZATION_RESPONSE (en kafka_listener)
    │     │
    │     ├─> print("[DRIVER] ✅ Central autorizó carga en CP_001")
    │     │
    │     ├─> LÍNEA 111 - PUNTO CRÍTICO:
    │     │   if self.producer:  ← Aquí puede ser None
    │     │
    │     │   ┌─── SI self.producer es None ────────────────┐
    │     │   │                                             │
    │     │   │  NO entra en el if                         │
    │     │   │  NO envía charging_started                 │
    │     │   │  CP_001 se queda en 'reserved' FOREVER     │
    │     │   │                                             │
    │     │   └─────────────────────────────────────────────┘
    │     │
    │     │   ┌─── SI self.producer funciona ──────────────┐
    │     │   │                                             │
    │     │   │  Envía charging_started                    │
    │     │   │  print("[DRIVER] 📤 Enviado evento...")    │
    │     │   │                                             │
    │     │   │  Central recibe charging_started           │
    │     │   │    ├─> create_charging_session()           │
    │     │   │    │     └─> UPDATE charging_points        │
    │     │   │    │         SET estado = 'charging'       │
    │     │   │    │         WHERE cp_id = 'CP_001'        │
    │     │   │    │                                        │
    │     │   │    └─> CP_001 cambia a 'charging' ✅       │
    │     │   │                                             │
    │     │   └─────────────────────────────────────────────┘
    │     │
    │     └─> Notifica al usuario
    │
    └─> FIN

┌─────────────────────────────────────────────────────────────────────┐
│ COMPARACIÓN: Consumer vs Producer                                  │
└─────────────────────────────────────────────────────────────────────┘

CONSUMER (funciona con reconexión):
    │
    ├─> kafka_listener() - loop infinito
    │     │
    │     ├─> for message in self.consumer:
    │     │     │
    │     │     └─> Procesa mensajes
    │     │
    │     └─> except Exception:
    │           │
    │           └─> self.consumer = KafkaConsumer(...)  ✅
    │               RECONEXIÓN AUTOMÁTICA
    │
    └─> Consumer SIEMPRE funciona ✅

PRODUCER (NO tiene reconexión):
    │
    ├─> initialize_kafka()
    │     │
    │     ├─> try:
    │     │     self.producer = KafkaProducer(...)
    │     │   except:
    │     │     self.producer = None  ❌
    │     │
    │     └─> NO HAY LÓGICA DE RECONEXIÓN
    │
    ├─> request_charging()
    │     │
    │     └─> if self.producer:  ← Si es None, FALLA
    │
    ├─> kafka_listener() (al recibir AUTHORIZATION_RESPONSE)
    │     │
    │     └─> if self.producer:  ← Si es None, FALLA
    │
    └─> Producer puede ser None en CUALQUIER momento ❌

┌─────────────────────────────────────────────────────────────────────┐
│ SOLUCIÓN                                                            │
└─────────────────────────────────────────────────────────────────────┘

Agregar reconexión al Producer:

def ensure_producer(self):
    if self.producer is None:
        try:
            self.producer = KafkaProducer(...)
            return True
        except:
            return False
    return True

Usar en todos los lugares:

ANTES:                          DESPUÉS:
if self.producer:               if self.ensure_producer():
    self.producer.send(...)  →      self.producer.send(...)

┌─────────────────────────────────────────────────────────────────────┐
│ FLUJO CON LA SOLUCIÓN                                               │
└─────────────────────────────────────────────────────────────────────┘

Driver recibe AUTHORIZATION_RESPONSE
    │
    ├─> if self.ensure_producer():  ← Intenta reconectar
    │     │
    │     ├─> if self.producer is None:
    │     │     │
    │     │     └─> self.producer = KafkaProducer(...)  ✅
    │     │
    │     └─> return True
    │
    ├─> self.producer.send(charging_started)  ✅
    │
    └─> Central recibe y cambia CP a 'charging'  ✅
```

