import sqlite3

conn = sqlite3.connect('ev_charging.db')

# Terminar sesiones activas
conn.execute("UPDATE charging_sesiones SET estado='completed' WHERE estado='active'")

# CPs deben estar en 'offline' 
conn.execute("UPDATE charging_points SET estado='offline'")

conn.commit()

# Verificar
cur = conn.execute("SELECT cp_id, estado FROM charging_points WHERE active=1 ORDER BY cp_id LIMIT 5")
print('Estado de CPs (offline hasta que se conecten):')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

# Verificar sesiones
cur = conn.execute("SELECT COUNT(*) FROM charging_sesiones WHERE estado='active'")
print(f'\nSesiones activas: {cur.fetchone()[0]}')

conn.close()
print('\n✅ BD limpia - Lista para pruebas')

