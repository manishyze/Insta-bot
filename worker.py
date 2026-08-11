import asyncio, random, logging
from datetime import datetime
from supabase import create_client
from instagrapi import Client as IGClient

SUPABASE_URL = "https://krkychjmledoaepyeyhw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtya3ljaGptbGVkb2FlcHlleWh3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYyNjcyNTcsImV4cCI6MjEwMTg0MzI1N30.VkMK6-ghUnlFj2n51JTMJE9KQeE55IrH8CjBQR4XgcA"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MSG_FOLLOW_ACCEPT = "Hey... thanks for following. Sach kahun toh main khud ko kaafi lost feel karta hu aajkal. Agar koi kaam hai toh bata dena. Thanks for being here. 🥀"
MSG_DM_REPLY = "Hey... kaise ho? Sach bataun toh main thoda akela feel kar raha hu aajkal. Tum sunaao, sab theek? 🥺"

current_sleep_time = random.uniform(2, 5)
def get_dynamic_sleep():
    global current_sleep_time
    current_sleep_time += random.uniform(2, 5)
    if current_sleep_time >= 100:
        current_sleep_time = random.uniform(2, 5)
        logging.info("🔄 Sleep timer reset to human baseline!")
    return current_sleep_time

def get_festival_bio():
    today = datetime.now()
    if today.month == 8 and today.day == 15: return "Happy Independence Day!  Jai Hind 🇮"
    if today.month == 1 and today.day == 26: return "Jai Hind! Happy Republic Day 🇮"
    if today.month == 1 and today.day == 1: return "Happy New Year! ✨"
    return None

async def process_user_account(user_data):
    cl = IGClient()
    try:
        logging.info(f"Attempting to load session for: {user_data['ig_user']}")
        cl.load_settings(user_data["ig_settings"])
        
        # FIX: Use the actual session ID saved in ig_pass_enc
        session_id = user_data["ig_pass_enc"]
        cl.login_by_sessionid(session_id)
        logging.info(f"✅ Successfully logged in as {user_data['ig_user']}")

        # 1. Auto Accept Requests & DM
        pending = cl.pending_follow_requests()
        if pending:
            logging.info(f"Found {len(pending)} pending requests.")
            for req in pending:
                cl.approve_pending_follow_requests([req.pk])
                cl.direct_send(MSG_FOLLOW_ACCEPT, user_ids=[req.pk])
                logging.info(f"✅ Accepted & DM'd: {req.username}")
                await asyncio.sleep(get_dynamic_sleep())
        else:
            logging.info("No pending follow requests.")

        # 2. Auto Reply to Unread DMs
        inbox = cl.direct_inbox()
        replied_count = 0
        for thread in inbox.get('threads', []):
            if not thread.get('is_read'):
                cl.direct_send(MSG_DM_REPLY, thread_id=thread['thread_id'])
                replied_count += 1
                logging.info(f"✅ Replied to unread DM thread: {thread['thread_id']}")
                await asyncio.sleep(get_dynamic_sleep())
        if replied_count == 0:
            logging.info("No unread DMs found.")

        # 3. Auto Like Recent Posts
        feed = cl.user_feed(cl.user_id, amount=3)
        liked_count = 0
        for item in feed:
            if not item.has_liked:
                cl.media_like(item.pk)
                liked_count += 1
                logging.info(f"❤️ Liked post: {item.pk}")
                await asyncio.sleep(get_dynamic_sleep())
        if liked_count == 0:
            logging.info("No new posts to like.")

        # 4. Auto View Stories (Increases Trust Score)
        try:
            following = cl.user_following(cl.user_id)
            story_count = 0
            for user_id in list(following.keys())[:5]: 
                try:
                    stories = cl.user_stories(user_id)
                    if stories:
                        for story in stories:
                            cl.story_seen([story.pk], [story.id])
                        story_count += 1
                        logging.info(f"👁️ Viewed stories of: {following[user_id]['username']}")
                        await asyncio.sleep(get_dynamic_sleep())
                except: pass
            if story_count == 0:
                logging.info("No new stories to view.")
        except Exception as e:
            logging.warning(f"Story viewing skipped: {e}")

        # 5. Calendar Bio Change
        festival_bio = get_festival_bio()
        if festival_bio:
            current_bio = cl.get_user_info(cl.user_id).biography
            if festival_bio not in current_bio:
                cl.set_account_bio(festival_bio)
                logging.info(f"🎉 Bio automatically changed to: {festival_bio}")

    except Exception as e:
        logging.error(f"❌ Error processing {user_data.get('ig_user', 'Unknown')}: {str(e)}")

async def main_loop():
    logging.info("🚀 InstaPilot 24/7 Worker Started...")
    while True:
        try:
            # Fetch users who have a valid session ID saved
            res = supabase.table("users").select("*").not_.is_("ig_pass_enc", "null").execute()
            
            active_users = [u for u in res.data if u.get("ig_pass_enc") and len(u.get("ig_pass_enc", "")) > 20]
            
            if not active_users:
                logging.info("😴 No active IG sessions found in database. Sleeping...")
            else:
                logging.info(f"🔍 Checking {len(active_users)} active accounts...")
                for user in active_users:
                    await process_user_account(user)
                    await asyncio.sleep(get_dynamic_sleep())
        except Exception as e:
            logging.error(f"Main loop crashed: {str(e)}")
        
        sleep_time = get_dynamic_sleep()
        logging.info(f"💤 Entering Sleep Mode for {sleep_time:.2f} seconds...")
        await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    asyncio.run(main_loop())
