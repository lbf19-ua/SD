import database as db

print("\n" + "="*60)
print("  ESTADO DE LA BASE DE DATOS")
print("="*60)

# Ver CPs
cps = db.get_all_charging_points()
print(f"\nPuntos de Carga: {len(cps)}")
for cp in cps:
    print(f"  {cp['cp_id']}: {cp['estado']}")

# Ver sesiones activas
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) as count FROM charging_sesiones WHERE estado = 'active'")
active_sessions = cursor.fetchone()['count']
conn.close()

print(f"\nSesiones Activas: {active_sessions}")

# Ver usuarios
users = db.get_all_users()
print(f"\nUsuarios: {len(users)}")
for user in users[:5]:  # Mostrar solo primeros 5
    print(f"  {user['nombre']}: €{user['balance']:.2f}")

print("\n" + "="*60)

