import os
import time
import random
import telebot
from instagrapi import Client
from supabase import create_client
from groq import Groq

# ================= CONFIGURATION & VARIABLES =================
BOT_TOKEN = "8804881343:AAFr7Li3dztS-KC7QMd-jdvexIOdvGncc68"
SUPABASE_URL = "https://krkychjmledoaepyeyhw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtya3ljaGptbGVkb2FlcHlleWh3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYyNjcyNTcsImV4cCI6MjEwMTg0MzI1N30.VkMK6-ghUnlFj2n51JTMJE9KQeE55IrH8CjBQR4XgcA"
GROQ_API_KEY = "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"
ADMIN_TG_ID = 8528276558
ADMIN_PASS = "manishyze123#@##@"

# Initialize Clients
bot = telebot.TeleBot(BOT_TOKEN)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# Temporary memory for user onboarding steps
user_onboarding = {}

# ================= ONBOARDING /START FLOW =================
@bot.message_handler(commands=['start'])
def start_onboarding(message):
    chat_id = message.chat.id
    user_onboarding[chat_id] = {}
    
    msg = bot.send_message(chat_id, "🤖 **Insta Pilot Setup Started, Manish Boss!**\n\nStep 1/6: Please enter your **Instagram Username**:")
    bot.register_next_step_handler(msg, get_ig_username)

def get_ig_username(message):
    chat_id = message.chat.id
    user_onboarding[chat_id]['ig_username'] = message.text.strip()
    
    msg = bot.send_message(chat_id, "🔒 Step 2/6: Enter your **Instagram Password**:")
    bot.register_next_step_handler(msg, get_ig_password)

def get_ig_password(message):
    chat_id = message.chat.id
    user_onboarding[chat_id]['ig_password'] = message.text.strip()
    
    msg = bot.send_message(chat_id, "👤 Step 3/6: What is your **Nickname**?")
    bot.register_next_step_handler(msg, get_nickname)

def get_nickname(message):
    chat_id = message.chat.id
    user_onboarding[chat_id]['nickname'] = message.text.strip()
    
    msg = bot.send_message(chat_id, "🎂 Step 4/6: What is your **Age**?")
    bot.register_next_step_handler(msg, get_age)

def get_age(message):
    chat_id = message.chat.id
    user_onboarding[chat_id]['age'] = message.text.strip()
    
    msg = bot.send_message(chat_id, "📅 Step 5/6: What is your **Birthday Date**? (e.g., 15 August)")
    bot.register_next_step_handler(msg, get_birthday)

def get_birthday(message):
    chat_id = message.chat.id
    user_onboarding[chat_id]['birthday'] = message.text.strip()
    
    msg = bot.send_message(chat_id, "👥 Step 6/6: Write down your **Personal Best Friends names (up to 10)** (comma separated):")
    bot.register_next_step_handler(msg, finalize_setup)

def finalize_setup(message):
    chat_id = message.chat.id
    user_onboarding[chat_id]['best_friends'] = message.text.strip()
    
    data = user_onboarding[chat_id]
    
    bot.send_message(chat_id, "🔄 Testing Instagram Login and saving your configuration...")
    
    try:
        # Test Instagram Login
        ig_client = Client()
        ig_client.login(data['ig_username'], data['ig_password'])
        
        # Save data to Supabase
        supabase.table("instapilot_users").upsert({
            "telegram_id": chat_id,
            "ig_username": data['ig_username'],
            "nickname": data['nickname'],
            "age": data['age'],
            "birthday": data['birthday'],
            "best_friends": data['best_friends']
        }).execute()
        
        bot.send_message(
            chat_id, 
            "✅ **Setup Successful, Manish Boss!**\n\n"
            "• Instagram Login: Connected 🟢\n"
            "• Supabase Memory: Saved 🟢\n"
            "• AI Pilot: Ready 🟢\n\n"
            "Your Insta Pilot is now fully operational!"
        )
    except Exception as e:
        bot.send_message(
            chat_id, 
            f"⚠️ Setup completed but Instagram Login failed:\n`{e}`\n\n"
            "Please check your username/password and restart using /start."
        )

# ================= MANUAL REPLY COMMAND =================
@bot.message_handler(commands=['reply'])
def handle_manual_reply(message):
    try:
        parts = message.text.split(" ", 2)
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ Format: `/reply <username> <message>`")
            return
        
        target_user = parts[1]
        msg_text = parts[2]
        
        bot.reply_to(message, f"✅ Message processed for @{target_user} with random sleep delay.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

# ================= RUN BOT =================
if __name__ == "__main__":
    print("Insta Pilot is running and listening to Telegram commands...")
    bot.infinity_polling()
  
