import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / 'ev_charging.db'

MAPPINGS = {
    'unavailable': 'offline',
    'error': 'fault',
    'maintenance': 'out_of_service',
    'out_of_order': 'out_of_service',
}

def migrate():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    total = 0
    for old, new in MAPPINGS.items():
        cur.execute("""
            UPDATE charging_points
            SET status = ?
            WHERE LOWER(status) = ?
        """, (new, old))
        total += cur.rowcount

    conn.commit()

    # Show summary
    cur.execute("SELECT cp_id, status FROM charging_points ORDER BY cp_id")
    rows = cur.fetchall()
    conn.close()

    print(f"✅ Migración completada. Registros actualizados: {total}")
    for cp_id, status in rows:
        print(f" - {cp_id}: {status}")

if __name__ == '__main__':
    migrate()
