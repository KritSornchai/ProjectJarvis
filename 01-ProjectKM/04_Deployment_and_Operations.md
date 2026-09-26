# 04. การติดตั้งและดำเนินงานระบบ (Deployment & Operations)

เอกสารนี้อธิบายวงจรการรันระบบ ทั้งการพัฒนาบนเครื่อง (Local Development) และการปล่อยรันบน Cloud 24/7 (Production Deployment)

---

## 1. การทำงาน 2 สภาพแวดล้อม (Dual-Environment Model)

| สภาพแวดล้อม | เครื่องมือที่ใช้ | วัตถุประสงค์ | ความพร้อมใช้งาน |
| :--- | :--- | :--- | :--- |
| **Local (Mac Mini)** | Uvicorn + Ngrok | ทดสอบฟังก์ชันใหม่ๆ, Debug โค้ดแบบเรียลไทม์ | รันเฉพาะตอนเปิดคอม |
| **Production (Cloud)** | Render.com | ให้บริการจริงตลอด 24 ชั่วโมง | ออนไลน์ตลอดเวลา ไม่ต้องเปิดคอม |

---

## 2. วิธีการรันบนเครื่อง Local (Local Development)

### คำสั่งรัน:
```bash
# 1. รัน FastAPI Server
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 2. รัน Ngrok Tunnel (ในอีกแท็บของ Terminal)
ngrok http 8000
```
- นำ URL ที่ได้จาก Ngrok เช่น `https://xxxx.ngrok-free.dev/callback` ไปใส่ใน LINE Developers
- เมื่อแก้โค้ด Uvicorn จะ reload อัตโนมัติทันที

---

## 3. วิธีการรันบน Cloud ถาวร (Production on Render.com)

Render.com เป็นบริการ Cloud Hosting ที่เชื่อมต่อกับ GitHub โดยตรงและมี Free Tier ให้ใช้งานฟรี 100%

### การตั้งค่า Web Service บน Render:
- **Repository**: `KritSornchai/ProjectJarvis`
- **Region**: `Singapore` (ใกล้ประเทศไทยที่สุด ค่า Latency ต่ำ)
- **Branch**: `main`
- **Runtime**: `Python 3`
- **Build Command**:
  ```bash
  pip install -r requirements.txt
  ```
- **Start Command**:
  ```bash
  uvicorn main:app --host 0.0.0.0 --port $PORT
  ```
- **Instance Type**: `Free ($0/month)`

### การตั้งค่าตัวแปรสิ่งแวดล้อม (Environment Variables บน Render):
กำหนดค่าในหน้า Dashboard แท็บ **Environment**:
```env
LINE_CHANNEL_SECRET=...
LINE_CHANNEL_ACCESS_TOKEN=...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash-lite
```

---

## 4. วงจรการอัปเดตอัตโนมัติ (CI/CD Auto-Deploy Workflow)

เมื่อโปรเจกต์เชื่อมกับ Render เรียบร้อยแล้ว ทุกครั้งที่พัฒนาฟีเจอร์ใหม่ การส่งขึ้น Production ทำได้ง่ายเพียง 3 คำสั่ง:

```bash
git add .
git commit -m "feat: คำอธิบายการเปลี่ยนแปลง"
git push origin main
```

### สิ่งที่เกิดขึ้นเบื้องหลัง:
1. GitHub ได้รับ Commit ใหม่บน branch `main`
2. GitHub ยิง Webhook แจ้งเตือน Render
3. Render ดึงโค้ดเวอร์ชันล่าสุดไปทำการ `pip install` และรีสตาร์ตเซิร์ฟเวอร์ใหม่อัตโนมัติ (ใช้เวลาประมาณ 1 นาที)
4. **URL เดิมของ LINE ไม่เปลี่ยนแปลง** ไม่ต้องเข้าไปแก้ไขใน LINE Developers อีกต่อไป

---

## 5. พฤติกรรมของ Render Free Tier (Sleep & Cold Start)
- **Inactivity Sleep**: หากไม่มีใครส่งข้อความหา Jarvis เกิน 15 นาที Render จะพักเซิร์ฟเวอร์ชั่วคราวเพื่อประหยัดพลังงาน
- **Cold Start**: เมื่อมีข้อความแรกทักเข้ามาหลังจากเซิร์ฟเวอร์พัก เซิร์ฟเวอร์จะใช้เวลาปลุกตัวเองประมาณ 30-50 วินาที ข้อความแรกอาจจะตอบกลับมาช้าเล็กน้อย แต่หลังจากนั้นจะตอบเร็วปกติทันที
