#!/usr/bin/env python3
"""
================================================================================
CP Control - Script para controlar un Charging Point remotamente
================================================================================

Este script permite enviar comandos a un CP sin necesidad de acceder directamente
al contenedor Docker. Se conecta vía Kafka para enviar comandos al CP.

USO:
    python cp_control.py CP_001 [comando]

Comandos disponibles:
    [P] plug      - Simular que el vehículo se enchufa
    [U] unplug    - Simular desenchufado (finaliza carga y envía ticket)
    [F] fault     - Simular fallo de hardware
    [R] recover   - Recuperarse del fallo
    [S] status    - Mostrar estado actual del CP

Ejemplo:
    python cp_control.py CP_001 unplug
    python cp_control.py CP_001 status
================================================================================
"""

import sys
import os
import argparse
import json

# Añadir el directorio padre al path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from network_config import KAFKA_BROKER as KAFKA_BROKER_DEFAULT, KAFKA_TOPICS
    from event_utils import generate_message_id, current_timestamp
except ImportError as e:
    print(f"❌ Error importando módulos: {e}")
    print(f"   Script dir: {script_dir}")
    print(f"   Parent dir: {parent_dir}")
    print(f"   Sys.path: {sys.path[:3]}")
    sys.exit(1)

# Kafka imports
try:
    from kafka import KafkaProducer
except ImportError:
    print("❌ Error: kafka-python no está instalado")
    print("   Instala con: pip install kafka-python")
    sys.exit(1)


def send_command(cp_id, command, kafka_broker=None):
    """
    Envía un comando al CP vía Kafka
    
    Args:
        cp_id: ID del Charging Point
        command: Comando a enviar (plug, unplug, fault, recover, status)
        kafka_broker: Dirección del broker Kafka (default: KAFKA_BROKER_DEFAULT)
    """
    # Usar broker por defecto si no se especifica
    if kafka_broker is None:
        kafka_broker = KAFKA_BROKER_DEFAULT
    
    command_map = {
        'plug': 'plug_in',
        'p': 'plug_in',
        'unplug': 'unplug',
        'u': 'unplug',
        'fault': 'fault',
        'f': 'fault',
        'recover': 'recover',
        'r': 'recover',
        'status': 'status',
        's': 'status'
    }
    
    cmd_normalized = command.lower().strip()
    if cmd_normalized not in command_map:
        print(f"❌ Comando desconocido: {command}")
        print(f"   Comandos disponibles: {', '.join(set(command_map.keys()))}")
        return False
    
    action = command_map[cmd_normalized]
    
    try:
        # Conectar a Kafka sin api_version explícito (auto-detección)
        print(f"📡 Conectando a Kafka broker: {kafka_broker}")
        print(f"   ℹ️  Verificando conectividad...")
        
        # Intentar conectar con timeout más corto inicialmente para diagnóstico
        try:
            producer = KafkaProducer(
                bootstrap_servers=kafka_broker,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                request_timeout_ms=30000,
                retries=3,
                acks='all'  # Esperar confirmación de todos los replicas
            )
            print(f"✅ Conectado a Kafka exitosamente")
        except Exception as conn_error:
            print(f"❌ Error de conexión a Kafka: {conn_error}")
            print(f"\n💡 Diagnóstico:")
            print(f"   1. Verifica que Kafka está corriendo en: {kafka_broker}")
            print(f"   2. Verifica conectividad de red:")
            print(f"      Windows: Test-NetConnection 192.168.1.235 -Port 9092")
            print(f"      Linux:   telnet 192.168.1.235 9092")
            print(f"   3. Verifica firewall: puerto 9092 debe estar abierto")
            print(f"   4. Si estás en PC3, asegúrate de poder alcanzar PC2 (192.168.1.235)")
            raise
        
        # Crear evento según el comando
        if action == 'status':
            # Para status, simplemente informamos que el comando se envió
            # El CP debería mostrar su estado internamente
            print(f"📤 Enviando comando STATUS a {cp_id}...")
            print(f"   (El estado se mostrará en los logs del CP)")
        else:
            event = {
                'message_id': generate_message_id(),
                'event_type': f'CP_{action.upper()}',
                'action': action,
                'cp_id': cp_id,
                'timestamp': current_timestamp()
            }
            
            # Enviar a través del topic de eventos de Central
            topic = KAFKA_TOPICS['central_events']
            print(f"📤 Enviando comando '{action}' al topic '{topic}' para CP {cp_id}...")
            
            # Enviar evento
            future = producer.send(topic, event)
            
            # Esperar confirmación
            record_metadata = future.get(timeout=10)
            
            producer.flush()
            
            print(f"✅ Comando '{action}' enviado exitosamente a {cp_id}")
            print(f"   📍 Topic: {record_metadata.topic}")
            print(f"   📍 Partition: {record_metadata.partition}")
            print(f"   📍 Offset: {record_metadata.offset}")
            
            if action == 'unplug':
                print(f"   ℹ️  El CP procesará el desenchufado y enviará el ticket al conductor")
        
        producer.close()
        return True
        
    except Exception as e:
        print(f"❌ Error enviando comando: {e}")
        import traceback
        traceback.print_exc()
        return False


def interactive_menu(cp_id, kafka_broker=None):
    """
    Menú interactivo para controlar el CP
    """
    # Usar broker por defecto si no se especifica
    if kafka_broker is None:
        kafka_broker = KAFKA_BROKER_DEFAULT
    
    print(f"\n{'='*80}")
    print(f"  🎮 CP CONTROL MENU - {cp_id}")
    print(f"{'='*80}")
    print(f"  📡 Kafka Broker: {kafka_broker}")
    print(f"  📋 Topic: {KAFKA_TOPICS['central_events']}")
    print(f"{'='*80}")
    print("  Commands available:")
    print("    [P] Plug in    - Simulate vehicle connection")
    print("    [U] Unplug     - Simulate vehicle disconnection (finishes charging)")
    print("    [F] Fault      - Simulate hardware failure")
    print("    [R] Recover    - Recover from failure")
    print("    [S] Status     - Show current CP status")
    print("    [Q] Quit       - Exit control menu")
    print(f"{'='*80}\n")
    
    while True:
        try:
            cmd = input(f"[{cp_id}] Command (P/U/F/R/S/Q): ").strip().upper()
            
            if cmd == 'Q' or cmd == 'QUIT':
                print("👋 Saliendo del menú de control...")
                break
            elif cmd:
                send_command(cp_id, cmd, kafka_broker)
            else:
                print("⚠️  Comando vacío")
                
        except KeyboardInterrupt:
            print("\n👋 Saliendo del menú de control...")
            break
        except EOFError:
            break


def main():
    parser = argparse.ArgumentParser(
        description='Control remoto de Charging Points vía Kafka',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s CP_001 unplug          # Desenchufar vehículo en CP_001
  %(prog)s CP_001 --interactive   # Abrir menú interactivo
  %(prog)s CP_002 fault           # Simular fallo en CP_002
        """
    )
    
    parser.add_argument(
        'cp_id',
        nargs='?',
        default=None,
        help='ID del Charging Point (ej: CP_001). Si no se especifica, se pedirá interactivamente.'
    )
    
    parser.add_argument(
        'command',
        nargs='?',
        default=None,
        help='Comando a ejecutar (plug, unplug, fault, recover, status). Si no se especifica, se abre menú interactivo.'
    )
    
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Forzar menú interactivo (por defecto se abre si no hay comando)'
    )
    
    parser.add_argument(
        '--kafka-broker',
        default=os.environ.get('KAFKA_BROKER', KAFKA_BROKER_DEFAULT),
        help=f'Dirección del broker Kafka (default: {KAFKA_BROKER_DEFAULT})'
    )
    
    args = parser.parse_args()
    
    # Si no se especifica cp_id, pedirlo interactivamente
    cp_id = args.cp_id
    if not cp_id:
        print("\n🎮 CP Control - Menú Interactivo\n")
        cp_id = input("Ingresa el ID del Charging Point (ej: CP_001): ").strip()
        if not cp_id:
            print("❌ Error: Se requiere un CP_ID")
            sys.exit(1)
    
    # Si se especifica --interactive o no se da comando, abrir menú interactivo
    if args.interactive or not args.command:
        interactive_menu(cp_id, args.kafka_broker)
    else:
        # Ejecutar comando directamente
        success = send_command(cp_id, args.command, args.kafka_broker)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

