# database.py
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_note(user_id, note_text):
    try:
        supabase.table("notes").insert({"user_id": user_id, "note": note_text}).execute()
        return True
    except:
        return False
      
