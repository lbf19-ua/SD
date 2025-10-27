import sqlite3
conn = sqlite3.connect('ev_charging.db')
conn.execute("UPDATE charging_sesiones SET estado='completed' WHERE estado='active'")
conn.execute("UPDATE charging_points SET estado='available'")
conn.commit()
cur = conn.execute("SELECT cp_id, estado FROM charging_points WHERE active=1 ORDER BY cp_id LIMIT 5")
print('CPs disponibles:')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')
conn.close()
print('\n BD reseteada - Lista para probar asignacion automatica')

