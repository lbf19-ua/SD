#!/usr/bin/env python3
"""
Script simple para pruebas manuales del sistema EV Charging
Ejecuta cada componente individualmente para verificar conexiones
"""

import os
import sys

def show_menu():
    """Muestra el menú de opciones"""
    print("\n" + "=" * 40)
    print("🔋 EV CHARGING SYSTEM - MANUAL TEST")
    print("=" * 40)
    print("1. Start EV_Central (Server)")
    print("2. Test EV_Driver connection")
    print("3. Test EV_CP_M (Monitor) connection") 
    print("4. Test EV_CP_E (Engine) connection")
    print("5. Exit")
    print("=" * 40)

def run_central():
    """Ejecuta EV_Central"""
    print("🚀 Starting EV_Central server...")
    print("Press Ctrl+C to stop the server")
    os.system(f"{sys.executable} EV_Central/EV_Central.py")

def run_driver():
    """Ejecuta EV_Driver"""
    print("🚗 Running EV_Driver test...")
    os.system(f"{sys.executable} EV_Driver/EV_Driver.py")

def run_monitor():
    """Ejecuta EV_CP_M"""
    print("📊 Running EV_CP_M (Monitor) test...")
    os.system(f"{sys.executable} EV_CP_M/EV_CP_M.py")

def run_engine():
    """Ejecuta EV_CP_E"""
    print("⚡ Running EV_CP_E (Engine) test...")
    os.system(f"{sys.executable} EV_CP_E/EV_CP_E.py")

def main():
    """Función principal"""
    while True:
        show_menu()
        
        try:
            choice = input("\nSelect an option (1-5): ").strip()
            
            if choice == '1':
                run_central()
            elif choice == '2':
                run_driver()
            elif choice == '3':
                run_monitor()
            elif choice == '4':
                run_engine()
            elif choice == '5':
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid option. Please select 1-5.")
                
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()