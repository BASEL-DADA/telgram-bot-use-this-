from telethon import TelegramClient, events
import time
import asyncio
import os
from datetime import datetime
from db import is_user_verified, add_verified_user, is_allowed_order, is_banned_order, log_usage, conn, cursor, get_order_code_for_user

# معلومات الـ API
api_id = int(os.environ.get("API_ID"))
api_hash = os.environ.get("API_HASH")

# إنشاء العميل
client = TelegramClient('my_session', api_id, api_hash)
bot_username = 'PoweredSteamBot'

waiting_requests = {}
active_request = None
welcomed_users = set()  # المستخدمين الذين تم إرسال رسالة الترحيب لهم

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
    allowed_orders = ["ORD123", "ORD345", "ORD457", "ORD567", "ORD678", "ORD789"]
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

    global active_request
    sender = await event.get_sender()
    message = event.raw_text.strip()

    if event.out or event.is_channel or sender.bot:
        return

    # فحص أمر الخروج
    if message.lower() == "exit":
        # حذف المستخدم من قاعدة البيانات
        cursor.execute("DELETE FROM users WHERE user_id = %s;", (sender.id,))
        conn.commit()
        
        # إزالة من المتغيرات
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
            # استخدام first_name من البروفايل
            display_name = sender.first_name or sender.username or "مستخدم مجهول"
            add_verified_user(sender.id, message, display_name)
            await event.reply(messages['order_activated'])
            
            # إرسال رسالة الترحيب مرة واحدة فقط للمستخدمين الجدد
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
    if sender.id in waiting_requests:
        if current_time - waiting_requests[sender.id]['time'] < 180:  # ✅ تغيير من 300 إلى 180 ثانية (3 دقائق)
            await event.reply(messages['wait_5_minutes'])
            return

    if active_request:
        await event.reply(messages['someone_using'])
        return

    print(f"📅 رسالة من {sender.id}: {message}")
    bot = await client.get_entity(bot_username)

    # ✅ حفظ سجل الاستخدام بشكل صحيح
    display_name = sender.first_name or sender.username or "مستخدم مجهول"
    log_usage(
        order_id=user_order_code or "غير معروف",  # رقم الطلب الحقيقي
        user_id=sender.id,
        username=display_name,  # اسم البروفايل
        account=message  # اسم الحساب المرسل
    )

    await client.send_message(bot, message)

    waiting_requests[sender.id] = {
        'account': message,
        'time': current_time
    }
    active_request = sender.id

    async def check_timeout():
        await asyncio.sleep(180)  # ✅ تغيير من 300 إلى 180 ثانية (3 دقائق)
        if sender.id in waiting_requests:
            print(f"⏳ انتهى وقت الانتظار للمستخدم {sender.id}")
            await client.send_message(sender.id, messages['timeout_message'])
            del waiting_requests[sender.id]
            global active_request
            active_request = None

    asyncio.create_task(check_timeout())
    
    # إرسال رسالة "تسجيل الدخول" بعد إرسال الرسالة للبوت مباشرة
    await event.reply(messages['login_message'])

@client.on(events.NewMessage(from_users=bot_username))
async def handle_reply(event):
    global active_request
    message = event.raw_text.strip()

    if "معلق" in message:
        print(f"🔴 تم الكشف عن رد يحتوي على 'معلق': {message}")
        fixed_message = message.replace("@ skytvx", "@ikon.storee")
        for user_id, data in list(waiting_requests.items()):
            await client.send_message(user_id, f"🚫 {fixed_message}")
            del waiting_requests[user_id]
            active_request = None
            print(f"📨 تم إرسال رسالة تعليق للمستخدم {user_id}")
        return

    elif "تجرى عملية الدخول" in message:
        print(f"🔵 تم الكشف عن رد يحتوي على 'تجرى عملية الدخول': {message}")
        for user_id in waiting_requests:
            await client.send_message(user_id, message)
            print(f"📨 تم إرسال رسالة 'تجرى عملية الدخول' للمستخدم {user_id}")
        return

    elif "رمز تحقق لحساب" in message and "هو" in message:
        print(f"📩 تم استلام الرد الثاني من البوت: {message}")
        try:
            account_part = message.split("رمز تحقق لحساب")[1]
            account_name = account_part.split(",")[0].strip().lower()

            for user_id, data in list(waiting_requests.items()):
                if data['account'].lower().strip() == account_name:
                    await client.send_message(user_id, message)
                    print(f"📨 أرسلنا الكود للمستخدم {user_id}")
                    del waiting_requests[user_id]
                    active_request = None
                    break
            else:
                print(f"⚠️ لا يوجد شخص بانتظار هذا الحساب: {account_name}")
        except Exception as e:
            print(f"❌ خطأ أثناء تحليل الرسالة: {e}")
    else:
        print(f"📄 تم تجاهل رد غير متعلق بالكود: {message}")

async def main():
    print("🤖 سكربت باسل شغال...")
    await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())