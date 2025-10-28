#!/usr/bin/env python3
import sqlite3
from pathlib import Path

db_path = Path('ev_charging.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# SESIONES ACTIVAS
print("\n" + "="*80)
print("SESIONES ACTIVAS (sin end_time):")
print("="*80)
cursor = conn.cursor()
cursor.execute("""
    SELECT s.id, s.user_id, u.nombre as username, s.cp_id, 
           s.start_time, s.energia_kwh, s.estado
    FROM charging_sesiones s
    JOIN usuarios u ON s.user_id = u.id
    WHERE s.end_time IS NULL
    ORDER BY s.start_time DESC
""")

sessions = cursor.fetchall()
if sessions:
    print(f"  [ERROR] HAY {len(sessions)} SESIONES ACTIVAS SIN CERRAR:")
    for s in sessions:
        print(f"    Sesion ID {s['id']}: user_id={s['user_id']} ({s['username']}) en {s['cp_id']}")
        print(f"      Start: {s['start_time']}, Estado: {s['estado']}")
else:
    print("  [OK] No hay sesiones activas sin cerrar")

# PUNTOS DE CARGA
print("\n" + "="*80)
print("ESTADO PUNTOS DE CARGA:")
print("="*80)
cursor.execute("SELECT cp_id, estado, localizacion FROM charging_points ORDER BY cp_id")
cps = cursor.fetchall()
for cp in cps:
    print(f"  {cp['cp_id']}: {cp['estado']} - {cp['localizacion']}")

# VERIFICACION
print("\n" + "="*80)
print("VERIFICACION:")
print("="*80)

# Ver si hay CPs en 'charging' sin sesion activa
cursor.execute("""
    SELECT cp.cp_id, cp.estado
    FROM charging_points cp
    LEFT JOIN charging_sesiones s ON cp.cp_id = s.cp_id AND s.end_time IS NULL
    WHERE cp.estado = 'charging' AND s.id IS NULL
""")
orphans = cursor.fetchall()
if orphans:
    print(f"  [ERROR] HAY {len(orphans)} CPs en 'charging' SIN sesion activa:")
    for cp in orphans:
        print(f"    - {cp['cp_id']}")
else:
    print("  [OK] Todos los CPs en 'charging' tienen sesion activa")

# Ver ultimas sesiones finalizadas
print("\n" + "="*80)
print("ULTIMAS 5 SESIONES FINALIZADAS:")
print("="*80)
cursor.execute("""
    SELECT s.id, u.nombre as username, s.cp_id, s.energia_kwh, s.coste,
           s.start_time, s.end_time
    FROM charging_sesiones s
    JOIN usuarios u ON s.user_id = u.id
    WHERE s.end_time IS NOT NULL
    ORDER BY s.end_time DESC
    LIMIT 5
""")
finished = cursor.fetchall()
if finished:
    for s in finished:
        print(f"  Sesion {s['id']}: {s['username']} en {s['cp_id']}")
        print(f"    Energia: {s['energia_kwh']:.2f} kWh, Coste: {s['coste']:.2f} EUR")
else:
    print("  [WARN] No hay sesiones finalizadas")

conn.close()
print("\n" + "="*80)
print("\nDIAGNOSTICO:")
print("  Si hay sesiones activas sin end_time:")
print("    -> Central NO esta procesando correctamente charging_stopped")
print("  Si hay CPs en 'charging' sin sesion:")
print("    -> Hubo un fallo en la sincronizacion")
print("="*80 + "\n")

