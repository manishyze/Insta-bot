import os, hashlib, secrets, requests
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from supabase import create_client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ChatMemberHandler, filters)
from telegram.constants import ChatMemberStatus

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TG_ID = int(os.getenv("ADMIN_TG_ID", "0"))
ADMIN_PASS = os.getenv("ADMIN_PASS", "change_me")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
IG_API_BASE = "https://graph.facebook.com/v21.0"
CONTACTS = ["@manish.yze", "@allowed"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
app = FastAPI()
ptb = Application.builder().token(BOT_TOKEN).build()
is_initialized = False

def h(pw): return hashlib.pbkdf2_hmac("sha256", pw.encode(), b"salt", 120000).hex()

def is_prem(uid):
    res = supabase.table("users").select("premium_until").eq("tg_id", uid).execute()
    if res.data and res.data[0]["premium_until"]:
        return datetime.fromisoformat(res.data[0]["premium_until"]) > datetime.now()
    return False

def ai_reply(text, system):
    if LLM_API_KEY:
        try:
            r = requests.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={"model": LLM_MODEL, "messages": [{"role":"system","content":system}, {"role":"user","content":text}]}, timeout=30)
            return r.json()["choices"][0]["message"]["content"].strip()
        except: pass
    t = text.lower()
    if "price" in t: return "Admin se contact karo."
    if "hi" in t or "hello" in t: return "Hello! Batao kaise madad karun?"
    return "Samajh gaya. Thoda detail me batao?"

def ig_post_image(ig_user_id, access_token, image_url, caption):
    r = requests.post(f"{IG_API_BASE}/{ig_user_id}/media", data={"image_url": image_url, "caption": caption, "access_token": access_token}, timeout=60)
    r.raise_for_status()
    cid = r.json().get("id")
    r2 = requests.post(f"{IG_API_BASE}/{ig_user_id}/media_publish", data={"creation_id": cid, "access_token": access_token}, timeout=60)
    r2.raise_for_status()
    return r2.json()

async def start_cmd(u, ctx):
    uid = u.effective_user.id
    res = supabase.table("users").select("privacy").eq("tg_id", uid).execute()
    if not res.data:
        supabase.table("users").insert({"tg_id": uid, "premium_until": (datetime.now() + timedelta(days=7)).isoformat()}).execute()
        res = supabase.table("users").select("privacy").eq("tg_id", uid).execute()
    if not res.data[0]["privacy"]:
        kb = [[InlineKeyboardButton("Accept", callback_data="priv_yes"), InlineKeyboardButton("Decline", callback_data="priv_no")]]
        await u.effective_message.reply_text("Privacy Policy: Bot sirf ID aur dashboard state store karta hai.", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await show_dashboard(u)

async def show_dashboard(u):
    uid = u.effective_user.id
    res = supabase.table("users").select("username, premium_until").eq("tg_id", uid).execute()
    un = res.data[0]["username"] if res.data else "not set"
    plan = "PREMIUM" if is_prem(uid) else "Free Trial"
    txt = f"Dashboard\nLogin: {un}\nPlan: {plan}"
    kb = [[InlineKeyboardButton("Login", callback_data="login")],
          [InlineKeyboardButton("Status", callback_data="status")],
          [InlineKeyboardButton("Premium", callback_data="premium")],
          [InlineKeyboardButton("Group AI", callback_data="grouphelp")],
          [InlineKeyboardButton("IG Post", callback_data="ighelp")]]
    await u.effective_message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb))

async def admin_cmd(u, ctx):
    if u.effective_user.id == ADMIN_TG_ID and ctx.args and ctx.args[0] == ADMIN_PASS:
        days = int(ctx.args[1]) if len(ctx.args) > 1 else 30
        code = secrets.token_urlsafe(5).upper()
        supabase.table("codes").insert({"code": code, "days": days}).execute()
        await u.message.reply_text(f"Code: {code} ({days} days)")
    else:
        await u.message.reply_text("Access Denied. Use: /admin pass 30")

async def save_ig_cmd(u, ctx):
    uid = u.effective_user.id
    if not is_prem(uid): return await u.message.reply_text("Pehle premium lo.")
    if len(ctx.args) < 2: return await u.message.reply_text("Use: /save_ig <ig_user_id> <token>")
    supabase.table("ig_accounts").upsert({"tg_id": uid, "ig_user_id": ctx.args[0], "access_token": ctx.args[1], "updated_at": datetime.now().isoformat()}).execute()
    await u.message.reply_text("IG account saved.")

async def post_cmd(u, ctx):
    uid = u.effective_user.id
    if not is_prem(uid): return await u.message.reply_text("Pehle premium lo.")
    if not ctx.args: return await u.message.reply_text("Use: /post <image_url> <caption>")
    acc = supabase.table("ig_accounts").select("*").eq("tg_id", uid).execute().data
    if not acc: return await u.message.reply_text("Pehle /save_ig karo.")
    try:
        res = ig_post_image(acc[0]["ig_user_id"], acc[0]["access_token"], ctx.args[0], " ".join(ctx.args[1:]))
        await u.message.reply_text(f"Published! media_id: {res.get('id')}")
    except Exception as e:
        await u.message.reply_text(f"Fail: {e}")

async def cb_handler(u, ctx):
    q = u.callback_query; uid = u.from_user.id
    if q.data == "priv_yes":
        supabase.table("users").update({"privacy": True}).eq("tg_id", uid).execute()
        await q.answer("Accepted"); await show_dashboard(u)
    elif q.data == "priv_no": await q.answer("Accept zaroori hai.")
    elif q.data == "login":
        supabase.table("users").update({"login_state": "wait_user"}).eq("tg_id", uid).execute()
        await q.answer(); await q.edit_message_text("Dashboard username likho:")
    elif q.data == "premium":
        supabase.table("users").update({"login_state": "wait_code"}).eq("tg_id", uid).execute()
        await q.answer()
        await q.edit_message_text("Premium contacts:\n" + "\n".join(CONTACTS) + "\n\nCode paste karo:")
    elif q.data == "status": await q.answer(); await q.edit_message_text("System: Online (24/7)")
    elif q.data == "grouphelp": await q.answer(); await q.edit_message_text("Bot ko group me add karo. AI onboarding start karega.")
    elif q.data == "ighelp": await q.answer(); await q.edit_message_text("IG Post:\n1. /save_ig <id> <token>\n2. /post <url> <caption>")

async def private_text_handler(u, ctx):
    uid = u.effective_user.id
    text = u.message.text.strip()
    res = supabase.table("users").select("login_state").eq("tg_id", uid).execute().data
    state = res[0]["login_state"] if res else ""
    if state == "wait_user":
        supabase.table("users").update({"username": text, "login_state": "wait_pass"}).eq("tg_id", uid).execute()
        await u.message.reply_text("Password likho:")
    elif state == "wait_pass":
        supabase.table("users").update({"pass_hash": h(text), "login_state": ""}).eq("tg_id", uid).execute()
        await u.message.reply_text("Dashboard login save. /start")
    elif state == "wait_code":
        supabase.table("users").update({"login_state": ""}).eq("tg_id", uid).execute()
        code_res = supabase.table("codes").select("*").eq("code", text.upper()).execute().data
        if not code_res: await u.message.reply_text("Galat code.")
        elif code_res[0]["used_by"]: await u.message.reply_text("Code use ho chuka.")
        else:
            days = code_res[0]["days"]
            new_date = (datetime.now() + timedelta(days=days)).isoformat()
            supabase.table("users").update({"premium_until": new_date}).eq("tg_id", uid).execute()
            supabase.table("codes").update({"used_by": uid}).eq("code", text.upper()).execute()
            await u.message.reply_text(f"Premium active till {new_date[:10]}")

async def group_member_update(u, ctx):
    cms = u.my_chat_member
    if cms.chat.type in ("group", "supergroup") and cms.new_chat_member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR):
        if not is_prem(cms.from_user.id):
            await cms.chat.send_text("Group AI requires Premium.")
            return
        supabase.table("groups").insert({"chat_id": cms.chat.id, "title": cms.chat.title, "owner_id": cms.from_user.id}).execute()
        await cms.chat.send_text("Q1: Is group ka topic kya hai? (Reply me likho)")

async def group_text_handler(u, ctx):
    gid = u.effective_chat.id
    res = supabase.table("groups").select("*").eq("chat_id", gid).execute().data
    if not res: return
    g = res[0]
    if g["stage"] == 1:
        supabase.table("groups").update({"stage": 2}).eq("chat_id", gid).execute()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Friendly", callback_data=f"tone:{gid}:friendly"), InlineKeyboardButton("Pro", callback_data=f"tone:{gid}:pro")]])
        await u.message.reply_text("Q2: Tone kaisa ho?", reply_markup=kb)
    elif g["active"]:
        m = u.message.text or ""
        if g["auto_mode"] == "mention" and f"@{ctx.bot.username}" not in m and not (u.message.reply_to_message and u.message.reply_to_message.from_user.id == ctx.bot.id):
            return
        await u.effective_chat.send_chat_action("typing")
        await u.message.reply_text(ai_reply(m, f"Tone: {g['tone']}. Group: {g['title']}. Be helpful."))

async def group_cb_handler(u, ctx):
    q = u.callback_query
    if q.data.startswith("tone:"):
        _, gid, tone = q.data.split(":", 2)
        supabase.table("groups").update({"tone": tone, "stage": 3}).eq("chat_id", int(gid)).execute()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Mention only", callback_data=f"mode:{gid}:mention"), InlineKeyboardButton("All msgs", callback_data=f"mode:{gid}:all")]])
        await q.edit_message_text("Q3: Kab reply kare?", reply_markup=kb)
    elif q.data.startswith("mode:"):
        _, gid, mode = q.data.split(":", 2)
        supabase.table("groups").update({"auto_mode": mode, "stage": 4, "active": True}).eq("chat_id", int(gid)).execute()
        await q.edit_message_text("Group AI Active!")

ptb.add_handler(CommandHandler("start", start_cmd))
ptb.add_handler(CommandHandler("admin", admin_cmd))
ptb.add_handler(CommandHandler("save_ig", save_ig_cmd))
ptb.add_handler(CommandHandler("post", post_cmd))
ptb.add_handler(ChatMemberHandler(group_member_update, ChatMemberHandler.MY_CHAT_MEMBER))
ptb.add_handler(CallbackQueryHandler(cb_handler, pattern="^(priv_|login|status|premium|grouphelp|ighelp)"))
ptb.add_handler(CallbackQueryHandler(group_cb_handler, pattern="^(tone|mode):"))
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, private_text_handler))
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, group_text_handler))

@app.post("/api/webhook")
async def webhook(request: Request):
    global is_initialized
    if not is_initialized:
        await ptb.initialize()
        is_initialized = True
    data = await request.json()
    update = Update.de_json(data)
    await ptb.process_update(update)
    return {"status": "ok"}
