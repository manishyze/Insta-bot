# ai_handler.py
from groq import Groq
from config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)

def get_zex_response(prompt):
    messages = [
        {"role": "system", "content": "You are Zex, a loyal and strict AI assistant for Manish Boss. Always call him 'Manish Boss'. Be cool, smart, and futuristic."},
        {"role": "user", "content": prompt}
    ]
    response = client.chat.completions.create(model="llama3-70b-8192", messages=messages)
    return response.choices[0].message.content
  
