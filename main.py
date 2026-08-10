import os, asyncio, random, json, logging, time
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
ptb = Application.builder().token(BOT_TOKEN).build()
is_initialized = False

# ==========================================
# 2. DATABASE HELPERS
# ==========================================
def get_user(uid):
    res = supabase.table("users").select("*").eq("tg_id", uid).execute()
    return res.data[0] if res.data else None

def create_user(uid, name, username, referred_by=None):
    ref_code = f"REF{uid}"
    data = {
        "tg_id": uid, "name": name, "username": username, 
        "privacy_accepted": False, "state": "idle", "referral_code": ref_code
    }
    if referred_by:
        data["referred_by"] = int(referred_by)
        try:
            referrer = get_user(int(referred_by))
            if referrer:
                supabase.table("users").update({"referral_count": referrer.get("referral_count", 0) + 1}).eq("tg_id", int(referred_by)).execute()
        except: pass
    supabase.table("users").insert(data).execute()

def update_user(uid, data):
    supabase.table("users").update(data).eq("tg_id", uid).execute()

def get_all_users():
    res = supabase.table("users").select("tg_id").execute()
    return [u["tg_id"] for u in res.data]

# ==========================================
# 3. INSTAGRAM ENGINE (Session ID + Automation)
# ==========================================
def login_by_sessionid(uid, session_id):
    cl = IGClient()
    try:
        cl.login_by_sessionid(session_id)
        settings = cl.get_settings()
        update_user(uid, {
            "ig_user": cl.username,
            "ig_pass_enc": "SESSION_LOGIN",
            "ig_settings": settings,
            "proxy_url": None
        })
        return True, f"Logged in as @{cl.username} via Session ID!"
    except Exception as e:
        return False, str(e)

def get_ig_client(uid):
    user = get_user(uid)
    if not user or not user.get("ig_settings"):
        return None
    cl = IGClient()
    if user.get("proxy_url"):
        cl.set_proxy(user["proxy_url"])
    cl.load_settings(user["ig_settings"])
    cl.login(user["ig_user"], cipher.decrypt(user["ig_pass_enc"].encode()).decode('utf-8') if user["ig_pass_enc"] != "SESSION_LOGIN" else "")
    # Agar session expired ho to session ID se retry karein (agar stored ho) - simplified for now
    return cl

# Emotional Messages
MSG_FOLLOW_ACCEPT = "Hey... thanks for following. Sach kahun toh main khud ko kaafi lost aur useless feel karta hu aajkal. Agar tumhara koi specific kaam hai ya kuch help chahiye toh bata dena, warna bas yahi. Thanks for being here. Take care. "
MSG_DM_REPLY = "Hey... kaise ho? Sach bataun toh main thoda akela feel kar raha hu aajkal. Tum sunaao, sab theek? Agar kuch share karna ho toh main hu yahan. 🥺"

# ==========================================
# 4. AI ENGINE (Groq)
# ==========================================
async def get_ai_reply(user_message: str, user_context: dict) -> str:
    nickname = user_context.get("nickname") or "Friend"
    system_prompt = (
        f"You are InstaPilot, a smart, witty, and friendly Telegram bot assistant. "
        f"The user's nickname is {nickname}. Reply naturally in Hinglish. "
        f"Use emojis frequently (😊🎉🔥💯). Act like a real human friend."
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
            return res.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return "Bhai, abhi thoda network issue hai. Thodi der baad try kar! 🤕"

# ==========================================
# 5. TELEGRAM HANDLERS
# ==========================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = update.effective_user.id
        user = get_user(uid)
        referred_by = None
        if context.args and context.args[0].startswith("REF"):
            referred_by = context.args[0].replace("REF", "")

        if not user:
            create_user(uid, update.effective_user.full_name, update.effective_user.username, referred_by)
            user = get_user(uid)
            
        if not user.get("privacy_accepted"):
            kb = [[InlineKeyboardButton("✅ I Accept", callback_data="accept_priv")]]
            await update.effective_message.reply_text("️ *InstaPilot Privacy Policy*\n\nHum tumhara data encrypt karke rakhte hain. Accept karo? 🔐", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
            return

        if not user.get("nickname"):
            update_user(uid, {"state": "wait_nickname"})
            await update.effective_message.reply_text("🎉 *Welcome to InstaPilot!* 🚀\n\nTumhara *Nickname* kya rakhun?", parse_mode="Markdown")
            return

        await show_main_menu(update)
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ ERROR: {e}")

async def show_main_menu(update: Update):
    name = update.effective_user.first_name
    await update.effective_chat.send_action("typing")
    await asyncio.sleep(1.5) 
    
    kb = [
        [InlineKeyboardButton(" Safe IG Login", callback_data="menu_ig_login")],
        [InlineKeyboardButton(" AI Chat Mode", callback_data="menu_chat")],
        [InlineKeyboardButton(" Refer & Earn 💰", callback_data="menu_refer")],
        [InlineKeyboardButton("📊 My Stats", callback_data="menu_stats")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings")]
    ]
    await update.effective_message.reply_text(f" Welcome back, *{name}*! 🎉\n\n👇 *Kya karna hai aaj?*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

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
            update_user(uid, {"state": "wait_session_id"})
            await q.edit_message_text("📸 *Safe Instagram Login* 🔐\n\n1. Chrome me 'Desktop site' on karo\n2. Instagram.com par login karo\n3. Cookies me jakar 'sessionid' copy karo\n4. Wo lamba code yahan paste kar do 👇", parse_mode="Markdown")
        elif q.data == "menu_chat":
            update_user(uid, {"state": "chat_mode"})
            await q.edit_message_text("💬 *AI Chat Mode ON* ✨\n\nKuch bhi type karo! 🤖")
        elif q.data == "menu_refer":
            user = get_user(uid)
            ref_count = user.get("referral_count", 0) if user else 0
            ref_link = f"https://t.me/InstaPilot_bot?start=REF{uid}"
            await q.edit_message_text(f"👥 *Refer & Earn* 💰\n\n🔗 *Link:*\n`{ref_link}`\n\n📊 *Referrals:* {ref_count} ", parse_mode="Markdown")
        elif q.data == "menu_stats":
            user = get_user(uid)
            if user:
                stats = f"📊 *Profile*\n\n👤 {user.get('name')}\n😎 {user.get('nickname')}\n🎂 {user.get('age')}\n🎉 {user.get('birthday')}\n👥 {', '.join(user.get('friends', [])) or 'None'}\n {user.get('created_at', 'N/A')[:10]}\n *Refs:* {user.get('referral_count', 0)}"
                await q.edit_message_text(stats, parse_mode="Markdown")
        elif q.data == "menu_settings":
            await q.edit_message_text("⚙️ *Settings*\n\nUse `/check_ig_requests` to auto-accept & DM.\nUse `/check_ig_dms` to auto-reply.\nUse `/auto_react` to like recent reels.")
    except Exception as e:
        await q.message.reply_text(f"⚠️ ERROR: {e}")

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
            await update.message.reply_text(f"Badhiya *{text}*! 😎\nAb *Age*? (number)", parse_mode="Markdown")
        elif state == "wait_age":
            if text.isdigit():
                update_user(uid, {"age": int(text), "state": "wait_bday"})
                await update.message.reply_text("Noted! 🎂\n*Birthday*? (DD-MM)", parse_mode="Markdown")
            else: await update.message.reply_text("Sirf number likho! 🔢")
        elif state == "wait_bday":
            update_user(uid, {"birthday": text, "state": "wait_friends"})
            await update.message.reply_text("Done! 🎊\n*Top 3 Friends* (comma se)")
        elif state == "wait_friends":
            friends = [f.strip() for f in text.split(",")]
            update_user(uid, {"friends": friends, "state": "idle"})
            await update.message.reply_text(f"Perfect! 🧠✨ Setup complete! 🎉")
            await show_main_menu(update)
        elif state == "wait_session_id":
            await update.message.reply_text("⏳ *Session verify ho raha hai...* 🔄", parse_mode="Markdown")
            success, msg = login_by_sessionid(uid, text)
            update_user(uid, {"state": "idle"})
            if success: await update.message.reply_text(f"✅ *{msg}*\n\nAccount connect! ✨", parse_mode="Markdown")
            else: await update.message.reply_text(f"❌ Invalid: {msg}")
        elif state == "chat_mode" or user.get("privacy_accepted"):
            await asyncio.sleep(random.uniform(1.5, 3.0))
            reply = await get_ai_reply(text, user)
            await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"⚠️ ERROR: {e}")

# ==========================================
# 6. NEW IG AUTOMATION COMMANDS (The Core Features)
# ==========================================
async def cmd_check_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-accept follow requests and send emotional DM."""
    uid = update.effective_user.id
    await update.message.reply_text("🔍 *Checking pending follow requests...* 🔄", parse_mode="Markdown")
    
    cl = get_ig_client(uid)
    if not cl: return await update.message.reply_text("❌ Pehle Instagram login karo!")

    try:
        pending = cl.pending_follow_requests()
        if not pending:
            return await update.message.reply_text("✅ Koi pending request nahi hai! 😊")

        accepted = 0
        for req in pending:
            # Accept request
            cl.approve_pending_follow_requests([req.pk])
            # Send Emotional DM
            cl.direct_send(MSG_FOLLOW_ACCEPT, user_ids=[req.pk])
            accepted += 1
            await asyncio.sleep(random.uniform(2.0, 4.0)) # Human delay

        await update.message.reply_text(f"✅ *Done!* {accepted} requests accept ki aur emotional DM bhej diya. 🥀", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:150]}")

async def cmd_check_dms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-reply to unread DMs with emotional message."""
    uid = update.effective_user.id
    await update.message.reply_text("💬 *Checking unread DMs...* 🔄", parse_mode="Markdown")
    
    cl = get_ig_client(uid)
    if not cl: return await update.message.reply_text("❌ Pehle Instagram login karo!")

    try:
        inbox = cl.direct_inbox()
        replied = 0
        for thread in inbox.get('threads', []):
            if not thread.get('is_read'):
                cl.direct_send(MSG_DM_REPLY, thread_id=thread['thread_id'])
                replied += 1
                await asyncio.sleep(random.uniform(2.0, 4.0))
        
        await update.message.reply_text(f"✅ *Done!* {replied} DMs ka emotional reply bhej diya. 🥺", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:150]}")

async def cmd_auto_react(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-like recent reels/posts."""
    uid = update.effective_user.id
    await update.message.reply_text("❤️ *Auto-reacting to recent reels...* ", parse_mode="Markdown")
    
    cl = get_ig_client(uid)
    if not cl: return await update.message.reply_text("❌ Pehle Instagram login karo!")

    try:
        feed = cl.user_feed(cl.user_id, amount=5) # Last 5 posts/reels
        liked = 0
        for item in feed:
            if not item.has_liked:
                cl.media_like(item.pk)
                liked += 1
                await asyncio.sleep(random.uniform(3.0, 6.0)) # Safe delay
        
        await update.message.reply_text(f"✅ *Done!* {liked} recent posts/reels ko like kar diya. 🔥", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:150]}")

async def handle_proxy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1: return await update.message.reply_text("Usage: /proxy http://user:pass@ip:port")
    update_user(update.effective_user.id, {"proxy_url": context.args[0]})
    await update.message.reply_text("✅ Proxy save! 🌍")

async def handle_broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TG_ID: return
    if not context.args: return await update.message.reply_text("Usage: /broadcast <message>")
    msg = " ".join(context.args)
    users = get_all_users()
    sent = 0
    for u_id in users:
        try:
            await ptb.bot.send_message(u_id, msg)
            sent += 1
            await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_text(f"📢 Sent to {sent} users! ✅")

def register_handlers(application):
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("proxy", handle_proxy_cmd))
    application.add_handler(CommandHandler("broadcast", handle_broadcast_cmd))
    
    # New IG Automation Commands
    application.add_handler(CommandHandler("check_ig_requests", cmd_check_requests))
    application.add_handler(CommandHandler("check_ig_dms", cmd_check_dms))
    application.add_handler(CommandHandler("auto_react", cmd_auto_react))
    
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_private_text))

register_handlers(ptb)

# ==========================================
# 7. FASTAPI WEBHOOK
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
