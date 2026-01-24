import os
import psycopg2

# الاتصال بقاعدة بيانات Neon PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL غير موجود! يرجى إضافته في متغيرات البيئة")

conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cursor = conn.cursor()

print("🔧 جاري إنشاء الجداول...")

# إنشاء جدول المستخدمين
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    order_id TEXT,
    language TEXT DEFAULT NULL,
    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")
print("✅ تم إنشاء جدول users")

# إنشاء جدول الطلبات
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_code TEXT UNIQUE,
    is_banned BOOLEAN DEFAULT FALSE
);
""")
print("✅ تم إنشاء جدول orders")

# إنشاء جدول السجل
cursor.execute("""
CREATE TABLE IF NOT EXISTS usage_log (
    id SERIAL PRIMARY KEY,
    order_id TEXT,
    user_id BIGINT,
    username TEXT,
    account TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")
print("✅ تم إنشاء جدول usage_log")

conn.commit()
conn.close()

print("🎉 تم إنشاء جميع الجداول بنجاح!")
