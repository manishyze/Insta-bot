import asyncio, random, logging
from datetime import datetime
from supabase import create_client
from instagrapi import Client as IGClient
from cryptography.fernet import Fernet

# ==========================================
# 1. CONFIG & DATABASE
# ==========================================
SUPABASE_URL = "https://krkychjmledoaepyeyhw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtya3ljaGptbGVkb2FlcHlleWh3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYyNjcyNTcsImV4cCI6MjEwMTg0MzI1N30.VkMK6-ghUnlFj2n51JTMJE9KQeE55IrH8CjBQR4XgcA"
FERNET_KEY = b'z9X8y7W6v5U4t3S2r1Q0p9O8n7M6l5K4j3I2h1G0f9E=' 
cipher = Fernet(FERNET_KEY)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
logging.basicConfig(level=logging.INFO)

# Emotional Messages
MSG_FOLLOW_ACCEPT = "Hey... thanks for following. Sach kahun toh main khud ko kaafi lost feel karta hu aajkal. Agar koi kaam hai toh bata dena. Thanks for being here. 🥀"
MSG_DM_REPLY = "Hey... kaise ho? Sach bataun toh main thoda akela feel kar raha hu aajkal. Tum sunaao, sab theek? 🥺"

# ==========================================
# 2. DYNAMIC SLEEP LOGIC (Tumhara Master Logic)
# ==========================================
current_sleep_time = random.uniform(2, 5)
MAX_SLEEP = 100

def get_dynamic_sleep():
    global current_sleep_time
    # Har baar 2 se 5 second badhao
    current_sleep_time += random.uniform(2, 5)
    # Agar 100 second cross kar gaya, toh wapas 2-5 par reset karo
    if current_sleep_time >= MAX_SLEEP:
        current_sleep_time = random.uniform(2, 5)
        logging.info("🔄 Sleep timer reset to human baseline!")
    return current_sleep_time

# ==========================================
# 3. CALENDAR & BIO LOGIC (15th August etc.)
# ==========================================
def get_festival_bio():
    today = datetime.now()
    # 15 August - Independence Day
    if today.month == 8 and today.day == 15:
        return "Happy Independence Day! 🇳 Jai Hind 🇮"
    # 26 January - Republic Day
    if today.month == 1 and today.day == 26:
        return "Jai Hind! Happy Republic Day 🇮"
    # 1 January - New Year
    if today.month == 1 and today.day == 1:
        return "Happy New Year! 🎉✨"
    return None # Normal days me bio change nahi karna

# ==========================================
# 4. CORE AUTOMATION TASKS
# ==========================================
async def process_user_account(user_data):
    """Runs all tasks for a single logged-in user."""
    cl = IGClient()
    try:
        # Load session
        cl.load_settings(user_data["ig_settings"])
        cl.login(user_data["ig_user"], cipher.decrypt(user_data["ig_pass_enc"].encode()).decode('utf-8'))
        logging.info(f"✅ Logged in as {user_data['ig_user']}")

        # --- TASK 1: Auto Accept Requests & DM ---
        pending = cl.pending_follow_requests()
        for req in pending:
            cl.approve_pending_follow_requests([req.pk])
            cl.direct_send(MSG_FOLLOW_ACCEPT, user_ids=[req.pk])
            logging.info(f"Accepted & DM'd {req.username}")
            await asyncio.sleep(get_dynamic_sleep())

        # --- TASK 2: Auto Reply to Unread DMs ---
        inbox = cl.direct_inbox()
        for thread in inbox.get('threads', []):
            if not thread.get('is_read'):
                cl.direct_send(MSG_DM_REPLY, thread_id=thread['thread_id'])
                logging.info(f"Replied to DM thread {thread['thread_id']}")
                await asyncio.sleep(get_dynamic_sleep())

        # --- TASK 3: Auto Like Recent Posts ---
        feed = cl.user_feed(cl.user_id, amount=3)
        for item in feed:
            if not item.has_liked:
                cl.media_like(item.pk)
                logging.info(f"Liked post {item.pk}")
                await asyncio.sleep(get_dynamic_sleep())

        # --- TASK 4: Calendar Bio Change ---
        festival_bio = get_festival_bio()
        if festival_bio:
            current_bio = cl.get_user_info(cl.user_id).biography
            if festival_bio not in current_bio:
                cl.set_account_bio(festival_bio)
                logging.info(f"Bio changed to: {festival_bio}")

    except Exception as e:
        logging.error(f"Error processing {user_data['ig_user']}: {e}")

# ==========================================
# 5. THE 24/7 INFINITE LOOP
# ==========================================
async def main_loop():
    logging.info("🚀 InstaPilot 24/7 Worker Started...")
    while True:
        try:
            # Fetch all users who have logged in via Session ID
            res = supabase.table("users").select("*").eq("ig_pass_enc", "SESSION_LOGIN").execute()
            
            if not res.data:
                logging.info("😴 No active sessions found. Sleeping...")
            else:
                logging.info(f"🔍 Checking {len(res.data)} active accounts...")
                for user in res.data:
                    await process_user_account(user)
                    # Wait between different users
                    await asyncio.sleep(get_dynamic_sleep())

        except Exception as e:
            logging.error(f"Main loop crashed: {e}")
        
        # The Master Sleep Logic
        sleep_time = get_dynamic_sleep()
        logging.info(f"💤 Entering Sleep Mode for {sleep_time:.2f} seconds...")
        await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    asyncio.run(main_loop())
