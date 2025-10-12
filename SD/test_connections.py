#!/usr/bin/env python3
"""
Script de prueba para verificar las conexiones entre todos los componentes del sistema EV Charging
"""

import subprocess
import time
import sys
import os

def start_central():
    """Inicia el servidor EV_Central"""
    print("🚀 Starting EV_Central server...")
    central_path = os.path.join("EV_Central", "EV_Central.py")
    return subprocess.Popen([sys.executable, central_path])

def test_driver():
    """Prueba la conexión del EV_Driver"""
    print("🚗 Testing EV_Driver connection...")
    driver_path = os.path.join("EV_Driver", "EV_Driver.py")
    result = subprocess.run([sys.executable, driver_path], capture_output=True, text=True)
    return result.returncode == 0

def test_monitor():
    """Prueba la conexión del EV_CP_M (Monitor)"""
    print("📊 Testing EV_CP_M (Monitor) connection...")
    monitor_path = os.path.join("EV_CP_M", "EV_CP_M.py")
    result = subprocess.run([sys.executable, monitor_path], capture_output=True, text=True)
    return result.returncode == 0

def test_engine():
    """Prueba la conexión del EV_CP_E (Engine)"""
    print("⚡ Testing EV_CP_E (Engine) connection...")
    engine_path = os.path.join("EV_CP_E", "EV_CP_E.py")
    result = subprocess.run([sys.executable, engine_path], capture_output=True, text=True)
    return result.returncode == 0

def main():
    """Función principal de prueba"""
    print("=" * 50)
    print("🔋 EV CHARGING SYSTEM - CONNECTION TEST")
    print("=" * 50)
    
    # Iniciar el servidor central
    central_process = start_central()
    
    try:
        # Esperar un poco para que el servidor se inicie
        time.sleep(2)
        
        # Probar cada componente
        results = {
            'Driver': test_driver(),
            'Monitor': test_monitor(), 
            'Engine': test_engine()
        }
        
        # Mostrar resultados
        print("\n" + "=" * 50)
        print("📋 CONNECTION TEST RESULTS")
        print("=" * 50)
        
        for component, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"{component:10} : {status}")
        
        # Resumen
        total_tests = len(results)
        passed_tests = sum(results.values())
        
        print(f"\nTests passed: {passed_tests}/{total_tests}")
        
        if passed_tests == total_tests:
            print("🎉 All components connected successfully!")
        else:
            print("⚠️  Some components failed to connect.")
            
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    
    finally:
        # Terminar el servidor central
        print("\n🔌 Stopping EV_Central server...")
        central_process.terminate()
        central_process.wait()
        print("✅ Server stopped")

if __name__ == "__main__":
    main()