import os
import asyncio
import logging
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import psycopg2
from psycopg2.extras import RealDictCursor

# Render üçün mini veb server
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

TOKEN = "8674181843:AAHm_9w4I4ERcrl_8_rWDEEETet_-J2uqmk"
ADMIN_ID = 8525508135

# Birbaşa PostgreSQL bağlantı linki
DATABASE_URL = "postgresql://postgres:vugartalis0@db.dmtjsunpgknjljkuopti.supabase.co:5432/postgres"

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

bot = Bot(token=TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

def register_chat(chat_id: int, title: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO chats (chat_id, title) VALUES (%s, %s)
            ON CONFLICT (chat_id) DO UPDATE SET title = EXCLUDED.title;
            """,
            (chat_id, title)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logging.error(f"Chat qeydiyyatı xətası: {e}")

def update_message_count(chat_id: int, user_id: int, username: str, first_name: str):
    today = str(datetime.now().date())
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM user_messages WHERE chat_id = %s AND user_id = %s;", (chat_id, user_id))
        user = cur.fetchone()
        
        if not user:
            cur.execute(
                """
                INSERT INTO user_messages (chat_id, user_id, username, first_name, daily_count, monthly_count, total_count, last_message_date)
                VALUES (%s, %s, %s, %s, 1, 1, 1, %s);
                """,
                (chat_id, user_id, username, first_name, today)
            )
        else:
            daily = 1 if user["last_message_date"] == str(today) else user["daily_count"] + 1
            cur.execute(
                """
                UPDATE user_messages 
                SET daily_count = %s, monthly_count = monthly_count + 1, total_count = total_count + 1, 
                    last_message_date = %s, username = %s, first_name = %s
                WHERE chat_id = %s AND user_id = %s;
                """,
                (daily, today, username, first_name, chat_id, user_id)
            )
            
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logging.error(f"Mesaj yenilənmə xətası: {e}")

@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Məni qrupa əlavə et ➕", url=f"https://t.me/{(await bot.me()).username}?startgroup=true")]
    ])
    
    plain_text = (
        "Salam əziz dostum, mən AzGoldMedianın telegram söhbət qrupları üçün yaratdığı "
        "mesaj sayğacı botuyam, mən qruplarda istifadəçilərin yazdığı mesajları hesablayıb "
        "onları müəyyən mesajlarda təbrik edirəm. Top listə salıram qrupunuzu önə çəkirəm.\n\n"
        "/top - Ümumi qruplar arasında olan liderlik (Aylıq)\n"
        "/gunluk - Sadəcə qrupda olan istifadəçilərin gün ərzində atdığı mesajlar liderlik\n"
        "/ayliq - Sadəcə qrupda olan istifadəçilərin aylıq atdığı mesajlar üzrə liderlik"
    )
    await message.answer(plain_text, reply_markup=keyboard)

@dp.message(Command("reklam"), F.chat.type == "private")
async def cmd_reklam(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Zəhmət olmasa reklam mətnini daxil edin: /reklam [mətn]")
        return
    
    reklam_text = args[1]
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT chat_id FROM chats;")
        chats = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        await message.answer(f"Bazaya qoşulma xətası: {e}")
        return
    
    success, failed = 0, 0
    for chat in chats:
        try:
            await bot.send_message(chat["chat_id"], reklam_text)
            success += 1
            await asyncio.sleep(0.2)
        except Exception:
            failed += 1
            
    await message.answer(f"Reklam göndərildi!\nUğurlu: {success}\nUğursuz: {failed}")

@dp.message(Command("chats"), F.chat.type == "private")
async def cmd_chats(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT chat_id FROM chats;")
        chats = cur.fetchall()
        cur.close()
        conn.close()
        await message.answer(f"Bot hazırda {len(chats)} fərqli qrupda xidmət göstərir.")
    except Exception as e:
        await message.answer(f"Xəta baş verdi: {e}")

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_messages(message: Message):
    if not message.from_user or message.from_user.is_bot:
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.username or "Yoxdur"
    first_name = message.from_user.first_name
    
    register_chat(chat_id, message.chat.title)
    update_message_count(chat_id, user_id, username, first_name)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT daily_count FROM user_messages WHERE chat_id = %s AND user_id = %s;", (chat_id, user_id))
        res = cur.fetchone()
        cur.close()
        conn.close()
        
        if res:
            count = res["daily_count"]
            name = f"@{username}" if username != "Yoxdur" else first_name
            
            if count == 50:
                await message.reply(f"🤩 🇦🇿 Təbriklər {name} qrupa 50 mesaj göndərmişdir 🙌")
            elif count == 100:
                await message.reply(f"👑 Təbriklər {name} bu gün qrupa 100 mesaj göndərmişdir. /gunluk /ayliq")
            elif count == 200:
                await message.reply(f"✌️ {name} bu gün qrupa 200 mesaj göndərmişdir aktiv user adı verilə bilər.")
            elif count == 300:
                await message.reply(f"☺️ Qrupda ən çox aktivliyi saxlayanlardan biri {name} istifadəçisidir o artıq bu gün ərzində qrupa 300 mesaj göndərmişdir")
            elif count == 500:
                await message.reply(f"🤩 Ouu {name} bu gün qrupda 500 mesaj göndərmişdir, Qrupumuzun top listə liderlik səviyyəsinə qalxmasına böyük əməyi dəyir.")
            elif count == 1000:
                await message.reply(f"👑🇦🇿 {name} sənə boss deyə bilərəm çünki sən bu gün qrupa 1000 mesaj göndərmisən qrupun liderlik səviyyəsinə böyük əməyin dəyib.")
    except Exception as e:
        logging.error(f"Şərt yoxlanılarkən xəta: {e}")

@dp.message(Command("gunluk"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_gunluk(message: Message):
    chat_id = message.chat.id
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT first_name, username, daily_count FROM user_messages WHERE chat_id = %s ORDER BY daily_count DESC LIMIT 50;", (chat_id,))
        res = cur.fetchall()
        cur.close()
        conn.close()
        
        if not res:
            await message.answer("Hələki bu gün üçün məlumat yoxdur.")
            return
        
        text = "🚀 Günlük qrup üzrə ən aktiv ən çox mesaj göndərən istifadəçilər:\n\n"
        for i, user in enumerate(res, 1):
            name = f"@{user['username']}" if user['username'] != "Yoxdur" else user['first_name']
            text += f"{i}. {name} - {user['daily_count']} mesaj\n"
            
        await message.answer(text)
    except Exception as e:
        await message.answer("Məlumatlar alınarkən xəta baş verdi.")

@dp.message(Command("ayliq"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_ayliq(message: Message):
    chat_id = message.chat.id
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT first_name, username, monthly_count FROM user_messages WHERE chat_id = %s ORDER BY monthly_count DESC LIMIT 10;", (chat_id,))
        res = cur.fetchall()
        cur.close()
        conn.close()
        
        if not res:
            await message.answer("Hələki bu ay üçün məlumat yoxdur.")
            return
        
        text = "👑 Aylıq user aktivliyi siyahısı:\n\n"
        for i, user in enumerate(res, 1):
            name = f"@{user['username']}" if user['username'] != "Yoxdur" else user['first_name']
            text += f"{i} - ci yer {name} - {user['monthly_count']} mesaj\n"
            
        await message.answer(text)
    except Exception as e:
        await message.answer("Məlumatlar alınarkən xəta baş verdi.")

@dp.message(Command("top"))
async def cmd_top(message: Message):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT chat_id, title FROM chats;")
        chats = cur.fetchall()
        
        chat_totals = []
        for chat in chats:
            cur.execute("SELECT SUM(monthly_count) as total FROM user_messages WHERE chat_id = %s;", (chat["chat_id"],))
            row = cur.fetchone()
            total = row["total"] if row and row["total"] else 0
            chat_totals.append({"title": chat["title"], "total": total, "chat_id": chat["chat_id"]})
            
        cur.close()
        conn.close()
        
        chat_totals.sort(key=lambda x: x["total"], reverse=True)
        
        text = "🏆 Ümumi qruplar arasında liderlik (Aylıq):\n\n"
        for i, item in enumerate(chat_totals[:10], 1):
            text += f"{i} - ci yer {item['title']} - {item['total']} mesaj\n"
            
        if message.chat.type in {"group", "supergroup"}:
            user_chat_id = message.chat.id
            rank = next((i for i, item in enumerate(chat_totals, 1) if item["chat_id"] == user_chat_id), None)
            if rank and rank > 10:
                text += f"\n... Sizin qrup {rank}-ci yerdədir."
                
        await message.answer(text)
    except Exception as e:
        await message.answer("Liderlik cədvəli yüklənərkən xəta baş verdi.")

async def main():
    server_thread = Thread(target=run_web_server, daemon=True)
    server_thread.start()
    
    try:
        await bot.send_message(ADMIN_ID, "🚀 Bot uğurla serverə qoşuldu və fəaliyyətə başladı!")
    except Exception as e:
        logging.error(f"Adminə xəbərdarlıq göndərilə bilmədi: {e}")
        
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
