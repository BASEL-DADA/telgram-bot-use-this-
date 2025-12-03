from telethon import TelegramClient, events
from telethon.sessions import StringSession
import time
import asyncio
import os
from datetime import datetime
from db import is_user_verified, add_verified_user, is_allowed_order, is_banned_order, log_usage, conn, cursor, get_order_code_for_user

# معلومات الـ API
api_id = int(os.environ.get("API_ID"))
api_hash = os.environ.get("API_HASH")
session_string = os.environ.get("SESSION_STRING")  # ✅ استخدام String Session

# إنشاء العميل باستخدام String Session
if not session_string:
    raise ValueError("❌ SESSION_STRING غير موجود! يرجى إضافته في متغيرات Heroku")

client = TelegramClient(StringSession(session_string), api_id, api_hash)
bot_username = 'PoweredSteamBot'

waiting_requests = {}
# active_request = None  # ✅ تم إلغاؤه للسماح بأكثر من مستخدم
welcomed_users = set()

# إعدادات النظام
MAX_CONCURRENT_USERS = 10  # الحد الأقصى للمستخدمين المتزامنين
REQUEST_TIMEOUT = 180  # 3 دقائق

allowed_accounts = {
    'quzz5e',
}

# الرسائل بالعربي فقط
messages = {
    'welcome': "👋 أهلاً بك في بوت *ايكون ستور*!\n\n🔹 **طريقة الاستخدام:**\n- قم بتسجيل الدخول بالحساب على منصة ستيم.\n- مباشرة بعد تسجيل الدخول، أرسل **اسم الحساب** للبوت هنا.\n- انتظر قليلًا، وسيصلك رمز التحقق خلال دقائق.\n\n⚠️ **ملاحظة:** يمنع مشاركة الحسابات، وأي مشاركة ستؤدي إلى **سحب الحساب نهائيًا**.",
    'wait_5_minutes': "🚫 الرجاء الانتظار 3 دقائق قبل إرسال حساب آخر.",
    'someone_using': "🚫 شخص آخر يستخدم البوت حالياً. الرجاء الانتظار 3 دقائق ثم المحاولة مجددًا.",
    'login_message': "📩 الرجاء تسجيل دخول على الحساب عبر منصة ستيم\nوسيتم إرسال رمز التحقق إليك خلال 15 ثانية إلى 3 دقائق.\n\nيوم سعيد 🫶",
    'timeout_message': "⏳ تأخر وصول الرمز؟ تأكد أنك سجلت بالطريقة الصحيحة.",
    'order_banned': "🚫 هذا رقم الطلب محظور.",
    'order_activated': "✅ تم تفعيل رقم الطلب. يمكنك الآن استخدام البوت.",
    'send_order_first': "🔑 الرجاء إرسال رقم الطلب أولاً.",
    'account_banned': "🚫 تم حظر حسابك من استخدام البوت. تواصل مع الإدارة.",
    'invalid_account': "❌ الرجاء إرسال اسم حساب صحيح (بالأحرف الإنجليزية فقط)"
}

# ✅ استيراد الطلبات تلقائيًا مرة واحدة فقط عند التشغيل الأول
def auto_insert_orders():
    allowed_orders = [
        "ORD123", "ORD345", "ORD457", "ORD567", "ORD678", "ORD789",
        "25326725", "6782345", "5535642", "6493405", "17593648", "2313123", 
        "233214", "3453028753", "36537234", "3535432", "63952704", "436436", 
        "47537464", "44455654", "45346457427", "456453753", "4575647", 
        "46464564", "4745457", "4745649108", "4774457", "53426157", "5347654", 
        "5390265257", "6345634", "63952704", "642747", "645753858", "678234", 
        "7789", "78439458", "7893125", "804362911", "867", "8781", "88779", 
        "890123", "8912", "4258329"
    ]
    for order in allowed_orders:
        cursor.execute("""
            INSERT INTO orders (order_code, is_banned)
            VALUES (%s, FALSE)
            ON CONFLICT (order_code) DO NOTHING;
        """, (order.lower(),))
    conn.commit()
    print("✅ الطلبات المسموحة أُضيفت تلقائيًا (أو كانت موجودة).")

# تنفيذ الإدخال التلقائي عند بدء التشغيل
auto_insert_orders()

@client.on(events.NewMessage)
async def handle_incoming(event):
    if not event.is_private:
        return

    sender = await event.get_sender()
    message = event.raw_text.strip()

    if event.out or event.is_channel or sender.bot:
        return

    # فحص أمر الخروج
    if message.lower() == "exit":
        cursor.execute("DELETE FROM users WHERE user_id = %s;", (sender.id,))
        conn.commit()
        
        if sender.id in welcomed_users:
            welcomed_users.remove(sender.id)
        if sender.id in waiting_requests:
            del waiting_requests[sender.id]
        
        await event.reply("🚪 تم تسجيل خروجك بنجاح. أرسل رقم الطلب لإعادة التفعيل.")
        return

    # ✅ التحقق من التفعيل
    if not is_user_verified(sender.id):
        if is_banned_order(message):
            await event.reply(messages['order_banned'])
            return
        elif is_allowed_order(message):
            display_name = sender.first_name or sender.username or "مستخدم مجهول"
            add_verified_user(sender.id, message, display_name)
            await event.reply(messages['order_activated'])
            
            if sender.id not in welcomed_users:
                welcomed_users.add(sender.id)
                await event.reply(messages['welcome'])
            return
        else:
            await event.reply(messages['send_order_first'])
            return

    # ✅ فحص إذا كان المستخدم المفعل محظور
    user_order_code = get_order_code_for_user(sender.id)
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
    
    # التحقق من وقت الانتظار للمستخدم نفسه
    if sender.id in waiting_requests:
        if current_time - waiting_requests[sender.id]['time'] < REQUEST_TIMEOUT:
            remaining_time = int(REQUEST_TIMEOUT - (current_time - waiting_requests[sender.id]['time']))
            await event.reply(f"🚫 الرجاء الانتظار {remaining_time} ثانية قبل إرسال حساب آخر.")
            return
    
    # التحقق من عدد المستخدمين المتزامنين
    active_users = sum(1 for uid, data in waiting_requests.items() 
                      if current_time - data['time'] < REQUEST_TIMEOUT)
    
    if active_users >= MAX_CONCURRENT_USERS:
        await event.reply(f"⏳ البوت مشغول حالياً ({active_users}/{MAX_CONCURRENT_USERS} مستخدمين)\n"
                         f"الرجاء الانتظار قليلاً والمحاولة مرة أخرى.")
        return
    print(f"📅 رسالة من {sender.id}: {message}")
    bot = await client.get_entity(bot_username)

    display_name = sender.first_name or sender.username or "مستخدم مجهول"
    
    # تسجيل الاستخدام
    log_usage(
        order_id=user_order_code or "غير معروف",
        user_id=sender.id,
        username=display_name,
        account=message
    )
    
    waiting_requests[sender.id] = {
        'account': message,
        'time': current_time
    }

    # عرض موقع المستخدم في الطابور
    queue_position = len([uid for uid, data in waiting_requests.items() 
                         if data['time'] <= current_time])
    
    # إرسال رسالة التأكيد للمستخدم
    await event.reply(messages['login_message'])
    await client.send_message(bot.id, message)
    
    async def check_timeout():
        await asyncio.sleep(REQUEST_TIMEOUT)
        if sender.id in waiting_requests:
            print(f"⏳ انتهى وقت الانتظار للمستخدم {sender.id}")
            await client.send_message(sender.id, messages['timeout_message'])
            del waiting_requests[sender.id]

    asyncio.create_task(check_timeout())
@client.on(events.NewMessage(from_users=bot_username))
async def handle_reply(event):
    message = event.raw_text.strip()

    if "معلق" in message:
        print(f"🔴 تم الكشف عن رد يحتوي على 'معلق': {message}")
        fixed_message = message.replace("@ skytvx", "@ikon.storee")
        
        # إرسال للجميع (في حالة عدم معرفة الحساب المحدد)
        sent_to = []
        for user_id, data in list(waiting_requests.items()):
            await client.send_message(user_id, f"🚫 {fixed_message}")
            del waiting_requests[user_id]
            sent_to.append(user_id)
            print(f"📨 تم إرسال رسالة تعليق للمستخدم {user_id}")
        
        if sent_to:
            print(f"✅ تم إرسال رسالة التعليق لـ {len(sent_to)} مستخدمين")
        return
    elif "رمز تحقق لحساب" in message and "هو" in message:
        print(f"📩 تم استلام الرد من البوت: {message}")
        try:
            account_part = message.split("رمز تحقق لحساب")[1]
            account_name = account_part.split(",")[0].strip().lower()

            # البحث عن المستخدم المطابق
            found = False
            for user_id, data in list(waiting_requests.items()):
                if data['account'].lower().strip() == account_name:
                    await client.send_message(user_id, message)
                    print(f"✅ تم إرسال الكود للمستخدم {user_id} للحساب {account_name}")
                    del waiting_requests[user_id]
                    found = True
                    break
            
            if not found:
                print(f"⚠️ لا يوجد مستخدم بانتظار الحساب: {account_name}")
                print(f"📋 المستخدمون الحاليون: {[data['account'] for data in waiting_requests.values()]}")
        except Exception as e:
            print(f"❌ خطأ أثناء تحليل الرسالة: {e}")
    else:
        print(f"📄 تم تجاهل رد غير متعلق بالكود: {message}")

async def main():
    print("🤖 سكربت ايكون ستور شغال...")
    await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())
