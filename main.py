import os, asyncio, random, json, logging
from datetime import datetime
from fastapi import FastAPI, Request
from supabase import create_client
from cryptography.fernet import Fernet
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler, 
                          CallbackQueryHandler, filters, ContextTypes)
from instagrapi import Client as IGClient
import httpx

logging.basicConfig(level=logging.INFO)

# ==========================================
# 1. CONFIG & SECRETS
# ==========================================
BOT_TOKEN = "8804881343:AAFr7Li3dztS-KC7QMd-jdvexIOdvGncc68"
SUPABASE_URL = "https://krkychjmledoaepyeyhw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtya3ljaGptbGVkb2FlcHlleWh3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYyNjcyNTcsImV4cCI6MjEwMTg0MzI1N30.VkMK6-ghUnlFj2n51JTMJE9KQeE55IrH8CjBQR4XgcA"
GROQ_API_KEY = "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"
ADMIN_TG_ID = 8528276558

FERNET_KEY = b'z9X8y7W6v5U4t3S2r1Q0p9O8n7M6l5K4j3I2h1G0f9E=' 
cipher = Fernet(FERNET_KEY)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
app = FastAPI()

# Bot Application Build
ptb = Application.builder().token(BOT_TOKEN).build()
is_initialized = False

# ==========================================
# 2. DATABASE HELPERS
# ==========================================
def get_user(uid):
    res = supabase.table("users").select("*").eq("tg_id", uid).execute()
    return res.data[0] if res.data else None

def create_user(uid, name, username):
    supabase.table("users").insert({
        "tg_id": uid, "name": name, "username": username, 
        "privacy_accepted": False, "state": "idle"
    }).execute()

def update_user(uid, data):
    supabase.table("users").update(data).eq("tg_id", uid).execute()

# ==========================================
# 3. INSTAGRAM ENGINE
# ==========================================
def login_instagram(uid, ig_user, ig_pass, proxy_url=None):
    cl = IGClient()
    if proxy_url:
        cl.set_proxy(proxy_url)
    cl.login(ig_user, ig_pass)
    settings = cl.get_settings()
    enc_pass = cipher.encrypt(ig_pass.encode()).decode('utf-8')
    update_user(uid, {
        "ig_user": ig_user,
        "ig_pass_enc": enc_pass,
        "ig_settings": settings,
        "proxy_url": proxy_url
    })
    return True, "Login Successful! Virtual device created."

# ==========================================
# 4. AI ENGINE (Groq + Hinglish + Emojis)
# ==========================================
async def get_ai_reply(user_message: str, user_context: dict) -> str:
    await asyncio.sleep(random.uniform(1.5, 3.5))
    
    nickname = user_context.get("nickname") or "Friend"
    friends_list = user_context.get("friends") or []
    friends = ", ".join(friends_list) if friends_list else "none"
    
    system_prompt = (
        f"You are InstaPilot, a smart and friendly Telegram bot assistant. "
        f"The user's nickname is {nickname}. Their close friends are {friends}. "
        f"Reply naturally, concisely in Hinglish (Hindi + English mix). "
        f"Use emojis frequently (😊🎉🔥). Act like a real human friend. "
        f"Keep replies short (2-3 lines max)."
    )

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.8
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers)
            res.raise_for_status()
            reply = res.json()["choices"][0]["message"]["content"].strip()
            await asyncio.sleep(random.uniform(1.0, 3.0))
            return reply
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return "Bhai, abhi thoda network issue hai. Thodi der baad try kar! 🤕"

# ==========================================
# 5. TELEGRAM HANDLERS (DEBUG MODE ON 🔍)
# ==========================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = update.effective_user.id
        user = get_user(uid)
        
        if not user:
            create_user(uid, update.effective_user.full_name, update.effective_user.username)
            user = get_user(uid)
            
        if not user.get("privacy_accepted"):
            kb = [[InlineKeyboardButton("✅ I Accept", callback_data="accept_priv")]]
            await update.effective_message.reply_text(
                "🛡️ *InstaPilot Privacy Policy*\n\n"
                "Hum tumhara IG password encrypt karke rakhte hain.\n"
                "Data safe hai. Accept karo?",
                reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
            )
            return

        if not user.get("nickname"):
            update_user(uid, {"state": "wait_nickname"})
            await update.effective_message.reply_text(
                " *Welcome to InstaPilot!* 🚀\n\n"
                "Chalo pehchaan karte hain! 🤝\n"
                "Tumhara *Nickname* kya rakhun?", 
                parse_mode="Markdown"
            )
            return

        await show_main_menu(update)
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ DEBUG ERROR (start): {e}")

async def show_main_menu(update: Update):
    name = update.effective_user.first_name
    await update.effective_chat.send_action("typing")
    await asyncio.sleep(1)
    
    kb = [
        [InlineKeyboardButton(" Login Instagram", callback_data="menu_ig_login")],
        [InlineKeyboardButton("🤖 AI Chat Mode", callback_data="menu_chat")],
        [InlineKeyboardButton("⚙️ Settings & Proxy", callback_data="menu_settings")]
    ]
    
    await update.effective_message.reply_text(
        f"👋 Welcome back, *{name}*! 🎉\n\n"
        f"InstaPilot ready hai! 🚀\n"
        f"Tumhara AI assistant 24/7 available hai. 💪\n\n"
        f"👇 *Kya karna hai aaj?*", 
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.message: return
    await q.answer()
    uid = update.effective_user.id
    
    try:
        if q.data == "accept_priv":
            update_user(uid, {"privacy_accepted": True})
            await q.message.delete()
            await cmd_start(update, context)
        elif q.data == "menu_ig_login":
            update_user(uid, {"state": "wait_ig_user"})
            await q.edit_message_text("📸 *Instagram Login*\n\nApna Instagram Username bhejo (bina @ ke):", parse_mode="Markdown")
        elif q.data == "menu_chat":
            update_user(uid, {"state": "chat_mode"})
            await q.edit_message_text("💬 *AI Chat Mode ON* ✨\n\nKuch bhi type karo, main Hinglish me reply dunga! 🤖")
        elif q.data == "menu_settings":
            await q.edit_message_text("️ Proxy set karne ke liye bhejo:\n`/proxy http://user:pass@ip:port`", parse_mode="Markdown")
    except Exception as e:
        await q.message.reply_text(f"⚠️ DEBUG ERROR (button): {e}")

async def handle_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = update.effective_user.id
        user = get_user(uid)
        if not user: 
            await cmd_start(update, context)
            return
            
        text = update.message.text.strip()
        state = user.get("state") or "idle"
        
        await update.effective_chat.send_action("typing")

        if state == "wait_nickname":
            update_user(uid, {"nickname": text, "state": "wait_age"})
            await update.message.reply_text(f"Badhiya *{text}*! 😎\nAb tumhari *Age*? (sirf number) 🔢", parse_mode="Markdown")
            
        elif state == "wait_age":
            if text.isdigit():
                update_user(uid, {"age": int(text), "state": "wait_bday"})
                await update.message.reply_text("Noted! 🎂\n*Birthday* kab hai? (DD-MM format) 🎉")
            else:
                await update.message.reply_text("Bhai, sirf number likho! 🔢")
                
        elif state == "wait_bday":
            update_user(uid, {"birthday": text, "state": "wait_friends"})
            await update.message.reply_text("Done! 🎊\n*Top 3 Friends* ke naam comma se bhejo (Rahul, Priya, Amit) 👥")
            
        elif state == "wait_friends":
            friends = [f.strip() for f in text.split(",")]
            update_user(uid, {"friends": friends, "state": "idle"})
            await update.message.reply_text(f"Perfect! 🧠✨ {', '.join(friends)} ko yaad rakh liya.\nSetup complete! ")
            await show_main_menu(update)

        elif state == "wait_ig_user":
            update_user(uid, {"ig_user": text, "state": "wait_ig_pass"})
            await update.message.reply_text(f"🔒 Username *@{text}* save!\nAb *Password* bhejo (encrypted save hoga) 🔐", parse_mode="Markdown")
            
        elif state == "wait_ig_pass":
            await update.message.reply_text(" Virtual Device ban raha hai... Login ho raha hai... 🔄")
            try:
                success, msg = login_instagram(uid, user["ig_user"], text, user.get("proxy_url"))
                update_user(uid, {"state": "idle"})
                await update.message.reply_text(f"✅ {msg}\nAccount connect! 📱✨")
            except Exception as e:
                update_user(uid, {"state": "idle"})
                await update.message.reply_text(f"❌ Login Error: {str(e)[:200]}")

        elif state == "chat_mode" or user.get("privacy_accepted"):
            reply = await get_ai_reply(text, user)
            await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"️ DEBUG ERROR (text): {e}")

async def handle_proxy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /proxy http://user:pass@ip:port")
        return
    update_user(update.effective_user.id, {"proxy_url": context.args[0]})
    await update.message.reply_text("✅ Proxy save! 🌍")

def register_handlers(application):
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("proxy", handle_proxy_cmd))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_private_text))

# 🔥 THE FIX: Actually calling the function to register handlers!
register_handlers(ptb)

# ==========================================
# 6. FASTAPI WEBHOOK
# ==========================================
@app.post("/api/webhook")
async def webhook(request: Request):
    global is_initialized
    if not is_initialized:
        await ptb.initialize()
        is_initialized = True
    data = await request.json()
    update = Update.de_json(data, ptb.bot)
    await ptb.process_update(update)
    return {"status": "ok"}
