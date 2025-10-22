"""
Script de prueba para verificar que EV_Central maneja correctamente:
a) Registro y alta de nuevos puntos de recarga
b) Autorización de suministros

Este script simula eventos desde otros componentes y verifica que Central los procesa.
"""
import json
import time
import sys
from pathlib import Path
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import NoBrokersAvailable

sys.path.insert(0, str(Path(__file__).parent))
from event_utils import generate_message_id, current_timestamp
import database as db

KAFKA_BROKER = 'localhost:9092'

class CentralRequestTester:
    def __init__(self):
        self.producer = None
        self.consumer = None
        
    def initialize_kafka(self):
        """Inicializa productor y consumidor de Kafka"""
        try:
            print("\n" + "="*80)
            print(" 🧪 TEST: Verificación de Peticiones a EV_Central")
            print("="*80)
            print(f"\n📡 Conectando a Kafka broker: {KAFKA_BROKER}")
            
            self.producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKER,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            
            # Consumidor para escuchar respuestas de Central
            self.consumer = KafkaConsumer(
                'central-events',
                bootstrap_servers=KAFKA_BROKER,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                consumer_timeout_ms=5000
            )
            
            print("✅ Kafka conexión establecida\n")
            return True
            
        except NoBrokersAvailable:
            print("❌ Error: Kafka broker no disponible")
            print("   Asegúrate de que Kafka está corriendo en localhost:9092")
            return False
        except Exception as e:
            print(f"❌ Error inicializando Kafka: {e}")
            return False
    
    def test_charging_point_registration(self):
        """
        TEST A: Registro y alta de un nuevo punto de recarga
        Simula un EV_CP_E que se registra con Central
        """
        print("\n" + "-"*80)
        print("📋 TEST A: Registro de Nuevo Punto de Recarga")
        print("-"*80)
        
        # Datos del nuevo punto de carga
        new_cp_id = f"CP_TEST_{int(time.time())}"
        
        print(f"\n1️⃣ Enviando solicitud de registro para: {new_cp_id}")
        print(f"   Ubicación: Test Location - Campus Universitario")
        print(f"   Capacidad: 22.0 kW")
        print(f"   Tarifa: €0.28/kWh")
        
        # Evento de registro/conexión de CP
        registration_event = {
            'message_id': generate_message_id(),
            'event_type': 'CP_REGISTRATION',
            'component': 'engine',
            'engine_id': new_cp_id,
            'cp_id': new_cp_id,
            'action': 'connect',
            'data': {
                'location': 'Test Location - Campus Universitario',
                'max_kw': 22.0,
                'tarifa_kwh': 0.28,
                'status': 'available'
            },
            'timestamp': current_timestamp(),
            'correlation_id': generate_message_id()
        }
        
        # Enviar evento a Kafka (topic: cp-events)
        try:
            self.producer.send('cp-events', registration_event, key=new_cp_id.encode())
            self.producer.flush()
            print(f"✅ Evento de registro enviado a topic 'cp-events'")
            
            # Esperar procesamiento con reintentos
            print("\n2️⃣ Esperando que Central procese el registro...")
            retries = 6
            cp_in_db = None
            for i in range(retries):
                time.sleep(1)
                cp_in_db = db.get_charging_point_by_id(new_cp_id)
                if cp_in_db:
                    break
            
            # Verificar en la base de datos si el CP fue registrado
            print("\n3️⃣ Verificando en base de datos...")
            if cp_in_db:
                print(f"✅ ÉXITO: Punto de carga registrado en la base de datos")
                print(f"   - CP ID: {cp_in_db['cp_id']}")
                print(f"   - Ubicación: {cp_in_db.get('location', 'N/A')}")
                print(f"   - Estado: {cp_in_db.get('status', 'N/A')}")
                print(f"   - Potencia: {cp_in_db.get('max_power_kw', 'N/A')} kW")
                return True
            else:
                print(f"⚠️ ADVERTENCIA: CP no encontrado en BD tras {retries}s")
                print(f"   Revisa logs de Central para ver si llegó el evento y si se auto-registró")
                return False
                
        except Exception as e:
            print(f"❌ Error enviando evento: {e}")
            return False
    
    def test_charging_authorization(self):
        """
        TEST B: Solicitud de autorización de suministro
        Simula un Driver que solicita iniciar carga
        """
        print("\n" + "-"*80)
        print("🔐 TEST B: Autorización de Suministro")
        print("-"*80)
        
        # Obtener un usuario y CP disponible de la BD
        print("\n1️⃣ Obteniendo usuario de prueba...")
        test_user = db.get_user_by_nombre('driver1')
        if not test_user:
            # Sembrar datos de prueba si no existe el usuario
            try:
                if hasattr(db, 'seed_test_data'):
                    db.seed_test_data()
                    test_user = db.get_user_by_nombre('driver1')
                else:
                    print("❌ Error: Usuario 'driver1' no encontrado y no se pudo sembrar datos")
                    return False
            except Exception as e:
                print(f"❌ Error sembrando datos de prueba: {e}")
                return False
        print(f"✅ Usuario: {test_user['nombre']} (Balance: €{test_user['balance']:.2f})")
        
        print("\n2️⃣ Buscando punto de carga disponible...")
        available_cps = db.get_available_charging_points()
        if not available_cps:
            # Forzar disponibilidad de un CP existente o registrar uno temporal
            try:
                # Intentar obtener cualquier CP y marcarlo como available
                all_cps = db.get_all_charging_points()
                if all_cps:
                    cp_any = all_cps[0]
                    db.update_charging_point_status(cp_any['cp_id'], 'available')
                    available_cps = db.get_available_charging_points()
                else:
                    # Registrar uno temporal
                    temp_cp_id = f"CP_TEST_{int(time.time())}"
                    if hasattr(db, 'register_or_update_charging_point'):
                        db.register_or_update_charging_point(temp_cp_id, 'Test Auto', max_kw=22.0, tarifa_kwh=0.28, estado='available')
                        available_cps = db.get_available_charging_points()
            except Exception as e:
                print(f"❌ Error asegurando CP disponible: {e}")
                return False
            if not available_cps:
                print("❌ Error: No se pudo asegurar un CP disponible")
                return False
        
        cp = available_cps[0]
        print(f"✅ CP disponible: {cp['cp_id']} en {cp['location']}")
        
        # Crear sesión y solicitar autorización
        print(f"\n3️⃣ Enviando solicitud de autorización de carga...")
        correlation_id = generate_message_id()
        
        # Crear sesión en BD (simulando que Driver ya la creó)
        session_id = db.create_charging_session(test_user['id'], cp['cp_id'], correlation_id)
        
        if not session_id:
            print("❌ Error creando sesión de carga")
            return False
        
        print(f"✅ Sesión creada: ID={session_id}")
        
        # Evento de solicitud de inicio de carga
        authorization_event = {
            'message_id': generate_message_id(),
            'event_type': 'CHARGING_AUTHORIZATION_REQUEST',
            'component': 'driver',
            'driver_id': 'Driver_Test_001',
            'action': 'charging_started',
                'username': test_user['nombre'],
            'user_id': test_user['id'],
            'cp_id': cp['cp_id'],
            'session_id': session_id,
            'timestamp': current_timestamp(),
            'correlation_id': correlation_id
        }
        
        # Enviar evento a Kafka (topic: driver-events)
        try:
            self.producer.send('driver-events', authorization_event, key='Driver_Test_001'.encode())
            self.producer.flush()
            print(f"✅ Evento de autorización enviado a topic 'driver-events'")
            
            # Esperar procesamiento
            print("\n4️⃣ Esperando que Central procese la autorización...")
            time.sleep(2)
            
            # Verificar estado del CP (debería cambiar a 'charging')
            print("\n5️⃣ Verificando cambio de estado del CP...")
            cp_updated = db.get_charging_point_by_id(cp['cp_id'])
            
            if cp_updated:
                current_status = cp_updated.get('status', 'unknown')
                print(f"   Estado actual del CP: {current_status}")
                
                if current_status == 'charging':
                    print(f"✅ ÉXITO: CP cambió a estado 'charging'")
                    print(f"   Central procesó correctamente la autorización")
                    
                    # Limpiar: detener la sesión
                    print(f"\n6️⃣ Limpiando: finalizando sesión de prueba...")
                    db.end_charging_sesion(session_id, 0.5)
                    print(f"✅ Sesión finalizada")
                    
                    return True
                else:
                    print(f"⚠️ ADVERTENCIA: Estado no cambió a 'charging'")
                    print(f"   Esto puede ser normal si Central no actualiza estado automáticamente")
                    print(f"   o si el evento no incluye cambio de estado")
                    
                    # Limpiar sesión de todos modos
                    db.end_charging_sesion(session_id, 0.5)
                    return False
            else:
                print(f"❌ Error: No se pudo verificar estado del CP")
                return False
                
        except Exception as e:
            print(f"❌ Error enviando evento: {e}")
            # Limpiar sesión en caso de error
            try:
                db.end_charging_session(session_id, energy_kwh=0)
            except:
                pass
            return False
    
    def run_tests(self):
        """Ejecuta todos los tests"""
        if not self.initialize_kafka():
            print("\n❌ No se pudo conectar a Kafka. Tests abortados.")
            print("   Asegúrate de que:")
            print("   1. Kafka está corriendo (docker-compose up)")
            print("   2. EV_Central está corriendo")
            return
        
        # Test A: Registro de CP
        test_a_result = self.test_charging_point_registration()
        
        # Test B: Autorización de carga
        test_b_result = self.test_charging_authorization()
        
        # Resumen
        print("\n" + "="*80)
        print(" 📊 RESUMEN DE TESTS")
        print("="*80)
        print(f"\nTEST A - Registro de CP:         {'✅ PASADO' if test_a_result else '⚠️ REVISAR'}")
        print(f"TEST B - Autorización de Carga:  {'✅ PASADO' if test_b_result else '⚠️ REVISAR'}")
        
        if test_a_result and test_b_result:
            print(f"\n🎉 ¡TODOS LOS TESTS PASARON!")
        else:
            print(f"\n⚠️ Algunos tests necesitan revisión")
            print(f"\nNotas:")
            print(f"- El test de registro puede fallar si Central no auto-registra CPs")
            print(f"- Verifica los logs de Central para ver si procesa los eventos")
            print(f"- Abre el dashboard de Central (http://localhost:8002) para monitorear")
        
        print("\n" + "="*80 + "\n")
        
        # Cerrar conexiones
        if self.producer:
            self.producer.close()
        if self.consumer:
            self.consumer.close()

if __name__ == "__main__":
    tester = CentralRequestTester()
    tester.run_tests()
