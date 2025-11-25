import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import time
import google.generativeai as genai
from datetime import datetime
from duckduckgo_search import DDGS
import os

# ==================== 1. ตั้งค่าระบบ (ใส่ Key ของคุณ) ====================
# ถ้าคุณรันในคอมตัวเอง ให้ใส่ Key ตรงๆ ในเครื่องหมาย '' ได้เลย
# แต่ถ้ารันบน GitHub Actions ให้ใช้ os.getenv เหมือนเดิม
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'ใส่_TOKEN_ของคุณ_ถ้า_รันในคอม')
CHAT_ID = os.getenv('CHAT_ID', 'ใส่_CHAT_ID_ของคุณ_ถ้า_รันในคอม')
GENAI_API_KEY = os.getenv('GENAI_API_KEY', 'ใส่_GEMINI_KEY_ของคุณ_ถ้า_รันในคอม')

SHEET_NAME = 'Flood_Rescue_Data'
CREDS_FILE = 'credentials.json'

# ==================== 2. ฟังก์ชันระบบ ====================
genai.configure(api_key=GENAI_API_KEY)

def get_sheet():
    """เชื่อมต่อ Google Sheet"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

def send_alert(msg):
    """ส่งแจ้งเตือนเข้า Telegram"""
    print(f"Sending via Telegram: {msg}") # Print ใน Console ด้วย
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Error: {e}")

def search_flood_posts():
    """ค้นหาโพสต์ (ปรับ Keyword ให้กว้างขึ้นเพื่อ Test ระบบ)"""
    results = []
    
    # Keyword แบบกว้าง (เอา range:1d ออกก่อนเพื่อเช็คว่าดึงข้อมูลได้ไหม)
    keywords = [
        'site:twitter.com "น้ำท่วม" "ช่วยด้วย"',
        'site:facebook.com "น้ำท่วม" "ช่วยเหลือ"',
        'ข่าวน้ำท่วม ภาคใต้ ล่าสุด', # ลองดึงข่าวด้วย
        'ขอความช่วยเหลือ น้ำท่วม'
    ]

    print("🔍 Searching...")
    with DDGS() as ddgs:
        for query in keywords:
            try:
                # ลองดึงสัก 3-5 รายการต่อคำค้นหา
                search_res = ddgs.text(query, region='th-th', max_results=5)
                if search_res:
                    for item in search_res:
                        results.append({
                            "id": item['href'],
                            "text": f"{item['title']} : {item['body']}",
                            "url": item['href']
                        })
                time.sleep(1) 
            except Exception as e:
                print(f"⚠️ Search Error ({query}): {e}")
                
    return results

def analyze_with_ai(text):
    """ใช้ Gemini แยกแยะข้อมูล"""
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    Analyze this text related to floods in Thailand.
    Text: "{text}"
    
    1. Is this related to a rescue request OR a flood situation report? (True/False)
    2. Extract Location, Contact Number, and Needs.
    
    Return JSON only:
    {{
        "is_relevant": true,
        "location": "string or null",
        "contact": "string or null",
        "needs": "string or null"
    }}
    """
    try:
        response = model.generate_content(prompt)
        clean_json = response.text.replace('```json', '').replace('```', '')
        return eval(clean_json)
    except:
        return None

# ==================== 3. การทำงานหลัก (Main Loop Debug Mode) ====================
def run_bot():
    try:
        # 1. แจ้งเตือนเริ่มทำงาน
        send_alert("🚀 เริ่มต้นกระบวนการค้นหา (Debug Mode)...")
        
        sheet = get_sheet()
        existing_ids = sheet.col_values(1) 
        
        posts = search_flood_posts()
        
        # 2. แจ้งจำนวนที่เจอ
        send_alert(f"🔎 ค้นหาเจอทั้งหมด: {len(posts)} รายการ")
        
        if len(posts) == 0:
            send_alert("⚠️ ไม่พบข้อมูลเลย (DuckDuckGo อาจหาไม่เจอ หรือไม่มีโพสต์ใหม่)")
            return

        count_new = 0
        for post in posts:
            if post['id'] in existing_ids:
                continue # ข้าม

            # ส่งไปให้ AI อ่าน
            analysis = analyze_with_ai(post['text'])

            if analysis and analysis.get('is_relevant'):
                count_new += 1
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                loc = analysis.get('location') or "-"
                con = analysis.get('contact') or "-"
                need = analysis.get('needs') or "-"
                
                # บันทึก
                sheet.append_row([post['id'], timestamp, post['text'], loc, con, need, "New"])
                
                # แจ้งเตือน
                msg = (
                    f"🌊 **พบข้อมูลน้ำท่วม**\n"
                    f"📍 **ที่อยู่:** {loc}\n"
                    f"🗣 **รายละเอียด:** {need}\n"
                    f"🔗 **Link:** [ต้นทาง]({post['url']})"
                )
                send_alert(msg)
                print(f"✅ Sent alert for: {post['url']}")
                time.sleep(1)
            else:
                print(f"❌ AI บอกว่าไม่เกี่ยว: {post['url']}")
        
        send_alert(f"✅ จบการทำงานรอบนี้ เพิ่มข้อมูลใหม่ {count_new} รายการ")
                
    except Exception as e:
        send_alert(f"❌ System Error: {str(e)}")
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    run_bot()
