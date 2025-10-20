#!/usr/bin/env python3
"""
Test script para probar la simulación interactiva del EV_CP_E (Engine)
Incluye simulación de fallos con teclado.
"""

import subprocess
import time
import sys
import os

def test_engine_interactive():
    """
    Prueba la funcionalidad interactiva del motor EV_CP_E
    """
    print("🔋 TESTING EV_CP_E INTERACTIVE SIMULATION")
    print("="*60)
    print("Este script probará la simulación interactiva del motor.")
    print("Asegúrate de que EV_Central esté ejecutándose.")
    print("="*60)
    
    # Verificar que EV_Central esté ejecutándose
    print("⚠️  IMPORTANTE: Asegúrate de que EV_Central esté ejecutándose antes de continuar.")
    input("Presiona ENTER para continuar cuando EV_Central esté listo...")
    
    print("\n🚀 Iniciando EV_CP_E en modo interactivo...")
    print("Una vez iniciado, podrás usar:")
    print("  🔴 K + ENTER → Simular fallo")
    print("  🟢 O + ENTER → Restaurar funcionamiento")
    print("  ❌ Q + ENTER → Salir")
    print("\n" + "="*60 + "\n")
    
    try:
        # Cambiar al directorio del script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # Ejecutar EV_CP_E en modo interactivo
        subprocess.run([
            sys.executable, 
            "EV_CP_E/EV_CP_E.py", 
            "--interactive",
            "--engine-id", "Engine_Interactive_Test"
        ])
        
    except KeyboardInterrupt:
        print("\n[TEST] Simulación interrumpida por el usuario")
    except Exception as e:
        print(f"[TEST] Error ejecutando la simulación: {e}")

def test_engine_basic():
    """
    Prueba básica del motor EV_CP_E (sin interactividad)
    """
    print("🔋 TESTING EV_CP_E BASIC MODE")
    print("="*60)
    
    try:
        # Cambiar al directorio del script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # Ejecutar EV_CP_E en modo básico
        subprocess.run([
            sys.executable, 
            "EV_CP_E/EV_CP_E.py", 
            "--engine-id", "Engine_Basic_Test"
        ])
        
    except Exception as e:
        print(f"[TEST] Error ejecutando el test básico: {e}")

if __name__ == "__main__":
    print("🔋 EV CHARGING SYSTEM - ENGINE TESTING")
    print("="*60)
    print("Selecciona el modo de prueba:")
    print("1. Modo Interactivo (con simulación de fallos)")
    print("2. Modo Básico (solo prueba de conexión)")
    print("3. Salir")
    print("="*60)
    
    while True:
        try:
            choice = input("\nSelecciona una opción (1-3): ").strip()
            
            if choice == "1":
                test_engine_interactive()
                break
            elif choice == "2":
                test_engine_basic()
                break
            elif choice == "3":
                print("¡Hasta luego!")
                break
            else:
                print("❌ Opción inválida. Usa 1, 2 o 3.")
                
        except KeyboardInterrupt:
            print("\n¡Hasta luego!")
            break
        except Exception as e:
            print(f"Error: {e}")