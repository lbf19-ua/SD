#!/usr/bin/env python3
"""
Script de inicialización de la base de datos para EV Charging System
Ejecutar antes del primer uso del sistema
"""
import database as db

if __name__ == "__main__":
    print("=" * 60)
    print("  Inicializando Base de Datos - EV Charging System")
    print("=" * 60)
    
    # Inicializar esquema
    db.init_database()
    
    # Cargar datos de prueba
    db.seed_test_data()
    
    print("\n" + "=" * 60)
    print("  USUARIOS DE PRUEBA CREADOS")
    print("=" * 60)
    print("  Username: driver1         | Password: pass123   | Balance: €150.00")
    print("  Username: driver2         | Password: pass456   | Balance: €200.00")
    print("  Username: driver3         | Password: pass789   | Balance: €75.50")
    print("  Username: driver4         | Password: pass321   | Balance: €300.00")
    print("  Username: driver5         | Password: pass654   | Balance: €25.75")
    print("  Username: maria_garcia    | Password: maria2025 | Balance: €180.00")
    print("  Username: juan_lopez      | Password: juan123   | Balance: €95.25")
    print("  Username: ana_martinez    | Password: ana456    | Balance: €220.00")
    print("  Username: pedro_sanchez   | Password: pedro789  | Balance: €45.00")
    print("  Username: laura_fernandez | Password: laura321  | Balance: €165.50")
    print("  Username: admin           | Password: admin123  | Balance: €0.00 (admin)")
    print("  Username: operator1       | Password: oper123   | Balance: €0.00 (operator)")
    
    print("\n" + "=" * 60)
    print("  PUNTOS DE CARGA REGISTRADOS")
    print("=" * 60)
    cps = db.get_all_charging_points()
    for cp in cps:
        print(f"  {cp['cp_id']:8s} - {cp['location']:30s} - {cp['max_power_kw']:6.1f}kW - €{cp['tariff_per_kwh']:.2f}/kWh")
    
    # Mostrar estadísticas
    print("\n" + "=" * 60)
    print("  ESTADÍSTICAS DEL SISTEMA")
    print("=" * 60)
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE role='driver'")
    total_drivers = cursor.fetchone()['total']
    print(f"  Total Drivers: {total_drivers}")
    
    cursor.execute("SELECT COUNT(*) as total FROM charging_points")
    total_cps = cursor.fetchone()['total']
    print(f"  Total Charging Points: {total_cps}")
    
    cursor.execute("SELECT COUNT(*) as total FROM charging_sessions WHERE status='completed'")
    total_sessions = cursor.fetchone()['total']
    print(f"  Sesiones Completadas: {total_sessions}")
    
    cursor.execute("SELECT SUM(energy_kwh) as total FROM charging_sessions WHERE status='completed'")
    total_energy = cursor.fetchone()['total'] or 0
    print(f"  Energía Total Despachada: {total_energy:.2f} kWh")
    
    cursor.execute("SELECT SUM(cost) as total FROM charging_sessions WHERE status='completed'")
    total_revenue = cursor.fetchone()['total'] or 0
    print(f"  Ingresos Totales: €{total_revenue:.2f}")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("  ✅ Base de datos inicializada correctamente")
    print(f"  📁 Ubicación: {db.DB_PATH}")
    print("=" * 60)
    print("\n  Puedes ahora ejecutar EV_Central.py")
