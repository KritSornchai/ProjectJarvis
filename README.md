# ProjectJarvis - Personal LINE AI Agent 🤖

**ProjectJarvis** เป็น AI Agent ผู้ช่วยส่วนตัวอัจฉริยะที่เชื่อมต่อกับ **LINE Messaging API** และขับเคลื่อนด้วย **Google Gemini API** (Zero-Cost / 100% Free Tier Stack)

---

## ✨ ความสามารถหลัก (Features)

- 💬 **คุยส่วนตัว 1-on-1**: ตอบคำถาม วิเคราะห์ข้อมูล ให้คำปรึกษา พร้อมจำบริบทบทสนทนา (Conversation Memory)
- 👥 **รองรับ Group Chat**: ทำงานในกลุ่ม LINE โดยจะตอบเฉพาะเมื่อถูก Tag หรือ Mention เท่านั้น เช่น `@Jarvis ...` (ไม่รบกวนการคุยทั่วไป)
- ⚡ **Multi-Model Auto-Fallback**: รองรับการสลับโมเดลอัตโนมัติเมื่อโมเดลใดโมเดลหนึ่งชน Rate Limit หรือโควตา Free Tier เต็ม (ป้องกัน Error 429)
- ⏳ **Loading Animation**: แสดงสถานะ *"Jarvis กำลังพิมพ์..."* ใน LINE ระหว่าง AI กำลังประมวลผล
- 🔄 **Memory Management**: พิมพ์ `/reset` หรือ `รีเซ็ต` เพื่อล้างความจำบทสนทนาได้ทุกเมื่อ
- 💸 **100% Free**: ไม่เสียค่าบริการทั้ง LINE API, Gemini LLM และการทดสอบเซิร์ฟเวอร์

---

## 🛠️ Tech Stack

- **Language**: Python 3.9+
- **Web Framework**: [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn
- **AI Brain**: [Google GenAI SDK](https://github.com/googleapis/python-genai) (Gemini 2.5 Flash Lite & Fallbacks)
- **LINE Integration**: [LINE Bot SDK v3 for Python](https://github.com/line/line-bot-sdk-python)
- **Tunneling**: Ngrok / Cloudflare Tunnel

---

## 🚀 วิธีติดตั้งและใช้งาน (Quick Start)

### 1. โคลนและติดตั้ง Dependencies
```bash
git clone https://github.com/<your-username>/ProjectJarvis.git
cd ProjectJarvis

# สร้าง virtual environment
python3 -m venv .venv
source .venv/bin/activate

# ติดตั้งแพ็กเกจ
pip install --no-compile -r requirements.txt
```

### 2. ตั้งค่า Environment Variables
สร้างไฟล์ `.env` จาก `.env.example`:
```bash
cp .env.example .env
```
กำหนดค่าใน `.env`:
```env
LINE_CHANNEL_SECRET=your_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash-lite
```

### 3. รัน Server
```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 4. เปิด Public Tunnel & เชื่อม LINE Webhook
```bash
ngrok http 8000
```
นำ URL ที่ได้ (เช่น `https://xxxx.ngrok-free.app/callback`) ไปใส่ในช่อง **Webhook URL** บน [LINE Developers Console](https://developers.line.biz/) และเปิดใช้งาน Webhook

---

## 🔒 Security Note
ไฟล์ `.env` ถูกตั้งค่าละเว้นไว้ใน `.gitignore` เพื่อความปลอดภัย โปรดอย่า Commit Secret Keys หรือ Access Tokens ขึ้นสู่ Public Repository โดยเด็ดขาด
