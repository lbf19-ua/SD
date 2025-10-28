#!/usr/bin/env python3
import sqlite3
from pathlib import Path

db_path = Path('ev_charging.db')
if not db_path.exists():
    print("ERROR: Base de datos no encontrada")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# SESIONES ACTIVAS
print("\n" + "="*80)
print("SESIONES ACTIVAS (sin fecha_fin):")
print("="*80)
cursor = conn.cursor()
cursor.execute("""
    SELECT s.id, s.usuario_id, u.username, s.cp_id, cp.cp_id as cp_code, 
           s.fecha_inicio, cp.status as cp_status
    FROM sesiones_carga s
    JOIN usuarios u ON s.usuario_id = u.id
    JOIN puntos_recarga cp ON s.cp_id = cp.id
    WHERE s.fecha_fin IS NULL
    ORDER BY s.fecha_inicio DESC
""")

sessions = cursor.fetchall()
if sessions:
    for s in sessions:
        print(f"  Sesion ID {s['id']}: {s['username']} en {s['cp_code']} (CP status: {s['cp_status']})")
        print(f"    Inicio: {s['fecha_inicio']}")
else:
    print("  [OK] No hay sesiones activas")

# PUNTOS DE CARGA
print("\n" + "="*80)
print("ESTADO PUNTOS DE CARGA:")
print("="*80)
cursor.execute("SELECT cp_id, status, location FROM puntos_recarga ORDER BY cp_id")
for cp in cursor.fetchall():
    print(f"  {cp['cp_id']}: {cp['status']} - {cp['location']}")

# VERIFICACION
print("\n" + "="*80)
print("VERIFICACION:")
print("="*80)
cursor.execute("""
    SELECT cp.cp_id, cp.status
    FROM puntos_recarga cp
    LEFT JOIN sesiones_carga s ON cp.id = s.cp_id AND s.fecha_fin IS NULL
    WHERE cp.status = 'charging' AND s.id IS NULL
""")
orphans = cursor.fetchall()
if orphans:
    print(f"  [ERROR] HAY {len(orphans)} CPs en 'charging' SIN sesion activa:")
    for cp in orphans:
        print(f"    - {cp['cp_id']}")
else:
    print("  [OK] Todos los CPs en 'charging' tienen sesion activa")

conn.close()
print("\n" + "="*80 + "\n")

