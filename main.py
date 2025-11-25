import os
import time
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
from duckduckgo_search import DDGS
from datetime import datetime, timedelta  # <--- เพิ่ม timedelta

# ================= CONFIGURATION =================
# ดึงค่าจาก GitHub Secrets
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
GENAI_API_KEY = os.getenv('GENAI_API_KEY')
SHEET_NAME = 'Flood_Rescue_Data'
CREDS_FILE = 'credentials.json'

# ตั้งค่า AI
if GENAI_API_KEY:
    genai.configure(api_key=GENAI_API_KEY)

# ================= FUNCTIONS =================

def send_telegram(message):
    """ฟังก์ชันส่งข้อความเข้า Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ ส่ง Telegram สำเร็จ")
        else:
            print(f"❌ ส่ง Telegram พลาด: {response.text}")
    except Exception as e:
        print(f"❌ Error send_telegram: {e}")

def get_sheet():
    """เชื่อมต่อ Google Sheet"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).sheet1
    except Exception as e:
        print(f"❌ เชื่อมต่อ Google Sheet ไม่ได้: {e}")
        return None

def search_social_media():
    """ค้นหาโพสต์ด้วย DuckDuckGo"""
    print("🔍 กำลังสแกนหาข่าว...")
    results = []
    
    # Keyword ค้นหา (ลองปรับให้กว้างขึ้นเพื่อทดสอบการเจอข้อมูล)
    keywords = [
        'site:facebook.com "น้ำท่วม" "ช่วยด้วย" range:1d',
        'site:twitter.com "น้ำท่วม" "ช่วยด้วย" range:1d',
        '"น้ำท่วม" "ขอความช่วยเหลือ" "ติดอยู่" range:1d' 
    ]

    try:
        with DDGS() as ddgs:
            for query in keywords:
                print(f"   ...ค้นหาคีย์เวิร์ด: {query}")
                # max_results=5 เพื่อความเร็ว
                search_res = ddgs.text(query, region='wt-wt', max_results=5) 
                
                if search_res:
                    for item in search_res:
                        results.append({
                            "id": item['href'],
                            "text": f"{item['title']} : {item['body']}",
                            "url": item['href']
                        })
                time.sleep(1) # พักหายใจกันโดนบล็อก
    except Exception as e:
        print(f"⚠️ ค้นหาล้มเหลว (อาจโดน Rate Limit): {e}")
        
    print(f"📥 เจอทั้งหมด: {len(results)} โพสต์")
    return results

def analyze_with_ai(text):
    """วิเคราะห์ด้วย Gemini"""
    if not GENAI_API_KEY:
        print("⚠️ ไม่พบ GENAI_API_KEY ข้ามการวิเคราะห์")
        return None

    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    Analyze this text related to flood rescue.
    Text: "{text}"
    
    1. Is this a Request for Help? (YES/NO) - Ignore news, donations, or general complaints.
    2. Extract: Location, Contact, Needs.
    
    Return JSON only:
    {{
        "is_rescue": true/false,
        "location": "...",
        "contact": "...",
        "needs": "..."
    }}
    """
    try:
        response = model.generate_content(prompt)
        # Clean Markdown formatting
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        return eval(clean_json)
    except Exception as e:
        print(f"⚠️ AI Error: {e}")
        return None

# ================= MAIN LOOP =================

# ... (ส่วน Import ด้านบน อย่าลืมเพิ่ม timedelta นะครับ) ...

def main():
    print("🚀 เริ่มต้นระบบ Flood Rescue Bot V2.1 (GMT+7)")
    
    # คำนวณเวลาไทย
    thai_time = datetime.utcnow() + timedelta(hours=7)
    
    # 1. TEST CONNECTION
    print("🧪 กำลังส่งข้อความทดสอบระบบ...")
    send_telegram(f"✅ **SYSTEM CHECK:** บอททำงาน ณ เวลา {thai_time.strftime('%H:%M:%S')} (เวลาไทย)")

    # 2. เตรียม Google Sheet
    sheet = get_sheet()
    existing_ids = []
    if sheet:
        try:
            existing_ids = sheet.col_values(1)
            print(f"📚 ฐานข้อมูลเดิมมี: {len(existing_ids)} รายการ")
        except:
            print("⚠️ อ่าน Sheet ไม่ได้")

    # 3. เริ่มค้นหา
    posts = search_social_media()

    # 4. วนลูปวิเคราะห์
    for post in posts:
        if post['id'] in existing_ids:
            continue
            
        print(f"🤖 AI กำลังอ่าน: {post['url']}")
        analysis = analyze_with_ai(post['text'])

        if analysis and analysis.get('is_rescue'):
            print(f"🚨 >> เจอเคสช่วยเหลือ! ที่: {analysis.get('location')}")
            
            loc = analysis.get('location') or "ไม่ระบุ"
            con = analysis.get('contact') or "-"
            need = analysis.get('needs') or "-"
            
            # ใช้เวลาไทยตรงนี้
            timestamp = (datetime.utcnow() + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")

            # ส่ง Alert
            msg = (
                f"🆘 **NEW RESCUE CASE**\n"
                f"📍 **พิกัด:** {loc}\n"
                f"🗣 **ต้องการ:** {need}\n"
                f"📞 **ติดต่อ:** {con}\n"
                f"🔗 **ต้นทาง:** [คลิกดูโพสต์]({post['url']})"
            )
            send_telegram(msg)
            
            # บันทึกลง Sheet
            if sheet:
                try:
                    sheet.append_row([post['id'], timestamp, post['text'], loc, con, need, "Sent"])
                    print("💾 บันทึกลง Sheet เรียบร้อย")
                except Exception as e:
                    print(f"❌ บันทึก Sheet ไม่ได้: {e}")
            
            time.sleep(1)
        else:
            print("   -> ไม่ใช่เคสช่วยเหลือ (ข้าม)")

    print("🏁 จบการทำงานรอบนี้")

if __name__ == "__main__":
    main()

