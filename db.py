import os
import psycopg2

# الاتصال بقاعدة بيانات Neon PostgreSQL
# يدعم SSL تلقائياً من خلال رابط الاتصال
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL غير موجود! يرجى إضافته في متغيرات البيئة")

conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cursor = conn.cursor()

# إنشاء جدول المستخدمين المفعلين مع عمود اللغة
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    order_id TEXT,
    language TEXT DEFAULT NULL,
    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# إضافة عمود اللغة إذا لم يكن موجوداً (للتحديث من النسخة القديمة)
try:
    cursor.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT NULL;")
    conn.commit()
    print("✅ تم إضافة عمود اللغة للجدول")
except psycopg2.errors.DuplicateColumn:
    conn.rollback()
    print("✅ عمود اللغة موجود بالفعل")
except Exception as e:
    conn.rollback()
    print(f"⚠️ خطأ في إضافة عمود اللغة: {e}")

# إنشاء جدول الطلبات
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_code TEXT UNIQUE,
    is_banned BOOLEAN DEFAULT FALSE
);
""")

# إنشاء سجل الاستخدام
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

conn.commit()

# التحقق من المستخدم
def is_user_verified(user_id):
    cursor.execute("SELECT 1 FROM users WHERE user_id = %s;", (user_id,))
    return cursor.fetchone() is not None

# إضافة مستخدم مفعل
def add_verified_user(user_id, order_id, username):
    cursor.execute("""
        INSERT INTO users (user_id, username, order_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO NOTHING;
    """, (user_id, username, order_id))
    conn.commit()

# إضافة مستخدم مفعل مع اللغة
def add_verified_user_with_language(user_id, order_id, username, language=None):
    cursor.execute("""
        INSERT INTO users (user_id, username, order_id, language)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET 
            username = EXCLUDED.username,
            order_id = EXCLUDED.order_id,
            language = EXCLUDED.language;
    """, (user_id, username, order_id, language))
    conn.commit()

# حفظ لغة المستخدم
def save_user_language(user_id, language):
    cursor.execute("""
        UPDATE users SET language = %s WHERE user_id = %s;
    """, (language, user_id))
    conn.commit()

# استرجاع لغة المستخدم
def get_user_language(user_id):
    cursor.execute("SELECT language FROM users WHERE user_id = %s;", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

# التحقق من صلاحية رقم الطلب
def is_allowed_order(order_code):
    cursor.execute("SELECT 1 FROM orders WHERE order_code = %s AND is_banned = FALSE;", (order_code.lower(),))
    return cursor.fetchone() is not None

# التحقق إذا رقم الطلب محظور
def is_banned_order(order_code):
    cursor.execute("SELECT 1 FROM orders WHERE order_code = %s AND is_banned = TRUE;", (order_code.lower(),))
    return cursor.fetchone() is not None

# تسجيل سجل استخدام
def log_usage(order_id, user_id, username, account):
    cursor.execute("""
        INSERT INTO usage_log (order_id, user_id, username, account)
        VALUES (%s, %s, %s, %s);
    """, (order_id, user_id, username, account))
    conn.commit()

# ✅ جلب رقم الطلب المرتبط بالمستخدم
def get_order_code_for_user(user_id):
    cursor.execute("SELECT order_id FROM users WHERE user_id = %s;", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else None