import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import time
import google.generativeai as genai
from datetime import datetime
from duckduckgo_search import DDGS
import os

# ==================== SETTINGS ====================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'ใส่_TOKEN_ของคุณ_ถ้า_รันในคอม')
CHAT_ID = os.getenv('CHAT_ID', 'ใส่_CHAT_ID_ของคุณ_ถ้า_รันในคอม')
GENAI_API_KEY = os.getenv('GENAI_API_KEY', 'ใส่_GEMINI_KEY_ของคุณ_ถ้า_รันในคอม')

SHEET_NAME = 'Flood_Rescue_Data'
CREDS_FILE = 'credentials.json'

genai.configure(api_key=GENAI_API_KEY)

# ==================== FUNCTIONS ====================
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

def send_alert(msg):
    # ฟังก์ชันส่งข้อความ Telegram แบบปลอดภัย (ไม่ Error ถ้ายิงรัว)
    print(f">> Sending: {msg}")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Error: {e}")

def search_flood_posts():
    # ค้นหาแบบกว้างสุดๆ เพื่อให้เจอข้อมูลแน่นอน
    results = []
    keywords = ['ข่าวน้ำท่วมภาคใต้', 'ช่วยด้วย น้ำท่วม'] # ใช้คำสั้นๆ เพื่อให้เจอชัวร์ๆ
    
    send_alert("🔍 ..กำลังกวาดข้อมูลจาก DuckDuckGo..")
    
    with DDGS() as ddgs:
        for query in keywords:
            try:
                # ดึงแค่ 3 อันพอ เพื่อไม่ให้แชทระเบิดตอนเทส
                search_res = ddgs.text(query, region='th-th', max_results=3) 
                if search_res:
                    for item in search_res:
                        results.append({
                            "id": item['href'],
                            "text": f"{item['title']} : {item['body']}",
                            "url": item['href']
                        })
            except Exception as e:
                print(f"Search Error: {e}")
    return results

def analyze_with_ai(text):
    # ปรับ Prompt ให้ "ยอมรับทุกอย่าง" (Accept All) เพื่อเทส Database
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    Analyze this text: "{text}"
    
    Task: Extract data related to floods.
    ALWAYS return "is_relevant": true for this test.
    
    Return JSON only:
    {{
        "is_relevant": true,
        "location": "Extract location or say 'General Area'",
        "contact": "Extract phone or say '-'",
        "needs": "Summarize topic briefly"
    }}
    """
    try:
        response = model.generate_content(prompt)
        clean_json = response.text.replace('```json', '').replace('```', '')
        return eval(clean_json)
    except:
        return None

# ==================== MAIN DEBUG LOOP ====================
def run_bot():
    send_alert("🛠 **STARTING EXTREME DEBUG MODE** 🛠")
    
    # 1. ทดสอบเขียน Google Sheet ก่อนเลย
    sheet = None
    try:
        sheet = get_sheet()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # เขียนบรรทัดทดสอบ
        sheet.append_row(["TEST_CONNECTION", timestamp, "System Check Write", "Test Loc", "-", "-", "DEBUG_ROW"])
        send_alert("✅ **Google Sheet Write Success!** (ตรวจสอบไฟล์ของคุณดูได้เลย)")
    except Exception as e:
        send_alert(f"❌ **Google Sheet Error:** เขียนไม่ได้!\nเหตุผล: `{str(e)}`")
        return # ถ้าเขียนไม่ได้ ให้จบโปรแกรมเลย

    # 2. เริ่มค้นหา
    existing_ids = sheet.col_values(1)
    posts = search_flood_posts()
    send_alert(f"🔎 เจอข้อมูลดิบ: {len(posts)} รายการ")

    if not posts:
        send_alert("⚠️ ไม่เจอข้อมูล (Search Engine อาจบล็อกชั่วคราว)")
        return

    # 3. ลูปดูข้อมูลทีละอัน
    for i, post in enumerate(posts):
        # ส่งข้อมูลดิบเข้าแชทให้คุณดูก่อน
        preview_msg = f"📄 **รายการที่ {i+1}**\nTitle: {post['text'][:100]}...\nLink: {post['url']}"
        send_alert(preview_msg)
        
        # เช็คซ้ำ
        if post['id'] in existing_ids:
            send_alert("⏭ ข้าม (มีใน Database แล้ว)")
            continue

        # ให้ AI อ่าน
        analysis = analyze_with_ai(post['text'])
        
        if analysis:
            # บันทึกจริง
            try:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row = [
                    post['id'], 
                    ts, 
                    post['text'][:200], # ตัดให้สั้นหน่อยกันรก
                    analysis.get('location'), 
                    analysis.get('contact'), 
                    analysis.get('needs'), 
                    "Analyzed"
                ]
                sheet.append_row(row)
                send_alert(f"💾 **Saved to Sheet!**\nLoc: {analysis.get('location')}")
            except Exception as e:
                send_alert(f"❌ Save Error: {e}")
        else:
            send_alert("❌ AI Failed to parse JSON")
            
        time.sleep(2) # พักหายใจหน่อย

    send_alert("🏁 **จบการทำงานรอบนี้**")

if __name__ == "__main__":
    run_bot()
