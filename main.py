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
# 1. CONFIG & SECRETS (Hardcoded for Private Repo)
# ==========================================
BOT_TOKEN = "8804881343:AAFr7Li3dztS-KC7QMd-jdvexIOdvGncc68"
SUPABASE_URL = "https://krkychjmledoaepyeyhw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtya3ljaGptbGVkb2FlcHlleWh3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYyNjcyNTcsImV4cCI6MjEwMTg0MzI1N30.VkMK6-ghUnlFj2n51JTMJE9KQeE55IrH8CjBQR4XgcA"
GROQ_API_KEY = "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"
ADMIN_TG_ID = 8528276558

# Encryption Key for IG Passwords
FERNET_KEY = b'z9X8y7W6v5U4t3S2r1Q0p9O8n7M6l5K4j3I2h1G0f9E=' 
cipher = Fernet(FERNET_KEY)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
app = FastAPI()
ptb = Application.builder().token(BOT_TOKEN).build()
is_initialized = False

# ==========================================
# 2. DATABASE HELPERS (Sab yahi hai, alag file nahi chahiye)
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
# 3. INSTAGRAM ENGINE (Virtual Device & Login)
# ==========================================
def login_instagram(uid, ig_user, ig_pass, proxy_url=None):
    """Logs into IG, generates Virtual Device fingerprint, and saves it."""
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

def get_ig_client(uid):
    """Restores a logged-in session using the saved Virtual Device fingerprint."""
    user = get_user(uid)
    if not user or not user.get("ig_settings"):
        return None
        
    cl = IGClient()
    if user.get("proxy_url"):
        cl.set_proxy(user["proxy_url"])
        
    cl.load_settings(user["ig_settings"])
    cl.login(user["ig_user"], cipher.decrypt(user["ig_pass_enc"].encode()).decode('utf-8'))
    return cl

# ==========================================
# 4. AI ENGINE (Groq + Hinglish + Human Sleep + Emojis)
# ==========================================
async def get_ai_reply(user_message: str, user_context: dict) -> str:
    # 💤 Human Sleep Mode: Random delay before thinking
    await asyncio.sleep(random.uniform(1.5, 3.5))
    
    nickname = user_context.get("nickname", "Friend")
    friends = ", ".join(user_context.get("friends", [])) if user_context.get("friends") else "none"
    
    system_prompt = (
        f"You are InstaPilot, a smart and friendly Telegram bot assistant. "
        f"The user's nickname is {nickname}. Their close friends are {friends}. "
        f"Reply naturally, concisely in Hinglish (Hindi + English mix). "
        f"Use emojis frequently to express emotions (😊🎉🔥💯). "
        f"Act like a real human friend, not an AI. Keep replies short (2-3 lines max)."
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
            
            # 💤 Human Sleep Mode: Random delay before sending (typing time)
            await asyncio.sleep(random.uniform(1.0, 4.0))
            return reply
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return "Bhai, abhi thoda network issue hai. Thodi der baad try kar! 🤕"

# ==========================================
# 5. TELEGRAM HANDLERS (Onboarding & Logic)
# ==========================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            "🎉 *Welcome to InstaPilot!* 🚀\n\n"
            "Chalo pehchaan karte hain! 🤝\n"
            "Tumhara *Nickname* kya rakhun? (e.g., Rocky, Boss, Champion)", 
            parse_mode="Markdown"
        )
        return

    await show_main_menu(update)

async def show_main_menu(update: Update):
    name = update.effective_user.first_name
    await update.effective_chat.send_action("typing")
    await asyncio.sleep(1)
    
    kb = [
        [InlineKeyboardButton("📸 Login Instagram", callback_data="menu_ig_login")],
        [InlineKeyboardButton("🤖 AI Chat Mode", callback_data="menu_chat")],
        [InlineKeyboardButton("⚙️ Settings & Proxy", callback_data="menu_settings")]
    ]
    
    welcome_msg = (
        f"👋 Welcome back, *{name}*! 🎉\n\n"
        f"InstaPilot ready hai! 🚀\n"
        f"Tumhara AI assistant 24/7 available hai. 💪\n\n"
        f"👇 *Kya karna hai aaj?*"
    )
    
    await update.effective_message.reply_text(
        welcome_msg, 
        reply_markup=InlineKeyboardMarkup(kb), 
        parse_mode="Markdown"
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.message: return
    await q.answer()
    uid = update.effective_user.id
    
    if q.data == "accept_priv":
        update_user(uid, {"privacy_accepted": True})
        await q.message.delete()
        await cmd_start(update, context)
    elif q.data == "menu_ig_login":
        update_user(uid, {"state": "wait_ig_user"})
        await q.edit_message_text(
            "📸 *Instagram Login*\n\n"
            "Apna Instagram Username bhejo (bina @ ke):\n"
            "_(e.g., manish.yze)_", 
            parse_mode="Markdown"
        )
    elif q.data == "menu_chat":
        update_user(uid, {"state": "chat_mode"})
        await q.edit_message_text(
            "💬 *AI Chat Mode ON* ✨\n\n"
            "Kuch bhi type karo, main Hinglish me reply dunga! 🤖\n"
            "_(Rukne ka time: 2-5 sec - human feel)_ ⏳"
        )
    elif q.data == "menu_settings":
        await q.edit_message_text(
            "⚙️ *Settings*\n\n"
            "Proxy set karne ke liye bhejo:\n"
            "`/proxy http://user:pass@ip:port`\n\n"
            "_(Optional - IP rotation ke liye)_", 
            parse_mode="Markdown"
        )

async def handle_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    if not user: 
        await cmd_start(update, context)
        return
        
    text = update.message.text.strip()
    state = user.get("state", "idle")
    
    await update.effective_chat.send_action("typing")

    # --- ONBOARDING FLOW ---
    if state == "wait_nickname":
        update_user(uid, {"nickname": text, "state": "wait_age"})
        await update.message.reply_text(
            f"Badhiya *{text}*! 😎✨\n"
            "Ab batao, tumhari *Age* kya hai? (Sirf number likho) 🔢", 
            parse_mode="Markdown"
        )
        
    elif state == "wait_age":
        if text.isdigit():
            update_user(uid, {"age": int(text), "state": "wait_bday"})
            await update.message.reply_text(
                f"Noted! 🎂\n"
                "Tumhara *Birthday* kab hai? (DD-MM format me likho)\n"
                "_(e.g., 15-08 for 15 August)_ 🎉"
            )
        else:
            await update.message.reply_text("Bhai, sirf number likho age ke liye! 🔢")
            
    elif state == "wait_bday":
        update_user(uid, {"birthday": text, "state": "wait_friends"})
        await update.message.reply_text(
            "Done! 🎊\n"
            "Ab apne *Top 3 Friends* ke naam comma (,) laga kar bhejo.\n"
            "_(e.g., Rahul, Priya, Amit)_ 👥"
        )
        
    elif state == "wait_friends":
        friends = [f.strip() for f in text.split(",")]
        update_user(uid, {"friends": friends, "state": "idle"})
        await update.message.reply_text(
            f"Perfect! 🧠✨\n"
            f"{', '.join(friends)} ko yaad rakh liya.\n"
            "Ab tumhara setup complete hai! 🎉\n\n"
            "Ab Instagram login kar sakte ho ya AI chat start kar sakte ho! 🚀"
        )
        await show_main_menu(update)

    # --- INSTAGRAM LOGIN FLOW ---
    elif state == "wait_ig_user":
        update_user(uid, {"ig_user": text, "state": "wait_ig_pass"})
        await update.message.reply_text(
            f"🔒 Username *@{text}* save ho gaya.\n\n"
            "Ab apna *Password* bhejo.\n"
            "_(Ye encrypted hoke save hoga, koi nahi dekh payega)_ 🔐"
        )
        
    elif state == "wait_ig_pass":
        await update.message.reply_text(
            "⏳ *Virtual Device generate ho raha hai...*\n"
            "Login ho raha hai... (10-15 sec lagenge) 🔄"
        )
        try:
            success, msg = login_instagram(uid, user["ig_user"], text, user.get("proxy_url"))
            update_user(uid, {"state": "idle"})
            if success:
                await update.message.reply_text(
                    f"✅ *{msg}*\n\n"
                    "Tumhara account connect ho gaya! 🎉\n"
                    "Virtual phone ready hai. 📱✨"
                )
            else:
                await update.message.reply_text(f"❌ Login fail: {msg}")
        except Exception as e:
            update_user(uid, {"state": "idle"})
            await update.message.reply_text(
                f"❌ *Error:* {str(e)}\n\n"
                "_(Shayad IG ne block kiya ya proxy galat hai)_ 🤕"
            )

    # --- AI CHAT MODE ---
    elif state == "chat_mode" or user.get("privacy_accepted"):
        reply = await get_ai_reply(text, user)
        await update.message.reply_text(reply)

async def handle_proxy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text(
            "⚙️ *Proxy Usage:*\n\n"
            "`/proxy http://user:pass@ip:port`\n\n"
            "_(IP rotation ke liye optional)_", 
            parse_mode="Markdown"
        )
        return
    update_user(update.effective_user.id, {"proxy_url": context.args[0]})
    await update.message.reply_text(
        "✅ *Proxy IP save ho gayi!* 🌍\n\n"
        "Ab IG login is IP se hoga. 🔒"
    )

def register_handlers(app):
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("proxy", handle_proxy_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_private_text))

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
