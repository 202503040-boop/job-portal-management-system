import psycopg2
from db_config import DB_SETTINGS

conn = psycopg2.connect(**DB_SETTINGS)
cur = conn.cursor()
cur.execute("SELECT version();")
print("Connected successfully!")
print("PostgreSQL version:", cur.fetchone()[0])
cur.close()
conn.close()