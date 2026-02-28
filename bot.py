from telethon import TelegramClient, events
from telethon.sessions import StringSession
import time
import asyncio
import os
import re
from datetime import datetime
from db import (
    is_user_verified, add_verified_user, is_allowed_order, is_banned_order, 
    log_usage, get_connection, get_order_code_for_user
)

# ==================== الإعدادات ====================
api_id = int(os.environ.get("API_ID"))
api_hash = os.environ.get("API_HASH")
session_string = os.environ.get("SESSION_STRING")
bot_token = os.environ.get("BOT_TOKEN")

# معرفات الأدمن (يمكن إضافة أكثر من واحد)
ADMIN_IDS = set()
ADMIN_USERNAMES = {'basel_iii'}  # يوزرنيم الأدمن

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

# البوت الجديد (7LE STORE)
steam_bot_username = 'hllestore_bot'
# البوت القديم (PoweredSteamBot) - للحسابات المحددة
powered_steam_bot_username = 'PoweredSteamBot'
bot_username = 'ORDERSIKON_bot'  # يوزرنيم البوت الجديد

# رقم الطلب الثابت للبوت الجديد (7LE STORE)
FIXED_ORDER_NUMBER = '208718912'

# قائمة الحسابات التي تذهب إلى PoweredSteamBot
POWERED_STEAM_ACCOUNTS = {
    'qapo2d', 'diteks', 'retlau', 'mrdarkness26', 'skytvstore0', 'skytvgames0',
    'chrismendoza', 'uzab54709', 'kcqum63847', 'ywfkn71206', 'rapcs71404',
    'cevjr69650', 'wsgln795693', 'mzxw6342', 'fwskfjmsk', 'fdssdaju',
    'gkhsj96522', 'jjuau71591', 'ppjfq021084', 'vgnpu15312', 'tyuqg35761',
    'ci0jy7uu2dc2', 'fhhxh50203', 'ky3np5vb7q', 'gblga428', 'nbfbe61423',
    'ogcoe40882', 'fowyw07349', 'qe9190211', 'oc6zw0vr9xc0', 'vl2hh3zi7iq0',
    '4745649108', 'oqtzv12285', 'sq251666', 'jgqa72431', 'ci0hy1uf3zl1',
    'cparm91075', '2b092449', 'smiwt62938', 'aleeshamahxbq', 'vhe99034',
    'wscfi02971', 'honeypayne36565', 'gyvfb49046', 'dasiisamoilov766',
    'ztmys93429', 'sgxunagc5212', 'ag7ay2050', 'bf0qmwlf0s', 'ohnyf579110',
    'nnfjg073', 'bm8gf5py8an0', 'cnini68869', 'xolzb825', 'quzzn64549',
    'tkm75854', 'fdjhv32611', 'tqbma351', 'qsaij049', 'lzbcp748', 'eisyt78173',
    'samu_2401', 'elninjo36', 'jessicadolittle8v', 'doggs2212', 'achilleee2',
    'qxen85607', 'yzvhr48817', 'azza_claydog', 'qbidw69605', 'njnzin2575',
    'no3ys6ct4ud0', 'binff93661', 'pr7ue2gn9hv3', 'nikolya_oss1233', 'lslbi05158',
    'obrqn26579', 'zcwn5836378', 'ecgxc961514', 'badotez', 'paulhendrikhammelmann',
    'hormonnisa2', 'unthc6ts', 'northcertpasscow1980', 'xbydk88881', 'zzisld9046',
    'harzke2', 'simonremol0t', 'dhgpr09228', 'dragon4404', 'bubblematend1972',
    'qrmdxtob6843', 'p7ao0hxls4', 'mattia3431', 'sundimemoli7g', 'lxakeisl',
    'alarmingbystand2', 'danwangbule', 'godofredo57', 'detroit_st',
    'amanda_reflect738086', 'vmjix46135', 'srwbi52693', 'pd67gxtl', 'witcher3_st',
    'xoool51874', 'xl2eb1bm1ks4',
    # حسابات جديدة
    'yf1qf5oh4xp0', 'cpcnc993712', 'qp6ef1dc6av3', 'ur8ts3zk4kf0', 'sf6mv9vq9gv8',
    'gc9um3qb1sh6', 'bb1hr4yz8gs8', 'vt1ot6nt3ro2', 'de8mg8qz0yo8', 'ax8az1rv1ga7',
    'tw5rm2tz3am3', 'ke6gc9yu6ij5', 'prmst44110', 'prtzt73337', 'prvnd57593',
    'qm5vq5yj2zc4', 'gk0lm5xr0nf1', 'mv8ue9ak9un4', 'lb2ef6wz4ml8'
}

waiting_requests = {}
active_request = None
welcomed_users = set()
auto_replied_users = set()  # لتجنب الرد المتكرر

# لتتبع أي بوت يستخدم لكل طلب
# الشكل: {user_id: 'powered' أو 'hlle'}
request_bot_type = {}

# قائمة للاحتفاظ بالطلبات الأخيرة حتى لو انتهى الـ timeout (للتعامل مع الردود المتأخرة)
# الشكل: {account_name: {'user_id': user_id, 'time': timestamp}}
recent_requests = {}

# وضع الصيانة
maintenance_mode = False

# المستخدمين المحظورين نهائياً (لا يمكنهم استخدام البوت أو التواصل)
BLOCKED_USERNAMES = {'hlesteam', 'skytvx'}

# ==================== دالة تنظيف الرسائل ====================
def clean_message(text):
    """تنظيف الرسائل من أي ذكر لحلّة ستور أو 7LE STORE"""
    # قائمة النصوص المراد حذفها
    remove_texts = [
        "-المتجر الأفضل حلّة ستور || 7LE STORE-",
        "المتجر الأفضل حلّة ستور || 7LE STORE",
        "حلّة ستور || 7LE STORE",
        "حلّة ستور",
        "حلة ستور",
        "7LE STORE",
        "7le store",
        "7LE",
    ]
    
    cleaned = text
    for remove_text in remove_texts:
        cleaned = cleaned.replace(remove_text, "")
    
    # تنظيف الأسطر الفارغة الزائدة
    lines = [line for line in cleaned.split('\n') if line.strip() and line.strip() != '-' and line.strip() != '||']
    cleaned = '\n'.join(lines)
    
    return cleaned.strip()

# ==================== الرسائل ====================
messages = {
    'welcome': "👋 أهلاً بك في بوت *IKON STORE*!\n\n🔹 **طريقة الاستخدام:**\n- قم بتسجيل الدخول بالحساب على منصة ستيم.\n- مباشرة بعد تسجيل الدخول، أرسل **اسم الحساب** للبوت هنا.\n- انتظر قليلًا، وسيصلك رمز التحقق خلال دقائق.\n\n⚠️ **ملاحظة:** يمنع مشاركة الحسابات، وأي مشاركة ستؤدي إلى **سحب الحساب نهائيًا**.",
    'wait_5_minutes': "🚫 الرجاء الانتظار 5 دقائق قبل إرسال حساب آخر.",
    'someone_using': "🚫 شخص آخر يستخدم البوت حالياً. الرجاء الانتظار 5 دقائق ثم المحاولة مجددًا.",
    'checking_account': "⏳ جاري التحقق من الحساب... انتظر قليلاً.",
    'login_message': "📩 الرجاء تسجيل دخول على الحساب عبر منصة ستيم\nوسيتم إرسال رمز التحقق إليك خلال 15 ثانية إلى 3 دقائق.\n\nيوم سعيد 🫶",
    'timeout_message': "⏳ تأخر وصول الرمز؟ تأكد أنك سجلت بالطريقة الصحيحة.",
    'order_banned': "🚫 هذا رقم الطلب محظور.",
    'order_activated': "✅ تم تفعيل رقم الطلب. يمكنك الآن استخدام البوت.",
    'send_order_first': "🔑 الرجاء إرسال رقم الطلب أولاً.",
    'account_banned': "🚫 تم حظر حسابك من استخدام البوت. تواصل مع الإدارة.",
    'invalid_account': "❌ الرجاء إرسال اسم حساب صحيح (بالأحرف الإنجليزية فقط)",
    'maintenance': "🔧 **البوت حالياً في وضع الصيانة**\n\nنعمل على تحسين الخدمة، يرجى المحاولة لاحقاً.\n\nشكراً لصبرك! 🙏"
}

# ==================== رسالة المساعدة للمستخدمين ====================
user_help = """
📖 **دليل استخدام البوت:**

🔹 **الأوامر المتاحة:**
• `exit` - تسجيل خروج وإدخال رقم طلب جديد
• `/help` - عرض هذه الرسالة
• `/info` - معلومات عن البوت

🔹 **طريقة الاستخدام:**
1️⃣ أرسل **رقم الطلب** للتفعيل
2️⃣ سجّل دخول على حسابك في Steam
3️⃣ أرسل **اسم الحساب** للبوت
4️⃣ انتظر رمز التحقق (يصل خلال دقائق)

🎬 **شرح بالفيديو:**
https://www.youtube.com/watch?v=FzFGnQ2asvQ

⚠️ **تنبيه:** يمنع مشاركة الحسابات!
"""

user_info = """
🎬 **شرح الاستخدام:**
https://www.youtube.com/watch?v=FzFGnQ2asvQ

📸 **للتواصل:** @ikon.storee (انستغرام)
"""

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
🔐 **أوامر لوحة التحكم (أدمن):**

⚙️ **الصيانة:**
/maintenance - تفعيل/إلغاء وضع الصيانة
/status - حالة البوت الحالية

📋 **إدارة الطلبات:**
/orders - عرض جميع الطلبات
/add رقم1 رقم2 - إضافة طلب (أو أكثر)
/ban رقم1 رقم2 - حظر طلب (أو أكثر)
/unban رقم1 رقم2 - إلغاء حظر
/del رقم1 رقم2 - حذف طلب (أو أكثر)

👥 **إدارة المستخدمين:**
/users - عرض المستخدمين النشطين
/kick user_id - طرد مستخدم

� **الرسائل:**
/broadcast الرسالة - إرسال للجميع
/msg رقم_الطلب الرسالة - إرسال لرقم طلب

📊 **الإحصائيات:**
/stats - إحصائيات سريعة
/logs - آخر 10 عمليات
/logs رقم_الطلب - آخر 20 عملية لرقم طلب
/userlogs اسم_المستخدم - آخر 30 عملية لمستخدم

🔧 **أدوات:**
/reset - إعادة تعيين البوت (إذا علق)

━━━━━━━━━━━━━━━━━━━━━━
👤 **أوامر المستخدمين:**
/info - معلومات عن البوت
exit - تسجيل خروج وإدخال رقم طلب جديد

ℹ️ /help - عرض هذه الرسالة

💡 **أمثلة:**
`/add 12345 67890 abc123`
`/ban 12345`
`/logs 12345`
`/userlogs basel_iii`
`/broadcast مرحبا بالجميع`
`/msg 12345 رسالة خاصة`
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
    connection = get_connection()
    with connection.cursor() as cursor:
        for order in allowed_orders:
            cursor.execute("""
                INSERT INTO orders (order_code, is_banned)
                VALUES (%s, FALSE)
                ON CONFLICT (order_code) DO NOTHING;
            """, (order.lower(),))
        connection.commit()
    print("✅ الطلبات المسموحة أُضيفت تلقائيًا.")

# ==================== معالجة رسائل البوت ====================
@bot.on(events.NewMessage(incoming=True))
async def handle_bot_message(event):
    # فقط الرسائل الخاصة الواردة
    if not event.is_private:
        return
    
    # تجاهل الرسائل المرسلة من البوت نفسه
    if event.out:
        return
    
    global active_request
    sender = await event.get_sender()
    
    # تجاهل البوتات
    if sender.bot:
        return
    
    message = event.raw_text.strip()
    user_id = sender.id
    username = sender.username
    
    # تجاهل المستخدمين المحظورين تماماً (بدون أي رد)
    if username and username.lower() in BLOCKED_USERNAMES:
        return
    
    # ==================== أوامر المستخدمين العاديين ====================
    if message.startswith('/') and not is_admin(user_id, username):
        # أوامر المساعدة للمستخدمين العاديين
        if message == '/help' or message == '/start':
            await event.reply(user_help)
            return
        elif message == '/info':
            await event.reply(user_info)
            return
        else:
            # أمر غير معروف للمستخدم العادي
            await event.reply("❓ أمر غير معروف. أرسل /help لعرض الأوامر المتاحة.")
            return
    
    # ==================== أوامر الأدمن ====================
    if is_admin(user_id, username):
        
        # أي أمر يبدأ بـ / يتم معالجته هنا
        if message.startswith('/'):
            
            # مساعدة
            if message == '/start' or message == '/help':
                await event.reply(admin_help)
                return
            
            # وضع الصيانة
            if message == '/maintenance':
                global maintenance_mode
                maintenance_mode = not maintenance_mode
                status = "🔴 مُفعّل" if maintenance_mode else "🟢 مُلغى"
                await event.reply(f"🔧 **وضع الصيانة:** {status}")
                return
            
            # حالة البوت
            if message == '/status':
                m_status = "🔴 وضع الصيانة مُفعّل" if maintenance_mode else "🟢 البوت يعمل بشكل طبيعي"
                active = f"👤 طلب نشط: {active_request}" if active_request else "✅ لا يوجد طلب نشط"
                waiting = f"⏳ طلبات منتظرة: {len(waiting_requests)}"
                recent = f"📋 طلبات أخيرة: {len(recent_requests)}"
                await event.reply(f"📊 **حالة البوت:**\n\n{m_status}\n{active}\n{waiting}\n{recent}")
                return
            
            # عرض الطلبات
            if message == '/orders':
                connection = get_connection()
                with connection.cursor() as cursor:
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
            if message.startswith('/add') or message.startswith('/addorder'):
                parts = message.split(' ', 1)
                if len(parts) < 2 or not parts[1].strip():
                    await event.reply("❌ **الاستخدام:**\n`/add رقم1 رقم2 رقم3`\n\nمثال:\n`/add 12345 67890 abcde`")
                    return
                
                codes = parts[1].strip().split()
                added = []
                connection = get_connection()
                with connection.cursor() as cursor:
                    for code in codes:
                        code = code.lower().strip()
                        if code:
                            cursor.execute("""
                                INSERT INTO orders (order_code, is_banned)
                                VALUES (%s, FALSE)
                                ON CONFLICT (order_code) DO UPDATE SET is_banned = FALSE;
                            """, (code,))
                            added.append(code)
                    connection.commit()
                await event.reply(f"✅ تم إضافة {len(added)} طلب:\n`{', '.join(added)}`")
                return
            
            # حظر طلب (أو أكثر)
            if message.startswith('/ban') or message.startswith('/banorder'):
                parts = message.split(' ', 1)
                if len(parts) < 2 or not parts[1].strip():
                    await event.reply("❌ **الاستخدام:**\n`/ban رقم1 رقم2`")
                    return
                
                codes = parts[1].strip().split()
                connection = get_connection()
                with connection.cursor() as cursor:
                    for code in codes:
                        cursor.execute("UPDATE orders SET is_banned = TRUE WHERE order_code = %s;", (code.lower(),))
                    connection.commit()
                await event.reply(f"🚫 تم حظر: `{', '.join(codes)}`")
                return
            
            # إلغاء حظر
            if message.startswith('/unban'):
                parts = message.split(' ', 1)
                if len(parts) < 2 or not parts[1].strip():
                    await event.reply("❌ **الاستخدام:**\n`/unban رقم1 رقم2`")
                    return
                
                codes = parts[1].strip().split()
                connection = get_connection()
                with connection.cursor() as cursor:
                    for code in codes:
                        cursor.execute("UPDATE orders SET is_banned = FALSE WHERE order_code = %s;", (code.lower(),))
                    connection.commit()
                await event.reply(f"✅ تم إلغاء حظر: `{', '.join(codes)}`")
                return
            
            # حذف طلب
            if message.startswith('/del'):
                parts = message.split(' ', 1)
                if len(parts) < 2 or not parts[1].strip():
                    await event.reply("❌ **الاستخدام:**\n`/del رقم1 رقم2`")
                    return
                
                codes = parts[1].strip().split()
                connection = get_connection()
                with connection.cursor() as cursor:
                    for code in codes:
                        cursor.execute("DELETE FROM orders WHERE order_code = %s;", (code.lower(),))
                    connection.commit()
                await event.reply(f"🗑️ تم حذف: `{', '.join(codes)}`")
                return
            
            # عرض المستخدمين
            if message == '/users':
                connection = get_connection()
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT user_id, username, order_id 
                        FROM users ORDER BY verified_at DESC LIMIT 20;
                    """)
                    users = cursor.fetchall()
                if not users:
                    await event.reply("📭 لا يوجد مستخدمين نشطين.")
                    return
                
                text = "👥 **المستخدمين النشطين:**\n\n"
                for uid, uname, order in users:
                    text += f"• {uname or 'مجهول'} | `{order}`\n"
                
                await event.reply(text)
                return
            
            # طرد مستخدم
            if message.startswith('/kick'):
                parts = message.split(' ', 1)
                if len(parts) < 2 or not parts[1].strip():
                    await event.reply("❌ **الاستخدام:**\n`/kick user_id`")
                    return
                try:
                    uid = int(parts[1].strip())
                    connection = get_connection()
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM users WHERE user_id = %s;", (uid,))
                        connection.commit()
                    await event.reply(f"✅ تم طرد المستخدم: `{uid}`")
                except:
                    await event.reply("❌ الرجاء إدخال ID صحيح")
                return
            
            # الإحصائيات
            if message == '/stats':
                connection = get_connection()
                with connection.cursor() as cursor:
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
            if message == '/logs' or message.startswith('/logs '):
                parts = message.split(' ', 1)
                connection = get_connection()
                
                if len(parts) > 1 and parts[1].strip():
                    # البحث برقم طلب معين
                    order_code = parts[1].strip().lower()
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT username, account, order_id 
                            FROM usage_log WHERE LOWER(order_id) = %s ORDER BY timestamp DESC LIMIT 20;
                        """, (order_code,))
                        logs = cursor.fetchall()
                    if not logs:
                        await event.reply(f"📭 لا توجد سجلات لرقم الطلب: `{order_code}`")
                        return
                    
                    text = f"📝 **آخر 20 عملية لرقم الطلب #{order_code}:**\n\n"
                    for uname, account, oid in logs:
                        text += f"• {uname} → `{account}`\n"
                else:
                    # عرض آخر 10 عمليات عامة
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT username, account, order_id 
                            FROM usage_log ORDER BY timestamp DESC LIMIT 10;
                        """)
                        logs = cursor.fetchall()
                    if not logs:
                        await event.reply("📭 لا توجد سجلات.")
                        return
                    
                    text = "📝 **آخر 10 عمليات:**\n\n"
                    for uname, account, order_code in logs:
                        text += f"• {uname} → `{account}` | #{order_code}\n"
                
                await event.reply(text)
                return
            
            # سجلات مستخدم معين باسم المستخدم (username)
            if message.startswith('/userlogs '):
                parts = message.split(' ', 1)
                if len(parts) < 2 or not parts[1].strip():
                    await event.reply("❌ **الاستخدام:**\n`/userlogs اسم_المستخدم`\n\nمثال:\n`/userlogs basel_iii`")
                    return
                
                target_username = parts[1].strip().lower().replace('@', '')
                connection = get_connection()
                
                with connection.cursor() as cursor:
                    # البحث باسم المستخدم
                    cursor.execute("""
                        SELECT account, order_id, timestamp 
                        FROM usage_log 
                        WHERE LOWER(username) = %s OR LOWER(username) = %s
                        ORDER BY timestamp DESC 
                        LIMIT 30;
                    """, (target_username, '@' + target_username))
                    logs = cursor.fetchall()
                
                if not logs:
                    await event.reply(f"📭 لا توجد سجلات للمستخدم: `@{target_username}`")
                    return
                
                text = f"📝 **آخر 30 عملية للمستخدم @{target_username}:**\n\n"
                for account, order_id, timestamp in logs:
                    time_str = timestamp.strftime('%Y-%m-%d %H:%M') if timestamp else ''
                    text += f"• `{account}` | #{order_id} | {time_str}\n"
                
                await event.reply(text)
                return
            
            # إعادة تعيين البوت (إذا علق)
            if message == '/reset':
                old_active = active_request
                old_waiting = len(waiting_requests)
                old_recent = len(recent_requests)
                
                active_request = None
                waiting_requests.clear()
                recent_requests.clear()
                request_bot_type.clear()
                
                await event.reply(f"🔄 **تم إعادة تعيين البوت:**\n\n• طلب نشط سابق: `{old_active}`\n• طلبات منتظرة محذوفة: {old_waiting}\n• طلبات أخيرة محذوفة: {old_recent}\n\n✅ البوت جاهز الآن")
                return
            
            # إرسال رسالة للجميع (broadcast)
            if message.startswith('/broadcast '):
                parts = message.split(' ', 1)
                if len(parts) < 2 or not parts[1].strip():
                    await event.reply("❌ **الاستخدام:**\n`/broadcast الرسالة`\n\nمثال:\n`/broadcast مرحباً بالجميع!`")
                    return
                
                msg_text = parts[1].strip()
                connection = get_connection()
                sent_count = 0
                failed_count = 0
                
                with connection.cursor() as cursor:
                    cursor.execute("SELECT user_id FROM users;")
                    all_users = cursor.fetchall()
                
                await event.reply(f"📤 جاري الإرسال لـ {len(all_users)} مستخدم...")
                
                for (uid,) in all_users:
                    try:
                        await bot.send_message(uid, f"📢 **رسالة من الإدارة:**\n\n{msg_text}")
                        sent_count += 1
                        await asyncio.sleep(0.1)  # تجنب الحظر من تيليجرام
                    except Exception as e:
                        print(f"❌ فشل إرسال لـ {uid}: {e}")
                        failed_count += 1
                
                await event.reply(f"✅ **تم الإرسال!**\n\n📤 نجح: {sent_count}\n❌ فشل: {failed_count}")
                return
            
            # إرسال رسالة للمستخدمين
            if message.startswith('/msg '):
                parts = message.split(' ', 2)
                if len(parts) < 3:
                    await event.reply("❌ **الاستخدام:**\n`/msg all الرسالة` - إرسال للجميع\n`/msg رقم_الطلب الرسالة` - إرسال لرقم طلب معين")
                    return
                
                target = parts[1].strip().lower()
                msg_text = parts[2].strip()
                
                if not msg_text:
                    await event.reply("❌ الرجاء كتابة نص الرسالة.")
                    return
                
                connection = get_connection()
                sent_count = 0
                failed_count = 0
                
                if target == 'all':
                    # إرسال للجميع
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT user_id FROM users;")
                        all_users = cursor.fetchall()
                    
                    for (uid,) in all_users:
                        try:
                            await bot.send_message(uid, f"📢 **رسالة من الإدارة:**\n\n{msg_text}")
                            sent_count += 1
                        except Exception as e:
                            print(f"❌ فشل إرسال لـ {uid}: {e}")
                            failed_count += 1
                    
                    await event.reply(f"✅ تم إرسال الرسالة للجميع\n📤 نجح: {sent_count}\n❌ فشل: {failed_count}")
                else:
                    # إرسال لرقم طلب معين
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT user_id FROM users WHERE LOWER(order_id) = %s;", (target,))
                        target_users = cursor.fetchall()
                    
                    if not target_users:
                        await event.reply(f"❌ لا يوجد مستخدمين لرقم الطلب: `{target}`")
                        return
                    
                    for (uid,) in target_users:
                        try:
                            await bot.send_message(uid, f"📢 **رسالة من الإدارة:**\n\n{msg_text}")
                            sent_count += 1
                        except Exception as e:
                            print(f"❌ فشل إرسال لـ {uid}: {e}")
                            failed_count += 1
                    
                    await event.reply(f"✅ تم إرسال الرسالة لرقم الطلب `{target}`\n📤 نجح: {sent_count}\n❌ فشل: {failed_count}")
                return
            
            # أمر /info للأدمن أيضاً
            if message == '/info':
                await event.reply(user_info)
                return
            
            # أمر غير معروف - السماح بالمرور لمنطق المستخدم العادي
            # (حتى يستطيع الأدمن استخدام البوت كمستخدم عادي)
            pass  # لا نرجع، نكمل لمنطق المستخدم
    
    # ==================== منطق المستخدم العادي ====================
    
    # فحص وضع الصيانة للمستخدمين العاديين
    if maintenance_mode:
        await event.reply(messages['maintenance'])
        return
    
    # أمر الخروج
    if message.lower() == "exit":
        connection = get_connection()
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE user_id = %s;", (user_id,))
            connection.commit()
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
    
    # التحقق من الأحرف العربية (اسم الحساب بالإنجليزي فقط)
    if any('\u0600' <= char <= '\u06FF' for char in message):
        await event.reply(messages['invalid_account'])
        return
    
    current_time = time.time()
    
    # ==================== آلية البوت الجديد (7LE STORE) ====================
    # المستخدم يرسل اسم الحساب فقط
    # البوت يطلب رقم الطلب → نرسل الرقم الثابت تلقائياً
    # البوت يطلب اسم الحساب → نرسل اسم الحساب تلقائياً
    
    # فحص قيد الانتظار 5 دقائق (للجميع بما فيهم الأدمن)
    if user_id in waiting_requests:
        if current_time - waiting_requests[user_id]['time'] < 300:  # 5 دقائق
            await event.reply(messages['wait_5_minutes'])
            return
    
    if active_request:
        await event.reply(messages['someone_using'])
        return
    
    print(f"📅 اسم حساب من {user_id}: {message}")
    
    # تسجيل الاستخدام
    display_name = sender.first_name or sender.username or "مستخدم مجهول"
    log_usage(
        order_id=user_order_code or "غير معروف",
        user_id=user_id,
        username=display_name,
        account=message
    )
    
    # تحديد أي بوت نستخدم بناءً على اسم الحساب
    if message.lower() in POWERED_STEAM_ACCOUNTS:
        # الحساب من قائمة PoweredSteamBot
        print(f"📤 إرسال إلى PoweredSteamBot: {message}")
        target_bot = await userbot.get_entity(powered_steam_bot_username)
        request_bot_type[user_id] = 'powered'
    else:
        # الحساب عادي - يذهب لـ hllestore_bot
        print(f"📤 إرسال إلى hllestore_bot: {message}")
        target_bot = await userbot.get_entity(steam_bot_username)
        request_bot_type[user_id] = 'hlle'
    
    await userbot.send_message(target_bot, message)
    
    waiting_requests[user_id] = {
        'account': message,
        'time': current_time
    }
    active_request = user_id
    
    # حفظ الطلب في recent_requests للتعامل مع الردود المتأخرة (لمدة 10 دقائق)
    recent_requests[message.lower()] = {
        'user_id': user_id,
        'time': current_time
    }
    
    await event.reply(messages['checking_account'])
    
    async def check_timeout():
        await asyncio.sleep(300)  # 5 دقائق بدلاً من 3
        if user_id in waiting_requests:
            print(f"⏳ انتهى وقت الانتظار للمستخدم {user_id}")
            await bot.send_message(user_id, messages['timeout_message'])
            del waiting_requests[user_id]
            global active_request
            active_request = None
            # لا نحذف من recent_requests - نبقيه لاحتمال وصول رد متأخر
    
    # تنظيف الطلبات القديمة من recent_requests (أكثر من 10 دقائق)
    async def cleanup_recent():
        await asyncio.sleep(600)  # 10 دقائق
        if message.lower() in recent_requests:
            del recent_requests[message.lower()]
            print(f"🧹 تم تنظيف الطلب القديم: {message}")
    
    asyncio.create_task(check_timeout())
    asyncio.create_task(cleanup_recent())

# ==================== تجاهل الرسائل من المحظورين على حسابك الشخصي ====================
@userbot.on(events.NewMessage(incoming=True))
async def ignore_blocked_users(event):
    sender = await event.get_sender()
    if sender and sender.username and sender.username.lower() in BLOCKED_USERNAMES:
        # تجاهل تام - لا رد
        return
    # باقي الرسائل تُعالج بواسطة handlers أخرى

# ==================== معالجة ردود Steam Bot (7LE STORE) ====================
@userbot.on(events.NewMessage(from_users=steam_bot_username))
async def handle_steam_reply(event):
    global active_request
    message = event.raw_text.strip()
    
    print(f"📨 رسالة من 7LE Bot: {message}")
    
    # ==================== طلب رقم الطلب أولاً ====================
    # "يرجى إدخال رقم الطلب 🆔 صالح للمتابعة"
    if "يرجى إدخال رقم الطلب" in message or "صالح للمتابعة" in message:
        print(f"📝 البوت طلب رقم الطلب - نرسل الرقم الثابت تلقائياً: {FIXED_ORDER_NUMBER}")
        # نرسل رقم الطلب الثابت تلقائياً
        steam_bot = await userbot.get_entity(steam_bot_username)
        await userbot.send_message(steam_bot, FIXED_ORDER_NUMBER)
        return
    
    # ==================== رقم الطلب صحيح - طلب اسم الحساب ====================
    # "اختيار موفق عزيزي العميل، الرجاء كتابة اسم حساب ستيم الذي ترغب بالدخول إليه"
    if "اختيار موفق" in message or "الرجاء كتابة اسم حساب ستيم" in message:
        print(f"✅ رقم الطلب صحيح - نرسل اسم الحساب تلقائياً")
        # نرسل اسم الحساب تلقائياً (المحفوظ في waiting_requests)
        steam_bot = await userbot.get_entity(steam_bot_username)
        for user_id, data in list(waiting_requests.items()):
            account_name = data.get('account', '')
            if account_name:
                print(f"📤 إرسال اسم الحساب تلقائياً: {account_name}")
                await userbot.send_message(steam_bot, account_name)
                break
        return
    
    # ==================== الحساب جاهز ====================
    # "الحساب جاهز عزيزي العميل، الآن قم بتسجيل الدخول على الحساب ⁨xxx⁩ عبر منصة ستيم"
    if "الحساب جاهز" in message or "قم بتسجيل الدخول" in message:
        print(f"✅ الحساب جاهز: {message}")
        cleaned_msg = clean_message(message)
        for user_id, data in list(waiting_requests.items()):
            if request_bot_type.get(user_id) == 'hlle':
                await bot.send_message(user_id, f"✅ {cleaned_msg}")
        return
    
    # ==================== رسالة معالجة الطلب (تجاهل) ====================
    # "📋 رقم الطلب: ... 👤 اسم المستخدم: ... ⏳ نحن نعالج طلبك"
    if "نحن نعالج طلبك" in message or "ستصلك إشعار عند استخراج" in message:
        print(f"📋 رسالة معالجة - نتجاهلها: {message}")
        # لا نرسل هذه الرسالة للمستخدم
        return
    
    # ==================== رقم الطلب موجود (قبل الكود) ====================
    # "رقم الطلب: ⁨208718912⁩ موجود هنا"
    if "رقم الطلب:" in message and "موجود هنا" in message:
        print(f"📋 رقم الطلب موجود: {message}")
        # لا نرسل هذه الرسالة للمستخدم، الكود سيأتي بعدها
        return
    
    # ==================== رمز التحقق (الكود) ====================
    # "⁨||```CDQWW```||⁩ رمز تحقق ستيم"
    if "رمز تحقق" in message or "رمز التحقق" in message:
        print(f"📩 رمز تحقق: {message}")
        
        account_found = False
        cleaned_msg = clean_message(message)
        
        # إرسال الكود لجميع من ينتظرون (فقط طلبات hlle)
        for uid, data in list(waiting_requests.items()):
            if request_bot_type.get(uid) == 'hlle':
                await bot.send_message(uid, f"✅ {cleaned_msg}")
                print(f"📨 أرسلنا الكود للمستخدم {uid}")
                del waiting_requests[uid]
                if uid in request_bot_type:
                    del request_bot_type[uid]
                account_found = True
        
        active_request = None
        
        # أيضاً نبحث في recent_requests
        if not account_found and recent_requests:
            for account, data in list(recent_requests.items()):
                uid = data['user_id']
                if request_bot_type.get(uid) == 'hlle':
                    await bot.send_message(uid, f"✅ {cleaned_msg}")
                    print(f"📨 أرسلنا الكود للمستخدم {uid} من recent_requests")
                    del recent_requests[account]
                    if uid in request_bot_type:
                        del request_bot_type[uid]
                    account_found = True
                    break
        
        if not account_found:
            print("⚠️ لا يوجد أحد ينتظر رمز")
        
        return
    
    # ==================== انتظر للحصول على كود جديد (cooldown) ====================
    if "إنتظر" in message and ("دقائق" in message or "دقيقة" in message):
        print(f"⏳ طلب انتظار: {message}")
        cleaned_msg = clean_message(message)
        for user_id, data in list(waiting_requests.items()):
            if request_bot_type.get(user_id) == 'hlle':
                await bot.send_message(user_id, f"⏳ {cleaned_msg}")
                del waiting_requests[user_id]
                if user_id in request_bot_type:
                    del request_bot_type[user_id]
        active_request = None
        return
    
    # ==================== حساب معلق ====================
    if "معلق" in message:
        print(f"🔴 رد معلق: {message}")
        fixed_message = message.replace("@ skytvx", "@ikon.storee")
        fixed_message = fixed_message.replace("@skytvx", "@ikon.storee")
        cleaned_msg = clean_message(fixed_message)
        for user_id, data in list(waiting_requests.items()):
            if request_bot_type.get(user_id) == 'hlle':
                await bot.send_message(user_id, f"🚫 {cleaned_msg}")
                del waiting_requests[user_id]
                if user_id in request_bot_type:
                    del request_bot_type[user_id]
        active_request = None
        return
    
    # ==================== تجري عملية دخول (الحساب مشغول) ====================
    if "تجرى عملية الدخول" in message or "حاليا تجرى" in message:
        print(f"🔵 الحساب مشغول: {message}")
        cleaned_msg = clean_message(message)
        for user_id, data in list(waiting_requests.items()):
            if request_bot_type.get(user_id) == 'hlle':
                await bot.send_message(user_id, f"⚠️ {cleaned_msg}")
                del waiting_requests[user_id]
                if user_id in request_bot_type:
                    del request_bot_type[user_id]
        active_request = None
        return
    
    # ==================== اسم المستخدم غير صحيح ====================
    if "اسم المستخدم غير صحيح" in message or "غير صحيح" in message:
        print(f"🔴 اسم المستخدم غير صحيح: {message}")
        for user_id, data in list(waiting_requests.items()):
            if request_bot_type.get(user_id) == 'hlle':
                await bot.send_message(user_id, "❌ الحساب غير موجود. تأكد من إدخال اسم الحساب بشكل صحيح.")
                del waiting_requests[user_id]
                if user_id in request_bot_type:
                    del request_bot_type[user_id]
        active_request = None
        return
    
    # ==================== حساب غير موجود ====================
    if "غير موجود" in message or "not found" in message.lower() or "خطأ" in message:
        print(f"🔴 حساب غير موجود: {message}")
        cleaned_msg = clean_message(message)
        for user_id, data in list(waiting_requests.items()):
            if request_bot_type.get(user_id) == 'hlle':
                await bot.send_message(user_id, f"❌ {cleaned_msg}")
                del waiting_requests[user_id]
                if user_id in request_bot_type:
                    del request_bot_type[user_id]
        active_request = None
        return
    
    # ==================== رسالة أخرى غير معروفة ====================
    print(f"📄 رسالة أخرى: {message}")
    # إذا الرسالة تحتوي على أرقام/أحرف (ربما رمز تحقق بصيغة مختلفة)
    codes = re.findall(r'\b[A-Z0-9]{4,8}\b', message)
    if codes and waiting_requests:
        for uid, data in list(waiting_requests.items()):
            if request_bot_type.get(uid) == 'hlle':
                cleaned_msg = clean_message(message)
                await bot.send_message(uid, f"📩 {cleaned_msg}")
                print(f"📨 أرسلنا رسالة محتملة للمستخدم {uid}")
                del waiting_requests[uid]
                if uid in request_bot_type:
                    del request_bot_type[uid]
                active_request = None
                break

# ==================== معالجة ردود PoweredSteamBot ====================
@userbot.on(events.NewMessage(from_users=powered_steam_bot_username))
async def handle_powered_steam_reply(event):
    global active_request
    message = event.raw_text.strip()
    
    print(f"📨 رسالة من PoweredSteamBot: {message}")
    
    # ==================== تأكيد تسجيل الدخول ====================
    # "الرجاء تسجيل دخول على حساب xxx عبر منصة ستيم"
    if "الرجاء تسجيل دخول على حساب" in message or "تسجيل الدخول على حساب" in message:
        print(f"✅ PoweredSteamBot: تأكيد تسجيل الدخول")
        # نرسل رسالة للمستخدم أن عليه تسجيل الدخول
        for user_id, data in list(waiting_requests.items()):
            if request_bot_type.get(user_id) == 'powered':
                await bot.send_message(user_id, messages['login_message'])
                print(f"📨 أرسلنا رسالة تسجيل الدخول للمستخدم {user_id}")
        return
    
    # ==================== رمز التحقق ====================
    # "رمز تحقق لحساب xxx, هو XXXXX"
    if "رمز تحقق لحساب" in message or ("رمز تحقق" in message and "هو" in message):
        print(f"📩 PoweredSteamBot: رمز تحقق: {message}")
        
        account_found = False
        
        # إرسال الكود لجميع من ينتظرون من PoweredSteamBot
        for uid, data in list(waiting_requests.items()):
            if request_bot_type.get(uid) == 'powered':
                await bot.send_message(uid, f"✅ {message}\n\nيوم سعيد 🫶")
                print(f"📨 أرسلنا الكود للمستخدم {uid}")
                del waiting_requests[uid]
                if uid in request_bot_type:
                    del request_bot_type[uid]
                account_found = True
        
        active_request = None
        
        # أيضاً نبحث في recent_requests
        if not account_found and recent_requests:
            for account, data in list(recent_requests.items()):
                uid = data['user_id']
                if request_bot_type.get(uid) == 'powered':
                    await bot.send_message(uid, f"✅ {message}\n\nيوم سعيد 🫶")
                    print(f"📨 أرسلنا الكود للمستخدم {uid} من recent_requests")
                    del recent_requests[account]
                    if uid in request_bot_type:
                        del request_bot_type[uid]
                    account_found = True
                    break
        
        if not account_found:
            print("⚠️ PoweredSteamBot: لا يوجد أحد ينتظر رمز")
        
        return
    
    # ==================== حساب معلق ====================
    # "الدخول لحساب xxx عبر منصة ستيم, معلق لفترة معينة"
    if "معلق" in message:
        print(f"🔴 PoweredSteamBot: حساب معلق: {message}")
        
        # حذف أي ذكر لـ skytvx
        fixed_message = message.replace("@ skytvx", "@ikon.storee")
        fixed_message = fixed_message.replace("@skytvx", "@ikon.storee")
        fixed_message = fixed_message.replace("@ SkyTvX", "@ikon.storee")
        fixed_message = fixed_message.replace("@SkyTvX", "@ikon.storee")
        
        # حذف السطر الذي يحتوي على skytvx بالكامل
        lines = fixed_message.split('\n')
        cleaned_lines = []
        for line in lines:
            if 'skytvx' not in line.lower():
                cleaned_lines.append(line)
        fixed_message = '\n'.join(cleaned_lines)
        
        for uid, data in list(waiting_requests.items()):
            if request_bot_type.get(uid) == 'powered':
                await bot.send_message(uid, f"🚫 {fixed_message.strip()}\n\nللتواصل: @ikon.storee (انستغرام)")
                del waiting_requests[uid]
                if uid in request_bot_type:
                    del request_bot_type[uid]
        
        active_request = None
        return
    
    # ==================== تجري عملية دخول (الحساب مشغول) ====================
    if "تجرى عملية الدخول" in message or "حاليا تجرى" in message:
        print(f"🔵 PoweredSteamBot: الحساب مشغول: {message}")
        for uid, data in list(waiting_requests.items()):
            if request_bot_type.get(uid) == 'powered':
                await bot.send_message(uid, f"⚠️ حالياً تجري عملية دخول على هذا الحساب.\nالرجاء الانتظار 5 دقائق ثم المحاولة مجدداً.")
                del waiting_requests[uid]
                if uid in request_bot_type:
                    del request_bot_type[uid]
        active_request = None
        return
    
    # ==================== حساب غير موجود ====================
    if "غير موجود" in message or "not found" in message.lower():
        print(f"🔴 PoweredSteamBot: حساب غير موجود: {message}")
        for uid, data in list(waiting_requests.items()):
            if request_bot_type.get(uid) == 'powered':
                await bot.send_message(uid, f"❌ {message}")
                del waiting_requests[uid]
                if uid in request_bot_type:
                    del request_bot_type[uid]
        active_request = None
        return
    
    # ==================== رسالة أخرى ====================
    print(f"📄 PoweredSteamBot: رسالة أخرى: {message}")
    # إذا الرسالة تحتوي على كود (5 أحرف/أرقام)
    codes = re.findall(r'\b[A-Z0-9]{5}\b', message)
    if codes and waiting_requests:
        for uid, data in list(waiting_requests.items()):
            if request_bot_type.get(uid) == 'powered':
                await bot.send_message(uid, f"✅ رمز التحقق: {codes[0]}\n\nيوم سعيد 🫶")
                print(f"📨 أرسلنا الكود للمستخدم {uid}")
                del waiting_requests[uid]
                if uid in request_bot_type:
                    del request_bot_type[uid]
                active_request = None
                break

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
