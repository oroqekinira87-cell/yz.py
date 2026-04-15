import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.enums import UserStatus, ChatAction
from flask import Flask
from threading import Thread

# --- كتم الأخطاء ليبقى اللوج نظيفاً ---
logging.basicConfig(level=logging.CRITICAL)
logging.getLogger("pyrogram").setLevel(logging.CRITICAL)
logging.getLogger("werkzeug").setLevel(logging.CRITICAL)

# --- إعدادات الحساب الشخصي ---
API_ID = 26528994 
API_HASH = "8095c1a85b9b743015f8cc0208f4c084"
SESSION_STRING = "BAHpctoAVAWQ_ZjHk91o0eA1OjzqDzSjCSU1o1KNGE7T6Za-frtwXdOG6yl37i1v3xZdyGEH2h_M_5C6nmYt4CtAjyUWx5aB8SiXUipQ-ifKIaNwp0zV1WzzhvYomi_g8KFuU6TQM1JkKrhj51aIuLdjxnvXrCa0RfvWo43INTs8WopcYhKo2FnwLfYvdx1BAQgQ1eBDsyQfFheDpUttseZjEKEyDCLshADe2rRr_aKdRrkiE34Agg7x3jab6jUndY9N2SSj4NF9kkFNMpDHV8RD2ufvVe4FODhU9JkvEF1l1y3mw1GYKliLq4v2B1_FcERRsATLrxdhHZX0uwfOx9TYHbBLaAAAAAHd8u9MAA"

app = Client(
    "Pro_Userbot_Fixed",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)

replied_users = set()

# --- الرسالة المزخرفة ---
FINAL_MESSAGE = """
<b>╭━━━━━━━ • ◈ • ━━━━━━━╮</b>
       <b>👋 أهلاً بك في خدماتنا</b>
<b>╰━━━━━━━ • ◈ • ━━━━━━━╯</b>

⚠️ <b>أنا غير متصل حالياً (OFFLINE)</b>
💬 <i>سأقوم بالرد عليك فور عودتي..</i>

<b>💻 خـدمـات الاسـتـضـافـة:</b>
• ⚡ نوفر لكم استضافة بايثون قوية (<b>شهر، شهرين، وأكثر</b>) حسب المدة والسعر.

<b>🤖 تـصـمـيـم الـبـوتات:</b>
• 🛠️ نقوم بتصميم <b>بوت خاص بك</b> تماماً حسب طلبك ومواصفاتك.

<b>📑 مـلاحـظـة:</b>
يرجى <b>"أرسل رسالتك كاملة الآن"</b> مع كافة التفاصيل، لكي أطلع عليها وأرد عليك مباشرة. ✅

<b>👇 لزيارة موقعنا واستكشاف الخدمات:</b>
<b>┌───────────────────┐</b>
     <b><a href='https://f0623244022-commits.github.io/Vps/'>🌐 اضغط هنا لدخول موقعنا</a></b>
<b>└───────────────────┘</b>

👤 <b>المطور:</b> @far_es_ban
📢 <b>القناة:</b> @fareshw
"""

@app.on_message(filters.private & ~filters.me & ~filters.bot)
async def auto_reply_system(client, message):
    try:
        me = await client.get_me()
        if me.status == UserStatus.ONLINE:
            return

        user_id = message.from_user.id
        await client.send_chat_action(message.chat.id, ChatAction.TYPING)
        await asyncio.sleep(1)

        if user_id not in replied_users:
            replied_users.add(user_id)
            await message.reply_text(FINAL_MESSAGE, disable_web_page_preview=True)
        else:
            reminder = "📌 <b>تذكير:</b> يرجى ترك طلبك كاملاً هنا.\n\n"
            reminder += "🔗 <b>موقعنا:</b> <a href='https://f0623244022-commits.github.io/Vps/'>اضغط هنا للفتح</a>"
            await message.reply_text(reminder, disable_web_page_preview=True)
    except:
        pass

# --- Flask Server ---
flask_app = Flask('')
@flask_app.route('/')
def home(): return "Bot is Online!"

def run_server(): flask_app.run(host='0.0.0.0', port=8080)

# --- وظيفة التشغيل المتوافقة مع بايثون 3.11+ ---
async def start_bot():
    print("✨ جاري تشغيل السكريبت...")
    await app.start()
    print("🚀 البوت يعمل الآن بنجاح!")
    await idle() # يبقي السكريبت يعمل
    await app.stop()

if __name__ == "__main__":
    # تشغيل سيرفر الويب
    Thread(target=run_server, daemon=True).start()
    
    # تشغيل البوت بطريقة Async لتجنب خطأ Event Loop
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(start_bot())
    except RuntimeError:
        # في حال لم تكن هناك حلقة أحداث، يتم إنشاء واحدة جديدة
        asyncio.run(start_bot())
