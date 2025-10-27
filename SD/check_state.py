import database as db
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute('SELECT cp_id, estado FROM charging_points WHERE cp_id=?', ('CP_001',))
result = cursor.fetchall()
print([dict(row) for row in result])

