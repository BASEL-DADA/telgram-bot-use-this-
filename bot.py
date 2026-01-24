from telethon import TelegramClient, events
from telethon.sessions import StringSession
import time
import asyncio
import os
from datetime import datetime
from db import (
    is_user_verified, add_verified_user, is_allowed_order, is_banned_order, 
    log_usage, conn, cursor, get_order_code_for_user
)

# ==================== الإعدادات ====================
api_id = int(os.environ.get("API_ID"))
api_hash = os.environ.get("API_HASH")
session_string = os.environ.get("SESSION_STRING")
bot_token = os.environ.get("BOT_TOKEN")

# معرفات الأدمن (يمكن إضافة أكثر من واحد)
ADMIN_IDS = set()
ADMIN_USERNAMES = {'ikonnstem'}  # يوزرنيم الأدمن

if not session_string:
    raise ValueError("❌ SESSION_STRING غير موجود!")

if not bot_token:
    raise ValueError("❌ BOT_TOKEN غير موجود!")

# ==================== العملاء ====================
# عميل Userbot للتواصل مع PoweredSteamBot
userbot = TelegramClient(StringSession(session_string), api_id, api_hash)

# عميل البوت للتواصل مع المستخدمين والأدمن
from telethon import TelegramClient as BotClient
bot = TelegramClient('bot', api_id, api_hash)

steam_bot_username = 'PoweredSteamBot'
bot_username = 'ORDERSIKON_bot'  # يوزرنيم البوت الجديد

waiting_requests = {}
active_request = None
welcomed_users = set()
auto_replied_users = set()  # لتجنب الرد المتكرر

# ==================== الرسائل ====================
messages = {
    'welcome': "👋 أهلاً بك في بوت *IKON STORE*!\n\n🔹 **طريقة الاستخدام:**\n- قم بتسجيل الدخول بالحساب على منصة ستيم.\n- مباشرة بعد تسجيل الدخول، أرسل **اسم الحساب** للبوت هنا.\n- انتظر قليلًا، وسيصلك رمز التحقق خلال دقائق.\n\n⚠️ **ملاحظة:** يمنع مشاركة الحسابات، وأي مشاركة ستؤدي إلى **سحب الحساب نهائيًا**.",
    'wait_5_minutes': "🚫 الرجاء الانتظار 3 دقائق قبل إرسال حساب آخر.",
    'someone_using': "🚫 شخص آخر يستخدم البوت حالياً. الرجاء الانتظار 3 دقائق ثم المحاولة مجددًا.",
    'checking_account': "⏳ جاري التحقق من الحساب... انتظر قليلاً.",
    'login_message': "📩 الرجاء تسجيل دخول على الحساب عبر منصة ستيم\nوسيتم إرسال رمز التحقق إليك خلال 15 ثانية إلى 3 دقائق.\n\nيوم سعيد 🫶",
    'timeout_message': "⏳ تأخر وصول الرمز؟ تأكد أنك سجلت بالطريقة الصحيحة.",
    'order_banned': "🚫 هذا رقم الطلب محظور.",
    'order_activated': "✅ تم تفعيل رقم الطلب. يمكنك الآن استخدام البوت.",
    'send_order_first': "🔑 الرجاء إرسال رقم الطلب أولاً.",
    'account_banned': "🚫 تم حظر حسابك من استخدام البوت. تواصل مع الإدارة.",
    'invalid_account': "❌ الرجاء إرسال اسم حساب صحيح (بالأحرف الإنجليزية فقط)"
}

# ==================== فحص الأدمن ====================
def is_admin(user_id, username=None):
    if user_id in ADMIN_IDS:
        return True
    if username and username.lower() in [u.lower() for u in ADMIN_USERNAMES]:
        ADMIN_IDS.add(user_id)  # حفظ الـ ID للمرات القادمة
        return True
    return False

# ==================== أوامر الأدمن ====================
admin_help = """
🔐 **أوامر لوحة التحكم:**

📋 **إدارة الطلبات:**
/orders - عرض جميع الطلبات
/add رقم1 رقم2 - إضافة طلب (أو أكثر)
/ban رقم1 رقم2 - حظر طلب (أو أكثر)
/unban رقم1 رقم2 - إلغاء حظر
/del رقم1 رقم2 - حذف طلب (أو أكثر)

👥 **إدارة المستخدمين:**
/users - عرض المستخدمين النشطين
/kick user_id - طرد مستخدم

📊 **الإحصائيات:**
/stats - إحصائيات سريعة
/logs - آخر 10 عمليات

ℹ️ /help - عرض هذه الرسالة

💡 **أمثلة:**
`/add 12345 67890 abc123`
`/ban 12345`
"""

# ==================== إدخال الطلبات الافتراضية ====================
def auto_insert_orders():
    allowed_orders = [
        "ORD123", "ORD345", "ORD457", "ORD567", "ORD678", "ORD789",
        "25326725", "6782345", "5535642", "6493405", "17593648", "2313123", 
        "233214", "3453028753", "36537234", "3535432", "63952704", "436436", 
        "47537464", "44455654", "45346457427", "456453753", "4575647", 
        "46464564", "4745457", "4745649108", "4774457", "53426157", "5347654", 
        "5390265257", "6345634", "63952704", "642747", "645753858", "678234", 
        "7789", "78439458", "7893125", "804362911", "867", "8781", "88779", 
        "890123", "8912", "4258329",
        # أرقام جديدة
        "4256723", "53463463", "zaid3424334"
    ]
    for order in allowed_orders:
        cursor.execute("""
            INSERT INTO orders (order_code, is_banned)
            VALUES (%s, FALSE)
            ON CONFLICT (order_code) DO NOTHING;
        """, (order.lower(),))
    conn.commit()
    print("✅ الطلبات المسموحة أُضيفت تلقائيًا.")

# ==================== معالجة رسائل البوت ====================
@bot.on(events.NewMessage)
async def handle_bot_message(event):
    if not event.is_private:
        return
    
    global active_request
    sender = await event.get_sender()
    message = event.raw_text.strip()
    user_id = sender.id
    username = sender.username
    
    # ==================== تجاهل الأوامر للمستخدمين العاديين ====================
    if message.startswith('/') and not is_admin(user_id, username):
        # المستخدم العادي أرسل أمر - نتجاهله
        return
    
    # ==================== أوامر الأدمن ====================
    if is_admin(user_id, username):
        
        # أي أمر يبدأ بـ / يتم معالجته هنا
        if message.startswith('/'):
            
            # مساعدة
            if message == '/start' or message == '/help':
                await event.reply(admin_help)
                return
            
            # عرض الطلبات
            if message == '/orders':
                cursor.execute("SELECT order_code, is_banned FROM orders ORDER BY order_code;")
                orders = cursor.fetchall()
                if not orders:
                    await event.reply("📭 لا توجد طلبات.")
                    return
                
                text = "📋 **قائمة الطلبات:**\n\n"
                for code, banned in orders[:50]:
                    status = "🚫" if banned else "✅"
                    text += f"{status} `{code}`\n"
                
                if len(orders) > 50:
                    text += f"\n... و {len(orders) - 50} طلب آخر"
                
                await event.reply(text)
                return
            
            # إضافة طلب (أو أكثر)
            if message.startswith('/add ') or message.startswith('/addorder '):
                parts = message.split(' ', 1)
                if len(parts) < 2 or not parts[1].strip():
                    await event.reply("❌ **الاستخدام:**\n`/add رقم1 رقم2 رقم3`\n\nمثال:\n`/add 12345 67890 abcde`")
                    return
                
                codes = parts[1].strip().split()
                added = []
                for code in codes:
                    code = code.lower().strip()
                    if code:
                        cursor.execute("""
                            INSERT INTO orders (order_code, is_banned)
                            VALUES (%s, FALSE)
                            ON CONFLICT (order_code) DO UPDATE SET is_banned = FALSE;
                        """, (code,))
                        added.append(code)
                conn.commit()
                await event.reply(f"✅ تم إضافة {len(added)} طلب:\n`{', '.join(added)}`")
                return
            
            # حظر طلب (أو أكثر)
            if message.startswith('/ban ') or message.startswith('/banorder '):
                parts = message.split(' ', 1)
                if len(parts) < 2 or not parts[1].strip():
                    await event.reply("❌ **الاستخدام:**\n`/ban رقم1 رقم2`")
                    return
                
                codes = parts[1].strip().split()
                for code in codes:
                    cursor.execute("UPDATE orders SET is_banned = TRUE WHERE order_code = %s;", (code.lower(),))
                conn.commit()
                await event.reply(f"🚫 تم حظر: `{', '.join(codes)}`")
                return
            
            # إلغاء حظر
            if message.startswith('/unban ') or message.startswith('/unbanorder '):
                parts = message.split(' ', 1)
                if len(parts) < 2 or not parts[1].strip():
                    await event.reply("❌ **الاستخدام:**\n`/unban رقم1 رقم2`")
                    return
                
                codes = parts[1].strip().split()
                for code in codes:
                    cursor.execute("UPDATE orders SET is_banned = FALSE WHERE order_code = %s;", (code.lower(),))
                conn.commit()
                await event.reply(f"✅ تم إلغاء حظر: `{', '.join(codes)}`")
                return
            
            # حذف طلب
            if message.startswith('/del ') or message.startswith('/deleteorder '):
                parts = message.split(' ', 1)
                if len(parts) < 2 or not parts[1].strip():
                    await event.reply("❌ **الاستخدام:**\n`/del رقم1 رقم2`")
                    return
                
                codes = parts[1].strip().split()
                for code in codes:
                    cursor.execute("DELETE FROM orders WHERE order_code = %s;", (code.lower(),))
                conn.commit()
                await event.reply(f"🗑️ تم حذف: `{', '.join(codes)}`")
                return
            
            # عرض المستخدمين
            if message == '/users':
                cursor.execute("""
                    SELECT user_id, username, order_id, verified_at 
                    FROM users ORDER BY verified_at DESC LIMIT 20;
                """)
                users = cursor.fetchall()
                if not users:
                    await event.reply("📭 لا يوجد مستخدمين نشطين.")
                    return
                
                text = "👥 **المستخدمين النشطين:**\n\n"
                for uid, uname, order, date in users:
                    text += f"• {uname or 'مجهول'} | `{order}` | {date.strftime('%Y-%m-%d')}\n"
                
                await event.reply(text)
                return
            
            # طرد مستخدم
            if message.startswith('/kick ') or message.startswith('/kickuser '):
                parts = message.split(' ', 1)
                if len(parts) < 2 or not parts[1].strip():
                    await event.reply("❌ **الاستخدام:**\n`/kick user_id`")
                    return
                try:
                    uid = int(parts[1].strip())
                    cursor.execute("DELETE FROM users WHERE user_id = %s;", (uid,))
                    conn.commit()
                    await event.reply(f"✅ تم طرد المستخدم: `{uid}`")
                except:
                    await event.reply("❌ الرجاء إدخال ID صحيح")
                return
            
            # الإحصائيات
            if message == '/stats':
                cursor.execute("SELECT COUNT(*) FROM orders WHERE is_banned = FALSE;")
                allowed = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM orders WHERE is_banned = TRUE;")
                banned = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM users;")
                users_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM usage_log;")
                logs_count = cursor.fetchone()[0]
                
                text = f"""📊 **إحصائيات IKON STORE:**

✅ طلبات مفعلة: {allowed}
🚫 طلبات محظورة: {banned}
👥 مستخدمين نشطين: {users_count}
📝 إجمالي العمليات: {logs_count}
"""
                await event.reply(text)
                return
            
            # السجلات
            if message == '/logs':
                cursor.execute("""
                    SELECT username, account, timestamp 
                    FROM usage_log ORDER BY timestamp DESC LIMIT 10;
                """)
                logs = cursor.fetchall()
                if not logs:
                    await event.reply("📭 لا توجد سجلات.")
                    return
                
                text = "📝 **آخر 10 عمليات:**\n\n"
                for uname, account, date in logs:
                    text += f"• {uname} → `{account}` | {date.strftime('%H:%M %d/%m')}\n"
                
                await event.reply(text)
                return
            
            # أمر غير معروف
            await event.reply(f"❓ أمر غير معروف: `{message}`\n\nأرسل /help لعرض الأوامر المتاحة.")
            return
    
    # ==================== منطق المستخدم العادي ====================
    
    # أمر الخروج
    if message.lower() == "exit":
        cursor.execute("DELETE FROM users WHERE user_id = %s;", (user_id,))
        conn.commit()
        if user_id in welcomed_users:
            welcomed_users.remove(user_id)
        if user_id in waiting_requests:
            del waiting_requests[user_id]
        await event.reply("🚪 تم تسجيل خروجك بنجاح. أرسل رقم الطلب لإعادة التفعيل.")
        return
    
    # التحقق من التفعيل
    if not is_user_verified(user_id):
        if is_banned_order(message):
            await event.reply(messages['order_banned'])
            return
        elif is_allowed_order(message):
            display_name = sender.first_name or sender.username or "مستخدم مجهول"
            add_verified_user(user_id, message, display_name)
            await event.reply(messages['order_activated'])
            if user_id not in welcomed_users:
                welcomed_users.add(user_id)
                await event.reply(messages['welcome'])
            return
        else:
            await event.reply(messages['send_order_first'])
            return
    
    # فحص إذا كان المستخدم المفعل محظور
    user_order_code = get_order_code_for_user(user_id)
    if user_order_code and is_banned_order(user_order_code):
        await event.reply(messages['account_banned'])
        return
    
    if " " in message:
        return
    
    # التحقق من الأحرف العربية
    if any('\u0600' <= char <= '\u06FF' for char in message):
        await event.reply(messages['invalid_account'])
        return
    
    current_time = time.time()
    if user_id in waiting_requests:
        if current_time - waiting_requests[user_id]['time'] < 180:
            await event.reply(messages['wait_5_minutes'])
            return
    
    if active_request:
        await event.reply(messages['someone_using'])
        return
    
    print(f"📅 رسالة من {user_id}: {message}")
    
    # تسجيل الاستخدام
    display_name = sender.first_name or sender.username or "مستخدم مجهول"
    log_usage(
        order_id=user_order_code or "غير معروف",
        user_id=user_id,
        username=display_name,
        account=message
    )
    
    # إرسال للـ Steam Bot عبر Userbot
    steam_bot = await userbot.get_entity(steam_bot_username)
    await userbot.send_message(steam_bot, message)
    
    waiting_requests[user_id] = {
        'account': message,
        'time': current_time
    }
    active_request = user_id
    
    async def check_timeout():
        await asyncio.sleep(180)
        if user_id in waiting_requests:
            print(f"⏳ انتهى وقت الانتظار للمستخدم {user_id}")
            await bot.send_message(user_id, messages['timeout_message'])
            del waiting_requests[user_id]
            global active_request
            active_request = None
    
    asyncio.create_task(check_timeout())
    await event.reply(messages['checking_account'])

# ==================== رد تلقائي على حسابك الشخصي ====================
@userbot.on(events.NewMessage(incoming=True))
async def auto_reply_personal(event):
    """رد تلقائي على أي شخص يراسل حسابك الشخصي"""
    if not event.is_private:
        return
    
    sender = await event.get_sender()
    
    # تجاهل البوتات
    if sender.bot:
        return
    
    # تجاهل @PoweredSteamBot
    if sender.username and sender.username.lower() == steam_bot_username.lower():
        return
    
    # تجاهل نفسك
    if event.out:
        return
    
    user_id = sender.id
    
    # رد مرة واحدة فقط لكل مستخدم (كل 24 ساعة)
    if user_id in auto_replied_users:
        return
    
    auto_replied_users.add(user_id)
    
    # الرسالة التلقائية
    auto_message = f"""👋 أهلاً بك!

للحصول على رموز التحقق وخدمات **IKON STORE**، يرجى التواصل مع البوت الرسمي:

🤖 @{bot_username}

شكراً لتفهمك! 🙏"""
    
    await event.reply(auto_message)
    print(f"📤 رد تلقائي على {sender.first_name or sender.username} ({user_id})")

# ==================== معالجة ردود Steam Bot ====================
@userbot.on(events.NewMessage(from_users=steam_bot_username))
async def handle_steam_reply(event):
    global active_request
    message = event.raw_text.strip()
    
    print(f"📨 رسالة من Steam Bot: {message}")
    
    # ==================== حساب معلق ====================
    if "معلق" in message:
        print(f"🔴 رد معلق: {message}")
        # استبدال جميع الأشكال المحتملة
        fixed_message = message.replace("@ skytvx", "@ikon.storee")
        fixed_message = fixed_message.replace("@skytvx", "@ikon.storee")
        for user_id, data in list(waiting_requests.items()):
            await bot.send_message(user_id, f"🚫 {fixed_message}")
            del waiting_requests[user_id]
        active_request = None
        return
    
    # ==================== تجري عملية دخول (الحساب مشغول) ====================
    elif "تجرى عملية الدخول" in message or "حاليا تجرى" in message:
        print(f"🔵 الحساب مشغول: {message}")
        for user_id, data in list(waiting_requests.items()):
            await bot.send_message(user_id, f"⚠️ {message}")
            del waiting_requests[user_id]
        active_request = None
        # نغلق الطلب لأن الحساب مشغول
        return
    
    # ==================== رمز التحقق ====================
    elif "رمز تحقق" in message or "رمز التحقق" in message:
        print(f"📩 رمز تحقق: {message}")
        
        # إذا لا يوجد أحد ينتظر
        if not waiting_requests:
            print("⚠️ لا يوجد أحد ينتظر رمز")
            return
        
        # محاولة استخراج اسم الحساب
        account_found = False
        try:
            # طريقة 1: "رمز تحقق لحساب X, هو Y"
            if "رمز تحقق لحساب" in message:
                account_part = message.split("رمز تحقق لحساب")[1]
                if "," in account_part:
                    account_name = account_part.split(",")[0].strip().lower()
                elif "هو" in account_part:
                    account_name = account_part.split("هو")[0].strip().lower()
                else:
                    account_name = account_part.split()[0].strip().lower()
                
                for user_id, data in list(waiting_requests.items()):
                    if data['account'].lower().strip() == account_name:
                        await bot.send_message(user_id, f"✅ {message}")
                        print(f"📨 أرسلنا الكود للمستخدم {user_id}")
                        del waiting_requests[user_id]
                        active_request = None
                        account_found = True
                        break
        except Exception as e:
            print(f"❌ خطأ في تحليل اسم الحساب: {e}")
        
        # طريقة 2: إذا لم نجد الحساب، نرسل لأول شخص ينتظر
        if not account_found and waiting_requests:
            user_id = list(waiting_requests.keys())[0]
            await bot.send_message(user_id, f"✅ {message}")
            print(f"📨 أرسلنا الكود للمستخدم الأول {user_id}")
            del waiting_requests[user_id]
            active_request = None
        
        return
    
    # ==================== حساب غير موجود ====================
    elif "غير موجود" in message or "not found" in message.lower() or "خطأ" in message:
        print(f"🔴 حساب غير موجود: {message}")
        for user_id, data in list(waiting_requests.items()):
            await bot.send_message(user_id, f"❌ {message}")
            del waiting_requests[user_id]
        active_request = None
        return
    
    # ==================== رسالة أخرى غير معروفة ====================
    else:
        print(f"📄 رسالة أخرى: {message}")
        # إذا الرسالة تحتوي على أرقام (ربما رمز تحقق بصيغة مختلفة)
        import re
        codes = re.findall(r'\b[A-Z0-9]{4,8}\b', message)
        if codes and waiting_requests:
            # ربما هذا رمز تحقق
            user_id = list(waiting_requests.keys())[0]
            await bot.send_message(user_id, f"📩 {message}")
            print(f"📨 أرسلنا رسالة محتملة للمستخدم {user_id}")
            del waiting_requests[user_id]
            active_request = None

# ==================== التشغيل ====================
async def main():
    auto_insert_orders()
    
    # تشغيل العميلين
    await userbot.start()
    await bot.start(bot_token=bot_token)
    
    print("🤖 IKON STORE Bot شغال...")
    print("✅ Userbot متصل")
    print("✅ Bot متصل")
    
    # تشغيل كلاهما معاً
    await asyncio.gather(
        userbot.run_until_disconnected(),
        bot.run_until_disconnected()
    )

if __name__ == "__main__":
    asyncio.run(main())
