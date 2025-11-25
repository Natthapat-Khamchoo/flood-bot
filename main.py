import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import time
import google.generativeai as genai
from datetime import datetime
from duckduckgo_search import DDGS

# --- รับค่าจาก GitHub Secrets ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
GENAI_API_KEY = os.getenv('GENAI_API_KEY')
SHEET_NAME = 'Flood_Rescue_Data'
CREDS_FILE = 'credentials.json' # ไฟล์นี้จะถูกสร้างตอนรันบน Server

genai.configure(api_key=GENAI_API_KEY)

def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

def send_alert(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def search_posts():
    print("🔍 Scanning Social Media...")
    results = []
    # ใช้ Dorks ค้นหา 1 วันล่าสุด (range:1d)
    keywords = [
        'site:facebook.com "น้ำท่วม" "ช่วยด้วย" range:1d',
        'site:twitter.com "น้ำท่วมภาคใต้" "ช่วยด้วย" range:1d',
        'site:instagram.com "น้ำท่วม" "ช่วยด้วย" range:1d'
    ]
    with DDGS() as ddgs:
        for query in keywords:
            try:
                res = ddgs.text(query, region='th-th', max_results=5)
                if res:
                    for item in res:
                        results.append({
                            "id": item['href'],
                            "text": f"{item['title']} : {item['body']}",
                            "url": item['href']
                        })
                time.sleep(1)
            except:
                pass
    return results

def analyze_ai(text):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    Analyze text: "{text}"
    Is this a real flood rescue request? Extract Location, Contact, Needs.
    Return JSON only: {{"is_rescue": bool, "location": str, "contact": str, "needs": str}}
    """
    try:
        res = model.generate_content(prompt)
        return eval(res.text.replace('```json','').replace('```',''))
    except:
        return None

def main():
    try:
        sheet = get_sheet()
        existing = sheet.col_values(1)
        posts = search_posts()
        
        for post in posts:
            if post['id'] in existing: continue
            
            data = analyze_ai(post['text'])
            if data and data.get('is_rescue'):
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row = [post['id'], timestamp, post['text'], data.get('location'), data.get('contact'), data.get('needs'), "New"]
                sheet.append_row(row)
                
                msg = f"🆘 **NEW ALERT**\n📍 {data.get('location')}\n🗣 {data.get('needs')}\n🔗 {post['url']}"
                send_alert(msg)
                time.sleep(1)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":

    main()

    # ... (โค้ดส่วนบนเหมือนเดิม)

def main():
    try:
        sheet = get_sheet()
        
        # =========== โซนทดสอบ (TEST ZONE) ===========
        print("🧪 กำลังทดสอบระบบ...")
        # 1. ลองส่งเข้า Telegram เลย
        send_alert("✅ **SYSTEM CHECK:** บอทเริ่มทำงานแล้วครับ (Test Message)")
        
        # 2. ลองยัดข้อมูลจำลอง 1 เคส (ไม่ต้องรอ Search เจอ)
        dummy_text = "ทดสอบระบบ: ช่วยด้วย น้ำท่วมบ้านเลขที่ 999 หาดใหญ่ ติดต่อ 081-111-2222"
        print("🤖 กำลังทดสอบ AI...")
        data = analyze_ai(dummy_text) # ให้ AI ลองวิเคราะห์ข้อความปลอมนี้
        
        if data:
            print(f"ผลการวิเคราะห์ AI: {data}")
            # ลองบันทึกลง Sheet
            sheet.append_row(["TEST-001", "2025-11-25", dummy_text, "Test Loc", "Test Contact", "Test Needs", "TEST"])
            print("📝 บันทึกลง Google Sheet สำเร็จ!")
        # ============================================

        # ... (โค้ด Search ของเดิมอยู่ข้างล่างนี้)
        existing = sheet.col_values(1)
        # ...
