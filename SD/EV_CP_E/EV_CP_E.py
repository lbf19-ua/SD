#!/usr/bin/env python3
"""
================================================================================
EV_CP_E - Electric Vehicle Charging Point Engine
================================================================================

DESCRIPCIÓN:
El Engine (Motor) es el componente que simula el hardware físico del punto de
carga. Es responsable de:
- Auto-registrarse al iniciar
- Ejecutar el proceso de carga real
- Responder a health checks del Monitor
- Reportar su estado a Central vía Kafka
- Simular consumo de energía durante la carga

ARQUITECTURA:
- Kafka Consumer: Escucha comandos de Central
- Kafka Producer: Publica eventos y cambios de estado
- TCP Server: Responde health checks del Monitor (cada 1 segundo)
- Threading: Simulación de carga en background

ESTADOS POSIBLES (según especificación):
- offline: Desconectado (gris)
- available: Disponible para cargar (verde)
- charging: Cargando actualmente (verde con ⚡)
- fault: Averiado - error de hardware (rojo)
- out_of_service: Fuera de servicio - mantenimiento (naranja)

================================================================================
"""

import sys
import os
import time
import json
import socket
import threading
import argparse
import random
from datetime import datetime

# Kafka imports
from kafka import KafkaProducer, KafkaConsumer

# Añadir el directorio padre al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network_config import ENGINE_CONFIG, KAFKA_BROKER as KAFKA_BROKER_DEFAULT, KAFKA_TOPICS
from event_utils import generate_message_id, current_timestamp


class EV_CP_Engine:
    """
    Engine del Charging Point - Simula el hardware físico del punto de carga
    """
    
    def __init__(self, cp_id, location, max_power_kw=22.0, tariff_per_kwh=0.30, 
                 health_check_port=5100, kafka_broker='localhost:9092'):
        """
        Inicializa el Engine del Charging Point
        
        Args:
            cp_id: ID único del punto de carga (ej: "CP_001")
            location: Ubicación física (ej: "Parking Norte")
            max_power_kw: Potencia máxima en kW
            tariff_per_kwh: Tarifa por kWh en euros
            health_check_port: Puerto TCP para health checks del Monitor
            kafka_broker: Dirección del broker Kafka
        """
        self.cp_id = cp_id
        self.location = location
        self.max_power_kw = max_power_kw
        self.tariff_per_kwh = tariff_per_kwh
        self.health_check_port = health_check_port
        self.kafka_broker = kafka_broker
        
        # Estado del CP
        self.status = 'offline'
        self.previous_status = 'offline'
        self._registered = False  # Flag para evitar re-registros
        
        # Sesión actual de carga
        self.current_session = None
        self.charging_thread = None
        self.stop_charging_flag = threading.Event()
        
        # Health check
        self.health_status = 'OK'  # OK o KO
        self.health_server_thread = None
        self.health_server_running = False
        
        # Kafka
        self.producer = None
        self.consumer = None
        self.running = True
        
        # Lock para thread safety
        self.lock = threading.Lock()
        
        print(f"\n{'='*80}")
        print(f"  ⚡ EV CHARGING POINT ENGINE - {self.cp_id}")
        print(f"{'='*80}")
        print(f"  📍 Location:        {self.location}")
        print(f"  ⚡ Max Power:        {self.max_power_kw} kW")
        print(f"  💶 Tariff:          €{self.tariff_per_kwh}/kWh")
        print(f"  🏥 Health Port:     {self.health_check_port}")
        print(f"  📡 Kafka Broker:    {self.kafka_broker}")
        print(f"{'='*80}\n")
    
    def initialize_kafka(self, max_retries=10):
        """Inicializa productor y consumidor de Kafka con reintentos"""
        print(f"[{self.cp_id}] 🔄 Connecting to Kafka at {self.kafka_broker}...")
        print(f"[{self.cp_id}] 📍 Broker address: {self.kafka_broker}")
        
        for attempt in range(max_retries):
            try:
                # Productor para enviar eventos
                print(f"[{self.cp_id}] 📤 Initializing producer...")
                # Producer sin api_version explícito (auto-detección)
                self.producer = KafkaProducer(
                    bootstrap_servers=self.kafka_broker,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    request_timeout_ms=30000,
                    retries=3,
                    acks='all'
                )
                
                # Consumidor para recibir comandos de Central
                print(f"[{self.cp_id}] 📥 Initializing consumer...")
                # Consumer sin api_version explícito (auto-detección)
                # Usar group_id único para evitar leer mensajes antiguos al reiniciar
                import time as time_module
                unique_group_id = f'engine_group_{self.cp_id}_{int(time_module.time())}'
                self.consumer = KafkaConsumer(
                    KAFKA_TOPICS['central_events'],
                    bootstrap_servers=self.kafka_broker,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='latest',  # Solo leer mensajes nuevos después de conectarse
                    group_id=unique_group_id,  # Group ID único por inicio
                    request_timeout_ms=30000,
                    session_timeout_ms=10000,
                    consumer_timeout_ms=5000
                )
                
                # Test producer connection - NO enviar mensaje de test al topic para evitar eventos UNKNOWN en Central
                # En su lugar, solo verificamos que el producer esté configurado correctamente
                print(f"[{self.cp_id}]  Verifying producer configuration...")
                # El flush() verificará que el producer funciona sin necesidad de enviar un mensaje
                # Si hay un error, se lanzará una excepción en el siguiente send real
                print(f"[{self.cp_id}]  Kafka producer configured successfully")
                print(f"[{self.cp_id}]  Listening to: {KAFKA_TOPICS['central_events']}")
                print(f"[{self.cp_id}]  Publishing to: {KAFKA_TOPICS['cp_events']}")
                return True
                
            except Exception as e:
                import traceback
                print(f"[{self.cp_id}] ⚠️  Attempt {attempt+1}/{max_retries} failed: {e}")
                print(f"[{self.cp_id}] 📋 Error details: {traceback.format_exc()}")
                if attempt < max_retries - 1:
                    print(f"[{self.cp_id}] ⏳ Retrying in 2 seconds...")
                    time.sleep(2)
                else:
                    print(f"[{self.cp_id}] ❌ Failed to connect to Kafka after {max_retries} attempts")
                    print(f"[{self.cp_id}] 💡 Verificar:")
                    print(f"[{self.cp_id}]    1. Kafka está corriendo en {self.kafka_broker}")
                    print(f"[{self.cp_id}]    2. Desde PC3, probar: telnet <IP_PC2> 9092")
                    print(f"[{self.cp_id}]    3. Firewall permite tráfico en puerto 9092 de PC2")
                    print(f"[{self.cp_id}]    4. Variable KAFKA_BROKER en .env de PC3: {self.kafka_broker}")
                    return False
    
    def publish_event(self, event_type, data=None):
        """
        Publica un evento en Kafka
        
        Args:
            event_type: Tipo de evento
            data: Datos adicionales del evento
        
        ⚠️ PROTECCIÓN: Limita la frecuencia de publicación de cp_status_change para evitar bucles.
        """
        if not self.producer:
            print(f"[{self.cp_id}] ⚠️  Cannot publish event: Kafka producer not initialized")
            return
        
        # ⚠️ PROTECCIÓN: Throttling para cp_status_change - no publicar más de una vez por segundo
        if event_type == 'cp_status_change':
            if not hasattr(self, '_last_status_change_publish'):
                self._last_status_change_publish = 0
            
            current_time = time.time()
            time_since_last = current_time - self._last_status_change_publish
            
            if time_since_last < 1.0:  # Mínimo 1 segundo entre cambios de estado
                status = data.get('status') if data else 'unknown'
                print(f"[{self.cp_id}] ⚠️ Throttling: cp_status_change a '{status}' ya se publicó hace {time_since_last:.2f}s, omitiendo para evitar bucle")
                return
            
            self._last_status_change_publish = current_time
        
        try:
            # ⚠️ CRÍTICO: Asegurar que SIEMPRE incluimos cp_id y engine_id en TODOS los eventos
            # Esto permite que el Monitor filtre correctamente eventos de otros CPs
            event = {
                'message_id': generate_message_id(),
                'event_type': event_type,
                'cp_id': self.cp_id,  # ⚠️ SIEMPRE incluir cp_id para filtrado en Monitor
                'engine_id': self.cp_id,  # ⚠️ También incluir engine_id como fallback
                'timestamp': current_timestamp()
            }
            
            if data:
                # Si data ya tiene cp_id o engine_id, asegurar que coinciden con self.cp_id
                # Esto previene errores donde se envía un evento con cp_id incorrecto
                if 'cp_id' in data and data['cp_id'] != self.cp_id:
                    print(f"[{self.cp_id}] ⚠️  Warning: data contains cp_id={data['cp_id']} but self.cp_id={self.cp_id}, using self.cp_id")
                    data['cp_id'] = self.cp_id
                if 'engine_id' in data and data['engine_id'] != self.cp_id:
                    data['engine_id'] = self.cp_id
                event.update(data)
            
            # ⚠️ VERIFICACIÓN FINAL: Asegurar que cp_id y engine_id están correctos
            if event.get('cp_id') != self.cp_id or event.get('engine_id') != self.cp_id:
                print(f"[{self.cp_id}] ❌ ERROR: Event cp_id mismatch! event.cp_id={event.get('cp_id')}, self.cp_id={self.cp_id}")
                event['cp_id'] = self.cp_id
                event['engine_id'] = self.cp_id
            
            self.producer.send(KAFKA_TOPICS['cp_events'], event)
            self.producer.flush()
            
            print(f"[{self.cp_id}] 📤 Published event: {event_type} (cp_id: {event.get('cp_id')})")
            
        except Exception as e:
            print(f"[{self.cp_id}] ❌ Error publishing event: {e}")
    
    def change_status(self, new_status, reason=None):
        """
        Cambia el estado del CP y publica el evento
        
        Args:
            new_status: Nuevo estado del CP
            reason: Razón del cambio (opcional)
        """
        with self.lock:
            if self.status == new_status:
                return  # No hay cambio
            
            self.previous_status = self.status
            self.status = new_status
            
            print(f"[{self.cp_id}] 🔄 Status change: {self.previous_status} → {new_status}")
            if reason:
                print(f"[{self.cp_id}]    Reason: {reason}")
        
        # ⚠️ PROTECCIÓN: Si acabamos de registrarnos y el estado es 'available', no publicar cp_status_change
        # porque CP_REGISTRATION ya incluye el estado 'available'
        if new_status == 'available' and hasattr(self, '_registered') and self._registered:
            # Verificar si el registro fue reciente (menos de 5 segundos)
            if not hasattr(self, '_registration_time'):
                self._registration_time = 0
            import time
            time_since_reg = time.time() - self._registration_time
            if time_since_reg < 5.0:
                print(f"[{self.cp_id}] ℹ Ignorando cp_status_change a 'available' - ya incluido en CP_REGISTRATION ({time_since_reg:.1f}s)")
                return
        
        # Publicar cambio de estado
        self.publish_event('cp_status_change', {
            'action': 'cp_status_change',
            'status': new_status,
            'previous_status': self.previous_status,
            'reason': reason
        })
    
    def auto_register(self):
        """
        Auto-registro del CP al iniciar
        Envía información del CP a Central para que lo registre en BD
        Solo se registra UNA VEZ al iniciar
        """
        # Flag para asegurar que solo nos registramos una vez
        if hasattr(self, '_registered') and self._registered:
            print(f"[{self.cp_id}] ⚠️ Already registered, skipping auto-registration")
            return
        
        print(f"[{self.cp_id}] 📝 Auto-registering with Central...")
        
        # Marcar que ya nos registramos para evitar re-registros
        self._registered = True
        
        # Cambiar a estado available ANTES de enviar el registro
        # Esto evita enviar dos eventos separados
        import time
        with self.lock:
            if self.status == 'offline':
                self.previous_status = self.status
                self.status = 'available'
                print(f"[{self.cp_id}]  Status change: {self.previous_status} → available")
        
        # ⚠️ REGISTRAR timestamp del registro para evitar cp_status_change subsecuentes
        self._registration_time = time.time()
        
        # Enviar UN SOLO evento CP_REGISTRATION con toda la información incluido el estado
        # Central lo registrará directamente como 'available' sin necesidad de cp_status_change
        self.publish_event('CP_REGISTRATION', {
            'action': 'connect',
            'status': 'available',  # Incluir estado directamente en el registro
            'data': {
                'location': self.location,
                'localizacion': self.location,
                'max_kw': self.max_power_kw,
                'max_power_kw': self.max_power_kw,
                'tarifa_kwh': self.tariff_per_kwh,
                'tariff_per_kwh': self.tariff_per_kwh,
                'price_eur_kwh': self.tariff_per_kwh,
                'status': 'available',  # También en data para compatibilidad
                'estado': 'available'
            }
        })
        
        print(f"[{self.cp_id}] ✅ Registration request sent to Central (status: available)")
    
    def start_health_check_server(self):
        """
        Inicia servidor TCP para responder a health checks del Monitor
        El Monitor envía "STATUS?" cada segundo y esperamos responder "OK" o "KO"
        """
        def health_server():
            try:
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind(('0.0.0.0', self.health_check_port))
                server_socket.listen(5)
                server_socket.settimeout(1.0)  # Timeout para poder chequear self.running
                
                self.health_server_running = True
                print(f"[{self.cp_id}] 🏥 Health check server started on port {self.health_check_port}")
                print(f"[{self.cp_id}] 🏥 Listening on 0.0.0.0:{self.health_check_port}, waiting for connections...")
                
                while self.running:
                    try:
                        client_socket, address = server_socket.accept()
                        # No imprimir cada conexión - reduce ruido en logs
                        client_socket.settimeout(5.0)
                        
                        try:
                            # Recibir mensaje del Monitor
                            data = client_socket.recv(1024).decode('utf-8').strip()
                            # No imprimir cada mensaje STATUS? - reduce ruido
                            
                            if data == "STATUS?":
                                # Responder según el estado actual
                                with self.lock:
                                    if self.status == 'fault':
                                        response = "KO"
                                    else:
                                        response = self.health_status
                                
                                # No imprimir cada respuesta - reduce ruido
                                # Enviar respuesta directamente sin verificar el socket primero
                                # getpeername() puede fallar incluso si el socket es válido
                                response_bytes = (response + '\n').encode('utf-8')
                                
                                try:
                                    # Intentar enviar directamente - sendall garantiza que todos los bytes se envíen
                                    # o devuelve error si el socket está cerrado
                                    client_socket.sendall(response_bytes)
                                    # No imprimir cada envío exitoso - reduce ruido
                                except (OSError, socket.error) as send_error:
                                    # Socket se cerró durante o antes del envío
                                    errno = getattr(send_error, 'errno', None)
                                    error_str = str(send_error)
                                    if errno == 22 or "Invalid argument" in error_str:
                                        # [Errno 22] Invalid argument - el Monitor probablemente cerró la conexión
                                        # o el socket está en un estado inválido
                                        # Intentar enviar con send() si sendall() falló
                                        try:
                                            bytes_sent = client_socket.send(response_bytes)
                                            # Solo imprimir si falló completamente - reduce ruido
                                            if bytes_sent == 0:
                                                pass  # Socket cerrado - normal, no imprimir
                                        except:
                                            # Socket completamente cerrado - no se puede enviar
                                            # Esto es normal si el Monitor cerró la conexión - no imprimir
                                            pass
                                    else:
                                        # Otro error de socket - solo imprimir si es grave
                                        if self.running:  # Solo si seguimos corriendo
                                            pass  # Errores de socket comunes - no imprimir
                                        # No lanzar error - el Monitor probablemente ya cerró la conexión
                                except Exception as send_error:
                                    # Error inesperado - solo imprimir si es crítico
                                    if self.running and "Broken pipe" not in str(send_error):
                                        # Solo errores críticos, no errores normales de socket cerrado
                                        pass  # Reducir ruido
                                    # No lanzar - continuar normalmente
                            else:
                                # Comando desconocido - solo imprimir si no es vacío
                                if data:
                                    print(f"[{self.cp_id}] ⚠️  Unknown health check command: {data}")
                                
                        except socket.timeout:
                            # Timeout normal - no imprimir para reducir ruido
                            pass
                        except Exception as e:
                            # No contar errores de socket después de enviar la respuesta como errores críticos
                            # Estos pueden ocurrir si el Monitor cierra la conexión
                            error_str = str(e)
                            if "Invalid argument" in error_str or "[Errno 22]" in error_str:
                                # Error de socket - probablemente el Monitor cerró la conexión
                                # Esto es normal después de enviar la respuesta
                                pass  # No imprimir ni lanzar - es comportamiento esperado
                            else:
                                print(f"[{self.cp_id}] ⚠️  Error processing health check: {e}")
                        finally:
                            # Cerrar la conexión limpiamente
                            # Verificar si el socket está todavía abierto antes de cerrar
                            try:
                                # Intentar cerrar solo si el socket está abierto
                                # Si el Monitor ya cerró la conexión, esto puede fallar con [Errno 22]
                                client_socket.shutdown(socket.SHUT_RDWR)
                            except (OSError, socket.error):
                                # Socket ya cerrado o error - continuar
                                pass
                            except:
                                pass
                            
                            try:
                                client_socket.close()
                            except:
                                pass
                            
                            # No imprimir si todo salió bien - reducir ruido en logs
                            # print(f"[{self.cp_id}] 🏥 Health check connection closed")
                            
                    except socket.timeout:
                        continue  # Timeout normal, continuar esperando
                    except Exception as e:
                        if self.running:  # Solo mostrar error si seguimos corriendo
                            print(f"[{self.cp_id}] ⚠️  Health check error: {e}")
                            import traceback
                            traceback.print_exc()
                
                server_socket.close()
                print(f"[{self.cp_id}] 🏥 Health check server stopped")
                
            except Exception as e:
                print(f"[{self.cp_id}] ❌ Health server error: {e}")
                self.health_server_running = False
        
        self.health_server_thread = threading.Thread(target=health_server, daemon=True)
        self.health_server_thread.start()
        
        # Esperar un poco a que el thread arranque
        time.sleep(0.5)
        
        # Verificar que el thread está corriendo
        if not self.health_server_thread.is_alive():
            print(f"[{self.cp_id}] ❌ ERROR: Health server thread failed to start!")
            raise RuntimeError("Health server thread failed to start")
    
    def start_charging_simulation(self, user_id, username):
        """
        Inicia la simulación de carga en un thread separado
        
        Args:
            user_id: ID del usuario
            username: Nombre del usuario
        """
        def charging_loop():
            print(f"[{self.cp_id}] ⚡ Starting charging simulation for user: {username}")
            
            start_time = time.time()
            energy_kwh = 0.0
            
            # Potencia de carga simulada (entre 80-95% de la máxima)
            charging_power = self.max_power_kw * random.uniform(0.80, 0.95)
            
            while not self.stop_charging_flag.is_set():
                time.sleep(1)  # Actualizar cada segundo
                
                # Calcular energía acumulada
                elapsed_hours = (time.time() - start_time) / 3600.0
                energy_kwh = elapsed_hours * charging_power
                cost = energy_kwh * self.tariff_per_kwh
                
                # Actualizar sesión actual
                with self.lock:
                    if self.current_session:
                        self.current_session['energy_kwh'] = energy_kwh
                        self.current_session['cost'] = cost
                
                # ⏱️ REQUISITO 8: Publicar actualización CADA SEGUNDO
                self.publish_event('charging_progress', {
                    'action': 'charging_progress',
                    'username': username,
                    'user_id': user_id,
                    'energy_kwh': round(energy_kwh, 3),
                    'cost': round(cost, 2),
                    'power_kw': round(charging_power, 2)
                })
            
            # Carga detenida
            print(f"[{self.cp_id}] ⛔ Charging stopped for {username}")
            print(f"[{self.cp_id}]    Energy: {energy_kwh:.2f} kWh | Cost: €{cost:.2f}")
        
        self.stop_charging_flag.clear()
        self.charging_thread = threading.Thread(target=charging_loop, daemon=True)
        self.charging_thread.start()
    
    def listen_for_commands(self):
        """
        Escucha comandos de Central vía Kafka
        Thread principal que procesa eventos
        """
        if not self.consumer:
            print(f"[{self.cp_id}] ❌ Cannot listen: Kafka consumer not initialized")
            return
        
        print(f"[{self.cp_id}] 👂 Listening for commands from Central...")
        print(f"[{self.cp_id}] 📡 Topic: {KAFKA_TOPICS['central_events']}")
        print(f"[{self.cp_id}] 🔌 Kafka broker: {self.kafka_broker}")
        print(f"[{self.cp_id}] ⏳ Waiting for messages...")
        
        try:
            # Verificar que el consumer está funcionando
            print(f"[{self.cp_id}] ✅ Kafka consumer ready, entering message loop...")
            for message in self.consumer:
                if not self.running:
                    break
                
                event = message.value
                event_type = event.get('event_type', '')
                action = event.get('action', '')
                
                # Filtrar solo eventos relevantes para este CP
                event_cp_id = event.get('cp_id')
                
                # Debug: Log todos los eventos recibidos
                print(f"[{self.cp_id}] 📨 Evento recibido: type={event_type}, action={action}, cp_id={event_cp_id}")
                
                # Procesar eventos globales o específicos para este CP
                if event_cp_id and event_cp_id != self.cp_id:
                    print(f"[{self.cp_id}] ⏭️  Ignorando evento para otro CP: {event_cp_id}")
                    continue  # No es para nosotros
                
                print(f"[{self.cp_id}] ✅ Procesando evento: {event_type or action}")
                
                # ============================================================
                # RESPUESTA DE AUTORIZACIÓN
                # ============================================================
                if event_type == 'AUTHORIZATION_RESPONSE':
                    authorized = event.get('authorized', False)
                    response_cp_id = event.get('cp_id')
                    
                    if response_cp_id == self.cp_id and authorized:
                        print(f"[{self.cp_id}] ✅ Authorization granted by Central")
                        # El estado cambiará a 'charging' cuando Central publique charging_started
                
                # ============================================================
                # INICIO DE CARGA (Central ya autorizó)
                # ============================================================
                elif action == 'charging_started':
                    target_cp = event.get('cp_id')
                    if target_cp == self.cp_id:
                        username = event.get('username')
                        user_id = event.get('user_id')
                        
                        with self.lock:
                            if self.status not in ['available', 'reserved']:
                                print(f"[{self.cp_id}] ⚠️  Cannot start charging: status is {self.status}")
                                continue
                            
                            # Crear sesión
                            self.current_session = {
                                'username': username,
                                'user_id': user_id,
                                'start_time': time.time(),
                                'energy_kwh': 0.0,
                                'cost': 0.0
                            }
                        
                        # Cambiar a charging (fuera del lock para evitar deadlock)
                        self.change_status('charging', f'Charging started for user {username}')
                        
                        # Iniciar simulación de carga
                        self.start_charging_simulation(user_id, username)
                
                # ============================================================
                # DETENER CARGA
                # ============================================================
                elif action == 'charging_stopped':
                    target_cp = event.get('cp_id')
                    if target_cp == self.cp_id:
                        with self.lock:
                            if self.status != 'charging' or not self.current_session:
                                print(f"[{self.cp_id}] ⚠️  Not charging, ignoring stop command")
                                continue
                            
                            # Detener simulación
                            self.stop_charging_flag.set()
                            
                            # Esperar a que termine el thread
                            if self.charging_thread and self.charging_thread.is_alive():
                                self.charging_thread.join(timeout=2)
                            
                            # Obtener datos finales
                            final_energy = self.current_session.get('energy_kwh', 0.0)
                            final_cost = self.current_session.get('cost', 0.0)
                            username = self.current_session.get('username')
                            
                            # Limpiar sesión
                            self.current_session = None
                        
                        # Cambiar a available (fuera del lock para evitar deadlock)
                        self.change_status('available', 'Charging completed')
                        
                        print(f"[{self.cp_id}] ✅ Charging session completed")
                        print(f"[{self.cp_id}]    User: {username}")
                        print(f"[{self.cp_id}]    Energy: {final_energy:.2f} kWh")
                        print(f"[{self.cp_id}]    Cost: €{final_cost:.2f}")
                
                # ============================================================
                # SIMULACIÓN DE ERROR (desde Admin)
                # ============================================================
                elif event_type == 'CP_ERROR_SIMULATED' or action == 'cp_error_simulated':
                    target_cp = event.get('cp_id')
                    if target_cp == self.cp_id:
                        error_type = event.get('error_type', 'fault')
                        new_status = event.get('new_status', 'fault')
                        
                        print(f"[{self.cp_id}] 🚨 Simulating error: {error_type}")
                        
                        # Si hay carga activa, detenerla
                        with self.lock:
                            if self.status == 'charging' and self.current_session:
                                self.stop_charging_flag.set()
                                if self.charging_thread and self.charging_thread.is_alive():
                                    self.charging_thread.join(timeout=2)
                                self.current_session = None
                        
                        # Cambiar estado
                        self.change_status(new_status, f'Admin simulated error: {error_type}')
                        
                        # Cambiar health status para que Monitor detecte
                        if new_status == 'fault':
                            self.health_status = 'KO'
                
                # ============================================================
                # REPARACIÓN (desde Admin)
                # ============================================================
                elif event_type == 'CP_ERROR_FIXED' or action == 'cp_error_fixed':
                    target_cp = event.get('cp_id')
                    if target_cp == self.cp_id:
                        print(f"[{self.cp_id}] 🔧 Error fixed by Admin")
                        
                        # Restaurar health status
                        self.health_status = 'OK'
                        
                        # Cambiar a available
                        self.change_status('available', 'Error fixed by admin')
                
                # ============================================================
                # REQUISITO 13a: PARAR CP (desde Admin)
                # ============================================================
                elif event_type == 'CP_STOP' or action == 'stop':
                    target_cp = event.get('cp_id')
                    if target_cp == self.cp_id:
                        reason = event.get('reason', 'Stopped by admin')
                        print(f"[{self.cp_id}] 🛑 STOP command received from Central")
                        print(f"[{self.cp_id}]    Reason: {reason}")
                        
                        # Si hay carga activa, detenerla
                        with self.lock:
                            if self.status == 'charging' and self.current_session:
                                print(f"[{self.cp_id}] ⚠️  Interrupting active charging session")
                                self.stop_charging_flag.set()
                                
                                # Esperar a que termine
                                if self.charging_thread and self.charging_thread.is_alive():
                                    self.charging_thread.join(timeout=2)
                                
                                self.current_session = None
                        
                        # Cambiar a out_of_service (FUERA DE SERVICIO - ROJO)
                        self.change_status('out_of_service', reason)
                        print(f"[{self.cp_id}] 🔴 CP is now OUT OF SERVICE")
                
                # ============================================================
                # REQUISITO 13b: REANUDAR CP (desde Admin)
                # ============================================================
                elif event_type == 'CP_RESUME' or action == 'resume':
                    target_cp = event.get('cp_id')
                    if target_cp == self.cp_id:
                        reason = event.get('reason', 'Resumed by admin')
                        print(f"[{self.cp_id}] ▶️  RESUME command received from Central")
                        print(f"[{self.cp_id}]    Reason: {reason}")
                        
                        # Cambiar a available (ACTIVADO - VERDE)
                        self.change_status('available', reason)
                        print(f"[{self.cp_id}] 🟢 CP is now AVAILABLE")
                
                # ============================================================
                # REQUISITO 7: ENCHUFAR VEHÍCULO (desde CLI remoto)
                # ============================================================
                elif event_type == 'CP_PLUG_IN' or action == 'plug_in':
                    target_cp = event.get('cp_id')
                    if target_cp == self.cp_id:
                        print(f"[{self.cp_id}] 🔌 PLUG_IN command received (from remote CLI)")
                        self.simulate_plug_in()
                
                # ============================================================
                # REQUISITO 9: DESENCHUFAR VEHÍCULO (desde CLI remoto)
                # ============================================================
                elif event_type == 'CP_UNPLUG' or action == 'unplug':
                    target_cp = event.get('cp_id')
                    if target_cp == self.cp_id:
                        print(f"[{self.cp_id}] 🔌 UNPLUG command received (from remote CLI)")
                        # Ejecutar simulate_unplug que detiene la carga y envía ticket
                        result = self.simulate_unplug()
                        if result:
                            print(f"[{self.cp_id}] ✅ Desenchufado completado - Ticket enviado al conductor")
                        else:
                            print(f"[{self.cp_id}] ⚠️  No había sesión activa para desenchufar")
                
        except KeyboardInterrupt:
            print(f"\n[{self.cp_id}] ⚠️  Interrupted by user")
        except Exception as e:
            print(f"[{self.cp_id}] ❌ Error in command listener: {e}")
            import traceback
            traceback.print_exc()
    
    def simulate_plug_in(self):
        """
        REQUISITO 7: Simula que el conductor enchufa su vehículo
        """
        with self.lock:
            if self.status != 'reserved':
                print(f"\n[{self.cp_id}] ⚠️  Cannot plug in: CP not reserved (status: {self.status})")
                print(f"[{self.cp_id}]    Wait for authorization from Central first")
                return False
            
            if self.current_session:
                print(f"\n[{self.cp_id}] ✅ Vehicle plugged in successfully")
                print(f"[{self.cp_id}]    User: {self.current_session.get('username')}")
                print(f"[{self.cp_id}]    Charging will begin automatically\n")
                return True
            else:
                print(f"\n[{self.cp_id}] ⚠️  No active session to plug in\n")
                return False
    
    def simulate_unplug(self):
        """
        REQUISITO 9: Simula que el conductor desenchufa su vehículo del CP
        Esto finaliza el suministro y notifica a Central para enviar el ticket
        """
        with self.lock:
            if self.status != 'charging' or not self.current_session:
                print(f"\n[{self.cp_id}] ⚠️  No active charging session to unplug\n")
                return False
            
            # Obtener datos de la sesión antes de detenerla
            username = self.current_session.get('username')
            user_id = self.current_session.get('user_id')
            final_energy = self.current_session.get('energy_kwh', 0.0)
            final_cost = self.current_session.get('cost', 0.0)
            start_time = self.current_session.get('start_time', time.time())
            duration_sec = time.time() - start_time
            
            print(f"\n[{self.cp_id}] 🔌 Vehicle unplugged by user")
            print(f"[{self.cp_id}]    User: {username}")
            print(f"[{self.cp_id}]    Energy: {final_energy:.2f} kWh")
            print(f"[{self.cp_id}]    Cost: €{final_cost:.2f}")
            print(f"[{self.cp_id}]    Duration: {duration_sec:.0f}s\n")
            
            # Detener el thread de carga
            self.stop_charging_flag.set()
        
        # Esperar a que termine el thread (fuera del lock)
        if self.charging_thread and self.charging_thread.is_alive():
            self.charging_thread.join(timeout=2)
        
        # Notificar a Central con todos los datos finales
        self.publish_event('charging_completed', {
            'action': 'charging_completed',
            'username': username,
            'user_id': user_id,
            'energy_kwh': round(final_energy, 3),
            'cost': round(final_cost, 2),
            'duration_sec': int(duration_sec),
            'reason': 'unplugged_by_user'
        })
        
        with self.lock:
            # Limpiar sesión
            self.current_session = None
        
        # Volver a estado disponible (fuera del lock para evitar deadlock)
        self.change_status('available', 'Vehicle unplugged - Ready for next charge')
        
        print(f"[{self.cp_id}] ✅ Session ended - CP is available again\n")
        return True
    
    def start_cli_menu(self):
        """
        REQUISITO 7 y 9: Menú CLI interactivo para simular acciones del usuario
        Se ejecuta en un thread separado
        """
        def cli_loop():
            print(f"\n{'='*80}")
            print(f"  🎮 INTERACTIVE CLI MENU - {self.cp_id}")
            print(f"{'='*80}")
            print("  Commands available:")
            print("    [P] Plug in    - Simulate vehicle connection")
            print("    [U] Unplug     - Simulate vehicle disconnection (finishes charging)")
            print("    [F] Fault      - Simulate hardware failure (reports KO to Monitor)")
            print("    [R] Recover    - Recover from failure (reports OK to Monitor)")
            print("    [S] Status     - Show current CP status")
            print("    [Q] Quit       - Shutdown the CP")
            print(f"{'='*80}\n")
            
            while self.running:
                try:
                    # Non-blocking input con timeout
                    import sys
                    import select
                    
                    # Windows no soporta select en stdin, usar alternativa
                    if sys.platform == 'win32':
                        # En Windows, simplemente esperamos input (bloqueante)
                        # Usamos un pequeño timeout en el loop principal
                        if not self.running:
                            break
                        
                        cmd = input(f"[{self.cp_id}] Command (P/U/F/R/S/Q): ").strip().upper()
                        
                        if cmd == 'P':
                            self.simulate_plug_in()
                        elif cmd == 'U':
                            self.simulate_unplug()
                        elif cmd == 'F':
                            # Simular fallo - reportar KO al Monitor
                            print(f"\n[{self.cp_id}] 🚨 SIMULATING HARDWARE FAILURE")
                            with self.lock:
                                self.health_status = 'KO'
                            self.change_status('fault', 'Hardware failure simulated')
                            print(f"[{self.cp_id}] ⚠️  Health status set to KO")
                            print(f"[{self.cp_id}] ⚠️  Monitor will detect this and report to Central\n")
                        elif cmd == 'R':
                            # Recuperarse del fallo - volver a OK
                            print(f"\n[{self.cp_id}] ✅ RECOVERING FROM FAILURE")
                            with self.lock:
                                self.health_status = 'OK'
                                has_session = bool(self.current_session)
                                is_fault = (self.status == 'fault')
                            
                            # Si no hay sesión activa, volver a available
                            if not has_session:
                                self.change_status('available', 'Recovered from failure')
                            elif is_fault:
                                # Si hay sesión activa en fault, volver a charging
                                self.change_status('charging', 'Recovered from failure')
                            
                            print(f"[{self.cp_id}] ✅ Health status set to OK")
                            print(f"[{self.cp_id}] ✅ CP is operational again\n")
                        elif cmd == 'S':
                            with self.lock:
                                print(f"\n{'='*60}")
                                print(f"  📊 STATUS REPORT - {self.cp_id}")
                                print(f"{'='*60}")
                                print(f"  Status:       {self.status}")
                                print(f"  Health:       {self.health_status}")
                                print(f"  Location:     {self.location}")
                                print(f"  Max Power:    {self.max_power_kw} kW")
                                print(f"  Tariff:       €{self.tariff_per_kwh}/kWh")
                                if self.current_session:
                                    print(f"  Active User:  {self.current_session.get('username')}")
                                    print(f"  Energy:       {self.current_session.get('energy_kwh', 0):.2f} kWh")
                                    print(f"  Cost:         €{self.current_session.get('cost', 0):.2f}")
                                else:
                                    print(f"  Active User:  None")
                                print(f"{'='*60}\n")
                        elif cmd == 'Q':
                            print(f"\n[{self.cp_id}] Initiating shutdown...")
                            self.running = False
                            break
                        elif cmd:
                            print(f"[{self.cp_id}] Unknown command: {cmd}\n")
                    else:
                        # Linux/Mac: usar select para non-blocking
                        time.sleep(0.5)
                        if select.select([sys.stdin], [], [], 0)[0]:
                            cmd = sys.stdin.readline().strip().upper()
                            # Procesar comando igual que en Windows
                            # ... (mismo código que arriba)
                        
                except KeyboardInterrupt:
                    print(f"\n[{self.cp_id}] CLI menu interrupted")
                    break
                except EOFError:
                    # Input cerrado, salir del loop
                    break
                except Exception as e:
                    if self.running:
                        print(f"[{self.cp_id}] CLI error: {e}")
                    time.sleep(0.5)
        
        cli_thread = threading.Thread(target=cli_loop, daemon=False)
        cli_thread.start()
        return cli_thread
    
    def shutdown(self):
        """Apaga el Engine limpiamente"""
        print(f"\n[{self.cp_id}] 🛑 Shutting down...")
        
        self.running = False
        
        # Detener carga si hay alguna activa
        if self.current_session:
            self.stop_charging_flag.set()
            if self.charging_thread and self.charging_thread.is_alive():
                self.charging_thread.join(timeout=2)
        
        # Cambiar estado a offline antes de apagar
        self.change_status('offline', 'Engine shutting down')
        
        # Cerrar Kafka
        if self.producer:
            self.producer.close()
        if self.consumer:
            self.consumer.close()
        
        print(f"[{self.cp_id}] ✅ Shutdown complete")
    
    def run(self):
        """
        Método principal - inicia todos los servicios
        """
        # 1. Conectar a Kafka
        if not self.initialize_kafka():
            print(f"[{self.cp_id}] ❌ Cannot continue without Kafka")
            return
        
        # 2. Auto-registrarse en Central
        self.auto_register()
        
        # 3. Iniciar servidor de health checks
        self.start_health_check_server()
        
        # Esperar a que el health server arranque y verificar que está escuchando
        max_wait = 5  # Esperar hasta 5 segundos
        wait_interval = 0.5  # Verificar cada 0.5 segundos
        waited = 0
        while not self.health_server_running and waited < max_wait:
            time.sleep(wait_interval)
            waited += wait_interval
        
        if not self.health_server_running:
            print(f"[{self.cp_id}] ⚠️  Warning: Health server may not be ready after {waited}s")
        else:
            print(f"[{self.cp_id}] ✅ Health server verified running after {waited:.1f}s")
        
        print(f"\n[{self.cp_id}] ✅ All systems operational")
        print(f"[{self.cp_id}] 🔋 Ready to charge vehicles\n")
        
        # 4. Iniciar menú CLI interactivo (opcional)
        cli_thread = None
        if hasattr(self, 'enable_cli') and self.enable_cli:
            cli_thread = self.start_cli_menu()
        
        # 5. Escuchar comandos (bloqueante)
        try:
            self.listen_for_commands()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()
            # Esperar a que el CLI termine
            if cli_thread and cli_thread.is_alive():
                cli_thread.join(timeout=2)


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='EV Charging Point Engine - Simulates physical charging hardware'
    )
    parser.add_argument(
        '--cp-id',
        default=os.environ.get('CP_ID', ENGINE_CONFIG.get('engine_id', 'CP_001')),
        help='Charging Point ID (default: from env CP_ID or config)'
    )
    parser.add_argument(
        '--location',
        default=os.environ.get('LOCATION', ENGINE_CONFIG.get('location', 'Unknown Location')),
        help='Physical location of the charging point (default: from env LOCATION or config)'
    )
    parser.add_argument(
        '--max-power',
        type=float,
        default=float(os.environ.get('MAX_POWER', '22.0')),
        help='Maximum power output in kW (default: 22.0 or env MAX_POWER)'
    )
    parser.add_argument(
        '--tariff',
        type=float,
        default=float(os.environ.get('TARIFF', str(ENGINE_CONFIG.get('price_eur_kwh', 0.30)))),
        help='Price per kWh in euros (default: 0.30 or env TARIFF)'
    )
    parser.add_argument(
        '--health-port',
        type=int,
        default=int(os.environ.get('HEALTH_PORT', str(ENGINE_CONFIG.get('engine_port', 5100)))),
        help='TCP port for health checks (default: 5100 or env HEALTH_PORT)'
    )
    parser.add_argument(
        '--kafka-broker',
        default=os.environ.get('KAFKA_BROKER', ENGINE_CONFIG.get('kafka_broker', KAFKA_BROKER_DEFAULT)),
        help='Kafka broker address (default: from env KAFKA_BROKER or config)'
    )
    parser.add_argument(
        '--no-cli',
        action='store_true',
        default=False,
        help='Disable interactive CLI menu (default: CLI enabled)'
    )
    
    args = parser.parse_args()
    
    # Crear e iniciar el Engine
    engine = EV_CP_Engine(
        cp_id=args.cp_id,
        location=args.location,
        max_power_kw=args.max_power,
        tariff_per_kwh=args.tariff,
        health_check_port=args.health_port,
        kafka_broker=args.kafka_broker
    )
    
    # Configurar si el CLI debe estar habilitado
    engine.enable_cli = not args.no_cli
    
    try:
        engine.run()
    except KeyboardInterrupt:
        print("\n\n Stopped by user")
    except Exception as e:
        print(f"\n Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

