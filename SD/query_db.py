#!/usr/bin/env python3
"""
Script para consultar y visualizar datos de la base de datos EV Charging System
"""
import database as db
from datetime import datetime

def print_separator(char="=", length=80):
    print(char * length)

def print_header(title):
    print_separator()
    print(f"  {title}")
    print_separator()

def show_all_users():
    """Muestra todos los usuarios registrados"""
    print_header("USUARIOS REGISTRADOS")
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, role, balance, active FROM users ORDER BY role, username")
    users = cursor.fetchall()
    conn.close()
    
    print(f"{'ID':<5} {'Username':<20} {'Email':<30} {'Role':<10} {'Balance':>10} {'Active':<7}")
    print("-" * 80)
    for user in users:
        active_str = "✓" if user['active'] else "✗"
        print(f"{user['id']:<5} {user['username']:<20} {user['email']:<30} {user['role']:<10} €{user['balance']:>8.2f} {active_str:<7}")
    print(f"\nTotal usuarios: {len(users)}")

def show_all_charging_points():
    """Muestra todos los puntos de carga"""
    print_header("PUNTOS DE CARGA")
    cps = db.get_all_charging_points()
    
    print(f"{'CP ID':<10} {'Location':<35} {'Status':<12} {'Power':>8} {'Tariff':>10}")
    print("-" * 80)
    for cp in cps:
        status_emoji = "🟢" if cp['status'] == 'available' else "🔴" if cp['status'] == 'charging' else "🟡"
        print(f"{cp['cp_id']:<10} {cp['location']:<35} {status_emoji} {cp['status']:<10} {cp['max_power_kw']:>6.1f}kW €{cp['tariff_per_kwh']:>5.2f}/kWh")
    print(f"\nTotal puntos de carga: {len(cps)}")

def show_all_sessions():
    """Muestra todas las sesiones de carga"""
    print_header("SESIONES DE CARGA (Últimas 20)")
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, u.username, s.cp_id, s.start_time, s.end_time, 
               s.energy_kwh, s.cost, s.status
        FROM charging_sessions s
        JOIN users u ON s.user_id = u.id
        ORDER BY s.start_time DESC
        LIMIT 20
    """)
    sessions = cursor.fetchall()
    conn.close()
    
    print(f"{'ID':<5} {'User':<18} {'CP':<10} {'Start':<20} {'Energy':>10} {'Cost':>10} {'Status':<10}")
    print("-" * 95)
    for session in sessions:
        start_dt = datetime.fromtimestamp(session['start_time']).strftime('%Y-%m-%d %H:%M')
        energy = session['energy_kwh'] if session['energy_kwh'] else 0
        cost = session['cost'] if session['cost'] else 0
        status_emoji = "✓" if session['status'] == 'completed' else "⏳"
        print(f"{session['id']:<5} {session['username']:<18} {session['cp_id']:<10} {start_dt:<20} {energy:>8.2f}kWh €{cost:>7.2f} {status_emoji} {session['status']:<8}")
    print(f"\nTotal sesiones mostradas: {len(sessions)}")

def show_user_history(username):
    """Muestra el historial de un usuario específico"""
    user = db.get_user_by_username(username)
    if not user:
        print(f"❌ Usuario '{username}' no encontrado")
        return
    
    print_header(f"HISTORIAL DE {username.upper()}")
    print(f"Balance actual: €{user['balance']:.2f}")
    print()
    
    sessions = db.get_user_sessions(user['id'], limit=10)
    if not sessions:
        print("No hay sesiones registradas para este usuario")
        return
    
    print(f"{'ID':<5} {'CP':<10} {'Inicio':<20} {'Fin':<20} {'Energía':>10} {'Costo':>10}")
    print("-" * 80)
    total_energy = 0
    total_cost = 0
    for session in sessions:
        start_dt = datetime.fromtimestamp(session['start_time']).strftime('%Y-%m-%d %H:%M')
        end_str = "En curso" if not session['end_time'] else datetime.fromtimestamp(session['end_time']).strftime('%Y-%m-%d %H:%M')
        energy = session['energy_kwh'] if session['energy_kwh'] else 0
        cost = session['cost'] if session['cost'] else 0
        print(f"{session['id']:<5} {session['cp_id']:<10} {start_dt:<20} {end_str:<20} {energy:>8.2f}kWh €{cost:>7.2f}")
        total_energy += energy
        total_cost += cost
    
    print("-" * 80)
    print(f"{'TOTAL':<57} {total_energy:>8.2f}kWh €{total_cost:>7.2f}")

def show_statistics():
    """Muestra estadísticas generales del sistema"""
    print_header("ESTADÍSTICAS DEL SISTEMA")
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Usuarios
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE role='driver'")
    total_drivers = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE role='driver' AND active=1")
    active_drivers = cursor.fetchone()['total']
    
    # Puntos de carga
    cursor.execute("SELECT COUNT(*) as total FROM charging_points")
    total_cps = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM charging_points WHERE status='available'")
    available_cps = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM charging_points WHERE status='charging'")
    charging_cps = cursor.fetchone()['total']
    
    # Sesiones
    cursor.execute("SELECT COUNT(*) as total FROM charging_sessions")
    total_sessions = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM charging_sessions WHERE status='active'")
    active_sessions = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM charging_sessions WHERE status='completed'")
    completed_sessions = cursor.fetchone()['total']
    
    # Energía y costos
    cursor.execute("SELECT SUM(energy_kwh) as total FROM charging_sessions WHERE status='completed'")
    total_energy = cursor.fetchone()['total'] or 0
    
    cursor.execute("SELECT SUM(cost) as total FROM charging_sessions WHERE status='completed'")
    total_revenue = cursor.fetchone()['total'] or 0
    
    cursor.execute("SELECT AVG(energy_kwh) as avg FROM charging_sessions WHERE status='completed'")
    avg_energy = cursor.fetchone()['avg'] or 0
    
    # Top usuarios
    cursor.execute("""
        SELECT u.username, COUNT(s.id) as sessions, SUM(s.energy_kwh) as total_energy, SUM(s.cost) as total_cost
        FROM users u
        LEFT JOIN charging_sessions s ON u.id = s.user_id AND s.status='completed'
        WHERE u.role='driver'
        GROUP BY u.id
        ORDER BY total_cost DESC
        LIMIT 5
    """)
    top_users = cursor.fetchall()
    
    conn.close()
    
    # Mostrar estadísticas
    print("\n📊 USUARIOS")
    print(f"  Total drivers: {total_drivers}")
    print(f"  Drivers activos: {active_drivers}")
    
    print("\n🔌 PUNTOS DE CARGA")
    print(f"  Total: {total_cps}")
    print(f"  Disponibles: {available_cps} (🟢)")
    print(f"  En uso: {charging_cps} (🔴)")
    
    print("\n⚡ SESIONES DE CARGA")
    print(f"  Total: {total_sessions}")
    print(f"  Activas: {active_sessions}")
    print(f"  Completadas: {completed_sessions}")
    
    print("\n💰 ENERGÍA Y COSTOS")
    print(f"  Energía total despachada: {total_energy:.2f} kWh")
    print(f"  Energía promedio por sesión: {avg_energy:.2f} kWh")
    print(f"  Ingresos totales: €{total_revenue:.2f}")
    
    print("\n🏆 TOP 5 USUARIOS (por gasto)")
    print(f"  {'Username':<20} {'Sesiones':>10} {'Energía':>12} {'Total Gastado':>15}")
    print("  " + "-" * 60)
    for user in top_users:
        sessions = user['sessions'] or 0
        energy = user['total_energy'] or 0
        cost = user['total_cost'] or 0
        print(f"  {user['username']:<20} {sessions:>10} {energy:>10.2f}kWh €{cost:>12.2f}")

def main_menu():
    """Menú interactivo"""
    while True:
        print("\n" + "=" * 80)
        print("  EV CHARGING SYSTEM - CONSULTA DE BASE DE DATOS")
        print("=" * 80)
        print("\n  1. Ver todos los usuarios")
        print("  2. Ver todos los puntos de carga")
        print("  3. Ver sesiones de carga")
        print("  4. Ver historial de usuario")
        print("  5. Ver estadísticas del sistema")
        print("  6. Salir")
        
        choice = input("\n  Selecciona una opción (1-6): ").strip()
        
        if choice == '1':
            print()
            show_all_users()
        elif choice == '2':
            print()
            show_all_charging_points()
        elif choice == '3':
            print()
            show_all_sessions()
        elif choice == '4':
            username = input("\n  Introduce el username: ").strip()
            print()
            show_user_history(username)
        elif choice == '5':
            print()
            show_statistics()
        elif choice == '6':
            print("\n  👋 ¡Hasta luego!")
            break
        else:
            print("\n  ❌ Opción no válida")
        
        input("\n  Presiona ENTER para continuar...")

if __name__ == "__main__":
    print("\n🔋 EV Charging System - Consulta de Base de Datos")
    print(f"📁 Base de datos: {db.DB_PATH}")
    
    # Verificar si existe la BD
    if not db.DB_PATH.exists():
        print("\n❌ La base de datos no existe. Ejecuta 'python init_db.py' primero.")
    else:
        main_menu()
