import os
import asyncio
import logging
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from supabase import create_client, Client

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

# Supabase URL və Key
SUPABASE_URL = "https://dmtjsunpgknljkuopti.supabase.co"
SUPABASE_KEY = "sb_publishable_4q0aoNK3helEzcBxtn70mg_-WfZNRdk"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

bot = Bot(token=TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

def register_chat(chat_id: int, title: str):
    try:
        supabase.table("chats").upsert({"chat_id": chat_id, "title": title}).execute()
    except Exception as e:
        logging.error(f"Chat qeydiyyatı xətası: {e}")

def update_message_count(chat_id: int, user_id: int, username: str, first_name: str):
    today = str(datetime.now().date())
    try:
        res = supabase.table("user_messages").select("*").eq("chat_id", chat_id).eq("user_id", user_id).execute()
        
        if not res.data:
            supabase.table("user_messages").insert({
                "chat_id": chat_id,
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "daily_count": 1,
                "monthly_count": 1,
                "total_count": 1,
                "last_message_date": today
            }).execute()
        else:
            user = res.data[0]
            daily = 1 if user.get("last_message_date") == today else user.get("daily_count", 0) + 1
            
            supabase.table("user_messages").update({
                "daily_count": daily,
                "monthly_count": user.get("monthly_count", 0) + 1,
                "total_count": user.get("total_count", 0) + 1,
                "last_message_date": today,
                "username": username,
                "first_name": first_name
            }).eq("chat_id", chat_id).eq("user_id", user_id).execute()
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
        chats = supabase.table("chats").select("chat_id").execute()
    except Exception as e:
        await message.answer(f"Bazaya qoşulma xətası: {e}")
        return
    
    success, failed = 0, 0
    for chat in chats.data:
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
        chats = supabase.table("chats").select("chat_id").execute()
        count = len(chats.data)
        await message.answer(f"Bot hazırda {count} fərqli qrupda xidmət göstərir.")
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
        res = supabase.table("user_messages").select("daily_count").eq("chat_id", chat_id).eq("user_id", user_id).execute()
        if res.data:
            count = res.data[0]["daily_count"]
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
        res = supabase.table("user_messages").select("first_name, username, daily_count").eq("chat_id", chat_id).order("daily_count", desc=True).limit(50).execute()
        
        if not res.data:
            await message.answer("Hələki bu gün üçün məlumat yoxdur.")
            return
        
        text = "🚀 Günlük qrup üzrə ən aktiv ən çox mesaj göndərən istifadəçilər:\n\n"
        for i, user in enumerate(res.data, 1):
            name = f"@{user['username']}" if user['username'] != "Yoxdur" else user['first_name']
            text += f"{i}. {name} - {user['daily_count']} mesaj\n"
            
        await message.answer(text)
    except Exception as e:
        await message.answer("Məlumatlar alınarkən xəta baş verdi.")

@dp.message(Command("ayliq"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_ayliq(message: Message):
    chat_id = message.chat.id
    try:
        res = supabase.table("user_messages").select("first_name, username, monthly_count").eq("chat_id", chat_id).order("monthly_count", desc=True).limit(10).execute()
        
        if not res.data:
            await message.answer("Hələki bu ay üçün məlumat yoxdur.")
            return
        
        text = "👑 Aylıq user aktivliyi siyahısı:\n\n"
        for i, user in enumerate(res.data, 1):
            name = f"@{user['username']}" if user['username'] != "Yoxdur" else user['first_name']
            text += f"{i} - ci yer {name} - {user['monthly_count']} mesaj\n"
            
        await message.answer(text)
    except Exception as e:
        await message.answer("Məlumatlar alınarkən xəta baş verdi.")

@dp.message(Command("top"))
async def cmd_top(message: Message):
    try:
        chats = supabase.table("chats").select("chat_id, title").execute()
        chat_totals = []
        
        for chat in chats.data:
            res = supabase.table("user_messages").select("monthly_count").eq("chat_id", chat["chat_id"]).execute()
            total = sum([row["monthly_count"] for row in res.data])
            chat_totals.append({"title": chat["title"], "total": total, "chat_id": chat["chat_id"]})
            
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
