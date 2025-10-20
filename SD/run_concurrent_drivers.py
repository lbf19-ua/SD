#!/usr/bin/env python3
"""
Script para lanzar múltiples EV_Driver de forma concurrente
Permite simular varios clientes conectándose al mismo tiempo
"""

import subprocess
import threading
import time
import sys
import os

def run_driver(driver_id, services_file, delay=0):
    """
    Ejecuta un Driver específico con un delay opcional
    """
    if delay > 0:
        print(f"[LAUNCHER] Driver {driver_id} will start in {delay} seconds...")
        time.sleep(delay)
    
    print(f"[LAUNCHER] Starting Driver {driver_id}...")
    
    cmd = [
        sys.executable,
        "EV_Driver/EV_Driver.py",
        "--broker-ip", "localhost",
        "--broker-port", "9092", 
        "--central-ip", "172.27.135.138",
        "--central-port", "5000",
        "--driver-id", driver_id,
        "--services-file", services_file
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"[LAUNCHER] Driver {driver_id} finished with return code: {result.returncode}")
        if result.stdout:
            print(f"[LAUNCHER] Driver {driver_id} output:\n{result.stdout}")
        if result.stderr:
            print(f"[LAUNCHER] Driver {driver_id} errors:\n{result.stderr}")
    except Exception as e:
        print(f"[LAUNCHER] Error running Driver {driver_id}: {e}")

def main():
    """
    Lanza múltiples Drivers de forma concurrente
    """
    print("=" * 60)
    print("🚗 EV DRIVER CONCURRENT TEST")
    print("=" * 60)
    
    # Configuración de los drivers a lanzar
    drivers_config = [
        ("Cliente_001", "EV_Driver/servicios.txt", 0),      # Sin delay
        ("Cliente_002", "EV_Driver/servicios2.txt", 2),    # 2 segundos de delay
        ("Cliente_003", "EV_Driver/servicios3.txt", 1),    # 1 segundo de delay
    ]
    
    # Lista para mantener referencia a los hilos
    threads = []
    
    # Lanzar cada driver en un hilo separado
    for driver_id, services_file, delay in drivers_config:
        thread = threading.Thread(
            target=run_driver,
            args=(driver_id, services_file, delay),
            name=f"Driver-{driver_id}"
        )
        threads.append(thread)
        thread.start()
    
    print(f"[LAUNCHER] {len(threads)} drivers launched concurrently!")
    
    # Esperar a que todos los hilos terminen
    for thread in threads:
        thread.join()
    
    print("=" * 60)
    print("✅ ALL DRIVERS COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    main()