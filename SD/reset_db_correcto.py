import sqlite3

conn = sqlite3.connect('ev_charging.db')

# Terminar sesiones activas
conn.execute("UPDATE charging_sesiones SET estado='completed' WHERE estado='active'")

# CPs deben iniciar en 'offline' (desconectados)
# Solo pasan a 'available' cuando se conectan
conn.execute("UPDATE charging_points SET estado='offline' WHERE estado IN ('charging', 'reserved', 'available')")

conn.commit()

# Verificar
cur = conn.execute("SELECT cp_id, estado FROM charging_points WHERE active=1 ORDER BY cp_id LIMIT 10")
print('Estado de CPs (deben estar OFFLINE hasta que se conecten):')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

conn.close()
print('\nBD reseteada correctamente')
print('Los CPs pasaran a AVAILABLE cuando Monitor/Engine se conecten')

