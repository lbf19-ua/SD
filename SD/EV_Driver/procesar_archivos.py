#!/usr/bin/env python3
# ============================================================================
# Script Auxiliar para Procesar Archivos de Servicios
# ============================================================================
"""
Este script puede usarse para procesar archivos de servicios automáticamente
desde la línea de comandos, útil para pruebas automatizadas.

Uso:
    python procesar_archivos.py servicios.txt user1
    python procesar_archivos.py servicios2.txt user2
"""

import sys
import os
from pathlib import Path

def load_services_from_file(file_path):
    """
    Carga lista de CPs desde archivo de servicios.
    
    Formato esperado:
    CP_001
    CP_002
    CP_003
    ...
    """
    services = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and line.startswith('CP_'):
                    services.append(line)
        print(f"✅ Archivo cargado: {len(services)} servicios de {file_path}")
        return services
    except FileNotFoundError:
        print(f"❌ Archivo no encontrado: {file_path}")
        return []
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")
        return []

def print_services_summary(services):
    """Muestra resumen de los servicios cargados"""
    print("\n" + "=" * 60)
    print("  📄 SERVICIOS DE CARGA")
    print("=" * 60)
    
    for i, cp_id in enumerate(services, 1):
        print(f"  {i:2d}. {cp_id}")
    
    print(f"\nTotal: {len(services)} puntos de carga")
    print("=" * 60 + "\n")

def main():
    """Función principal"""
    if len(sys.argv) < 2:
        print("Uso: python procesar_archivos.py <archivo.txt> [usuario]")
        print("\nEjemplo:")
        print("  python procesar_archivos.py servicios.txt user1")
        print("  python procesar_archivos.py servicios2.txt user2")
        print("\nArchivos disponibles:")
        for f in Path(__file__).parent.glob("servicios*.txt"):
            print(f"  - {f.name}")
        return
    
    file_path = sys.argv[1]
    username = sys.argv[2] if len(sys.argv) > 2 else "driver1"
    
    print("\n" + "=" * 60)
    print("  🔋 PROCESADOR DE ARCHIVOS DE SERVICIOS")
    print("=" * 60)
    print(f"Archivo: {file_path}")
    print(f"Usuario: {username}")
    print("=" * 60)
    
    services = load_services_from_file(file_path)
    
    if services:
        print_services_summary(services)
        print("ℹ️  Para procesar estos servicios automáticamente:")
        print("   1. Accede a http://localhost:8001")
        print(f"   2. Login como {username}")
        print("   3. Selecciona el archivo 'servicios.txt'")
        print("   4. Click en 'Procesar archivo'")
        print("")
        print("   Esto iniciará y detendrá cada carga secuencialmente.")
    else:
        print("⚠️  No se pudieron cargar servicios")

if __name__ == "__main__":
    main()

