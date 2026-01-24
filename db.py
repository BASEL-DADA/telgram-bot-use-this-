import os
import psycopg2
from psycopg2 import OperationalError, InterfaceError

# الاتصال بقاعدة بيانات Neon PostgreSQL
# يدعم SSL تلقائياً من خلال رابط الاتصال
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL غير موجود! يرجى إضافته في متغيرات البيئة")

# متغير الاتصال العام
conn = None

def get_connection():
    """الحصول على اتصال قاعدة البيانات مع إعادة الاتصال التلقائي"""
    global conn
    try:
        if conn is None or conn.closed:
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            print("✅ تم إنشاء اتصال جديد بقاعدة البيانات")
        else:
            # اختبار الاتصال
            try:
                with conn.cursor() as test_cursor:
                    test_cursor.execute("SELECT 1")
            except (OperationalError, InterfaceError):
                conn = psycopg2.connect(DATABASE_URL, sslmode='require')
                print("🔄 تم إعادة الاتصال بقاعدة البيانات")
    except Exception as e:
        print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
        raise
    return conn

def init_database():
    """تهيئة الجداول في قاعدة البيانات"""
    connection = get_connection()
    cursor = connection.cursor()
    
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
        connection.commit()
        print("✅ تم إضافة عمود اللغة للجدول")
    except psycopg2.errors.DuplicateColumn:
        connection.rollback()
        print("✅ عمود اللغة موجود بالفعل")
    except Exception as e:
        connection.rollback()
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

    connection.commit()
    cursor.close()
    print("✅ تم تهيئة قاعدة البيانات")

# تهيئة قاعدة البيانات عند استيراد الملف
init_database()

# التحقق من المستخدم
def is_user_verified(user_id):
    connection = get_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM users WHERE user_id = %s;", (user_id,))
        return cursor.fetchone() is not None

# إضافة مستخدم مفعل
def add_verified_user(user_id, order_id, username):
    connection = get_connection()
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO users (user_id, username, order_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING;
        """, (user_id, username, order_id))
        connection.commit()

# إضافة مستخدم مفعل مع اللغة
def add_verified_user_with_language(user_id, order_id, username, language=None):
    connection = get_connection()
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO users (user_id, username, order_id, language)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET 
                username = EXCLUDED.username,
                order_id = EXCLUDED.order_id,
                language = EXCLUDED.language;
        """, (user_id, username, order_id, language))
        connection.commit()

# حفظ لغة المستخدم
def save_user_language(user_id, language):
    connection = get_connection()
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE users SET language = %s WHERE user_id = %s;
        """, (language, user_id))
        connection.commit()

# استرجاع لغة المستخدم
def get_user_language(user_id):
    connection = get_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT language FROM users WHERE user_id = %s;", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None

# التحقق من صلاحية رقم الطلب
def is_allowed_order(order_code):
    connection = get_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM orders WHERE order_code = %s AND is_banned = FALSE;", (order_code.lower(),))
        return cursor.fetchone() is not None

# التحقق إذا رقم الطلب محظور
def is_banned_order(order_code):
    connection = get_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM orders WHERE order_code = %s AND is_banned = TRUE;", (order_code.lower(),))
        return cursor.fetchone() is not None

# تسجيل سجل استخدام
def log_usage(order_id, user_id, username, account):
    connection = get_connection()
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO usage_log (order_id, user_id, username, account)
            VALUES (%s, %s, %s, %s);
        """, (order_id, user_id, username, account))
        connection.commit()

# ✅ جلب رقم الطلب المرتبط بالمستخدم
def get_order_code_for_user(user_id):
    connection = get_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT order_id FROM users WHERE user_id = %s;", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else None