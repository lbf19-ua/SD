#!/usr/bin/env python3
import sqlite3
import os

db_path = './ev_central/ev_charging.db'

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verificar tablas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tablas encontradas:", tables)
    
    # Si hay tablas, mostrar su contenido
    if tables:
        for table in tables:
            table_name = table[0]
            print(f"\n--- Contenido de {table_name} ---")
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            if rows:
                for row in rows:
                    print(row)
            else:
                print("(tabla vacía)")
    
    conn.close()
else:
    print(f"La base de datos {db_path} no existe")