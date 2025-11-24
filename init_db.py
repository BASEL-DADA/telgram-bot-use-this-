import psycopg2
import os
import urllib.parse as urlparse

url = urlparse.urlparse(os.environ['DATABASE_URL'])
conn = psycopg2.connect(
    dbname=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS usages (
    id SERIAL PRIMARY KEY,
    order_id TEXT,
    user_id BIGINT,
    username TEXT,
    account TEXT,
    time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

conn.commit()
cursor.close()
conn.close()

print("✅ جدول usages تم إنشاؤه أو كان موجود مسبقًا.")
