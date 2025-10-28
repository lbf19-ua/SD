#!/usr/bin/env python3
import sqlite3
from pathlib import Path

db_path = Path('ev_charging.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\n=== TABLAS EN LA BASE DE DATOS ===\n")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for table in tables:
    print(f"  - {table[0]}")
    
    # Ver esquema
    cursor.execute(f"PRAGMA table_info({table[0]})")
    columns = cursor.fetchall()
    for col in columns:
        print(f"      {col[1]} ({col[2]})")
    print()

conn.close()

