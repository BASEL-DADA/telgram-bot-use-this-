from flask import Flask, render_template, request, redirect, url_for, flash
import os
import psycopg2
import urllib.parse as urlparse
from telethon.sync import TelegramClient
import asyncio

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# إعداد الاتصال بقاعدة البيانات من Heroku DATABASE_URL
url = urlparse.urlparse(os.environ['DATABASE_URL'])
conn = psycopg2.connect(
    dbname=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)
cursor = conn.cursor()

# إعداد Telegram Client للإرسال
api_id = int(os.environ.get("API_ID"))
api_hash = os.environ.get("API_HASH")

# الصفحة الرئيسية - عرض الطلبات
@app.route('/')
def index():
    cursor.execute("SELECT order_code, is_banned FROM orders ORDER BY order_code ASC;")
    orders = cursor.fetchall()
    
    # حساب الإحصائيات
    total_orders = len(orders)
    allowed_orders = sum(1 for _, banned in orders if not banned)
    banned_orders = sum(1 for _, banned in orders if banned)
    
    return render_template('index.html', 
                         orders=orders,
                         total_orders=total_orders,
                         allowed_orders=allowed_orders,
                         banned_orders=banned_orders)

# صفحة المستخدمين النشطين
@app.route('/users')
def view_users():
    cursor.execute("""
        SELECT user_id, username, order_id, verified_at
        FROM users
        ORDER BY verified_at DESC;
    """)
    users = cursor.fetchall()
    total_users = len(users)
    return render_template('users.html', users=users, total_users=total_users)

# تسجيل خروج مستخدم
@app.route('/logout_user/<int:user_id>')
def logout_user(user_id):
    # جلب معلومات المستخدم قبل الحذف
    cursor.execute("SELECT username, order_id FROM users WHERE user_id = %s;", (user_id,))
    user_data = cursor.fetchone()
    
    if user_data:
        username = user_data[0]
        order_id = user_data[1]
        
        # حذف المستخدم من قاعدة البيانات
        cursor.execute("DELETE FROM users WHERE user_id = %s;", (user_id,))
        conn.commit()
        
        # إرسال رسالة تليجرام للمستخدم
        try:
            client = TelegramClient('admin_session', api_id, api_hash)
            client.connect()
            
            if not client.is_user_authorized():
                flash('⚠️ يجب تسجيل الدخول لحساب التليجرام أولاً', 'warning')
            else:
                message = f"🚪 تم تسجيل خروجك من البوت.\n\n📋 رقم طلبك كان: **{order_id}**\n\n💡 لإعادة التفعيل، أرسل رقم الطلب مرة أخرى."
                client.loop.run_until_complete(client.send_message(user_id, message))
                flash(f'✅ تم تسجيل خروج {username} وإرسال رسالة له برقم الطلب: {order_id}', 'success')
            
            client.disconnect()
        except Exception as e:
            flash(f'⚠️ تم حذف المستخدم لكن فشل إرسال الرسالة: {str(e)}', 'warning')
    else:
        flash('❌ المستخدم غير موجود', 'error')
    
    return redirect(url_for('view_users'))

# صفحة سجل الاستخدام
@app.route('/logs')
def view_logs():
    cursor.execute("""
        SELECT order_id, username, account, timestamp
        FROM usage_log
        ORDER BY timestamp DESC
        LIMIT 100;
    """)
    logs = cursor.fetchall()
    return render_template('logs.html', logs=logs)

# إضافة رقم طلب جديد
@app.route('/add', methods=['POST'])
def add_order():
    order_code = request.form['order_code'].strip().lower()
    is_banned = True if request.form.get('is_banned') == 'on' else False

    cursor.execute("""
        INSERT INTO orders (order_code, is_banned)
        VALUES (%s, %s)
        ON CONFLICT (order_code) DO UPDATE SET is_banned = EXCLUDED.is_banned;
    """, (order_code, is_banned))
    conn.commit()
    return redirect(url_for('index'))

# حذف رقم طلب
@app.route('/delete/<code>')
def delete_order(code):
    cursor.execute("DELETE FROM orders WHERE order_code = %s;", (code,))
    conn.commit()
    return redirect(url_for('index'))

# تغيير حالة الحظر
@app.route('/toggle_ban/<code>')
def toggle_ban(code):
    cursor.execute("UPDATE orders SET is_banned = NOT is_banned WHERE order_code = %s;", (code,))
    conn.commit()
    return redirect(url_for('index'))

# تشغيل التطبيق على Heroku
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))