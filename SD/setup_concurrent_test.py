#!/usr/bin/env python3
"""
Script para preparar la base de datos para el test de concurrencia
Crea 10 usuarios y 10 puntos de carga
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import database as db

def setup_test_data():
    """Prepara usuarios y CPs para el test de concurrencia"""
    
    print("=" * 80)
    print("🔧 PREPARACIÓN DE BASE DE DATOS PARA TEST DE CONCURRENCIA")
    print("=" * 80)
    
    # Usuarios de prueba (además de los existentes)
    test_users = [
        ("test1", "test123", "test1@example.com", "driver", 200.0),
        ("test2", "test123", "test2@example.com", "driver", 200.0),
        ("test3", "test123", "test3@example.com", "driver", 200.0),
        ("test4", "test123", "test4@example.com", "driver", 200.0),
        ("test5", "test123", "test5@example.com", "driver", 200.0),
    ]
    
    print("\n📝 Creando usuarios de prueba...")
    for username, password, email, role, balance in test_users:
        try:
            # Verificar si ya existe
            existing = db.get_user_by_nombre(username)
            if existing:
                print(f"   ⏭️  Usuario '{username}' ya existe (Balance: €{existing['balance']:.2f})")
            else:
                # Crear usuario
                conn = db.get_connection()
                cursor = conn.cursor()
                
                import hashlib
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                
                cursor.execute("""
                    INSERT INTO usuarios (nombre, contraseña, email, role, balance)
                    VALUES (?, ?, ?, ?, ?)
                """, (username, password_hash, email, role, balance))
                
                conn.commit()
                print(f"   ✅ Usuario '{username}' creado (Balance: €{balance:.2f})")
        except Exception as e:
            print(f"   ❌ Error creando usuario '{username}': {e}")
    
    # Puntos de carga de prueba
    charging_points = [
        ("CP_001", "Campus Norte", 22.0, 0.30),
        ("CP_002", "Campus Sur", 22.0, 0.30),
        ("CP_003", "Biblioteca", 50.0, 0.35),
        ("CP_004", "Polideportivo", 22.0, 0.28),
        ("CP_005", "Cafetería", 22.0, 0.30),
        ("CP_006", "Facultad Ciencias", 50.0, 0.35),
        ("CP_007", "Facultad Derecho", 22.0, 0.30),
        ("CP_008", "Residencias", 22.0, 0.28),
        ("CP_009", "Aparcamiento Principal", 50.0, 0.35),
        ("CP_010", "Salida Campus", 22.0, 0.30),
    ]
    
    print("\n🔌 Creando/actualizando puntos de carga...")
    for cp_id, location, max_kw, tariff in charging_points:
        try:
            # Registrar o actualizar
            db.register_or_update_charging_point(
                cp_id=cp_id,
                localizacion=location,
                max_kw=max_kw,
                tarifa_kwh=tariff,
                estado='available'
            )
            print(f"   ✅ CP '{cp_id}' en '{location}' ({max_kw}kW, €{tariff}/kWh)")
        except Exception as e:
            print(f"   ❌ Error con CP '{cp_id}': {e}")
    
    # Mostrar resumen
    print("\n" + "=" * 80)
    print("📊 RESUMEN DE LA BASE DE DATOS")
    print("=" * 80)
    
    # Contar usuarios
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE role = 'driver'")
    num_drivers = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM charging_points WHERE estado = 'available'")
    num_available_cps = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM charging_points")
    num_total_cps = cursor.fetchone()[0]
    
    print(f"\n👥 Conductores disponibles: {num_drivers}")
    print(f"🔌 Puntos de carga totales: {num_total_cps}")
    print(f"✅ Puntos de carga disponibles: {num_available_cps}")
    
    # Mostrar todos los usuarios driver
    print("\n" + "-" * 80)
    print("👥 USUARIOS DISPONIBLES PARA TESTING:")
    print("-" * 80)
    
    cursor.execute("""
        SELECT nombre, balance, email
        FROM usuarios
        WHERE role = 'driver'
        ORDER BY nombre
    """)
    
    for row in cursor.fetchall():
        print(f"   • {row[0]:20s} | Balance: €{row[1]:8.2f} | {row[2]}")
    
    # Mostrar todos los CPs
    print("\n" + "-" * 80)
    print("🔌 PUNTOS DE CARGA DISPONIBLES:")
    print("-" * 80)
    
    cursor.execute("""
        SELECT cp_id, localizacion, estado, max_kw, tarifa_kwh
        FROM charging_points
        ORDER BY cp_id
    """)
    
    for row in cursor.fetchall():
        estado_emoji = "✅" if row[2] == "available" else "🔴"
        print(f"   {estado_emoji} {row[0]:10s} | {row[1]:25s} | {row[2]:15s} | {row[3]:5.1f}kW | €{row[4]:.2f}/kWh")
    
    print("\n" + "=" * 80)
    print("✅ Base de datos preparada para el test de concurrencia")
    print("=" * 80)
    print("\n💡 Ahora puedes ejecutar:")
    print("   python test_concurrent_charging.py -n 10 -d 5")
    print()


if __name__ == "__main__":
    setup_test_data()
