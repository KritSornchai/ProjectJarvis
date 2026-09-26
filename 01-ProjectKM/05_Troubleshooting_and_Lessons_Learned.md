# 05. บันทึกการแก้ปัญหาและบทเรียนสำคัญ (Troubleshooting & Lessons Learned)

เอกสารนี้รวบรวม **ปัญหาจริงทั้งหมดที่เกิดขึ้นจริงระหว่างการพัฒนา**, สาเหตุเชิงลึก (Root Cause), และวิธีการแก้ไขอย่างเป็นระบบ เพื่อเป็นแนวทางอ้างอิงสำหรับอนาคต

---

## 📌 บทเรียนที่ 1: การติดตั้งไลบรารีด้วย pip บน Python 3.9 ของ macOS
- **อาการ**: เมื่อรัน `pip install -r requirements.txt` จะเกิด Error:
  ```text
  SyntaxError: invalid syntax in aenum/_py2.py
  TypeError: encode() argument 'encoding' must be str, not None
  ```
- **สาเหตุ**: แพ็กเกจ `aenum` (dependency ย่อยของ LINE SDK) มีโค้ดของ Python 2 ปนอยู่ ซึ่งตัว compileall ของ Python 3.9 บน macOS พยายาม pre-compile เป็น `.pyc` แล้วล้มเหลว
- **วิธีแก้**: เติมแฟล็ก `--no-compile` ในคำสั่ง pip เสมอ:
  ```bash
  pip install --no-compile -r requirements.txt
  ```

---

## 📌 บทเรียนที่ 2: ข้อผิดพลาด Error 429 RESOURCE_EXHAUSTED (Quota Limit)
- **อาการ**: ใช้งาน Jarvis ไปได้ประมาณ 15-20 ข้อความ แล้ว AI เริ่มตอบว่า:
  ```text
  429 RESOURCE_EXHAUSTED: Quota exceeded for metric: ... limit: 20, model: gemini-2.5-flash
  ```
- **สาเหตุ**: โมเดล `gemini-2.5-flash` เป็นโมเดลเวอร์ชันทดสอบ (Preview) ซึ่ง Google กำหนดเพดาน Free Tier ไว้ต่ำมากเพียง **20 ครั้งต่อวัน**
- **วิธีแก้**:
  1. เปลี่ยนโมเดลหลักไปใช้ **`gemini-2.5-flash-lite`** ซึ่งเป็นโมเดลที่โควตาสูง ตอบสนองเร็วมาก และมีไว้สำหรับงาน Chatbot
  2. เขียนระบบ **Multi-Model Auto-Fallback** ใน `agent.py` หากโมเดลใดเต็ม ให้สลับไปเรียกโมเดลตัวถัดไปทันทีโดยอัตโนมัติ

---

## 📌 บทเรียนที่ 3: Loading Animation ใช้งานไม่ได้ในกลุ่ม (Group Chat)
- **อาการ**: เมื่อดึง Jarvis เข้ากลุ่ม LINE และมีคนพิมพ์คุย ระบบพ่น Warning:
  ```text
  Could not trigger loading animation: 400 Bad Request
  ```
- **สาเหตุ**: ข้อกำหนดอย่างเป็นทางการของ LINE Messaging API ระบุว่า `ShowLoadingAnimationRequest` **รองรับเฉพาะห้องแชตส่วนตัว 1-on-1 (`source.type == "user"`) เท่านั้น** ห้ามยิงใน Group หรือ Room
- **วิธีแก้**: ครอบเงื่อนไขใน `main.py`:
  ```python
  if source_type == "user":
      line_bot_api.show_loading_animation(...)
  ```

---

## 📌 บทเรียนที่ 4: Jarvis ตอบแทรกทุกคนในกลุ่มโดยไม่ได้เรียก
- **อาการ**: เมื่อเพื่อนในกลุ่มคุยกันเอง Jarvis ตอบกลับทุกข้อความ ทำให้รบกวนการคุยในกลุ่ม
- **สาเหตุ**: Webhook ของ LINE จะส่งทุกข้อความในกลุ่มมาที่เซิร์ฟเวอร์ โค้ดเดิมยังไม่มีตัวกรอง Mention
- **วิธีแก้**: ออกแบบระบบ **Hybrid Mention Detection**:
  1. ดักจับ LINE Native Mention (`mentionee.is_self == True`)
  2. ดักจับ Text Mention (`@Jarvis`, `@จาร์วิส`, หรือขึ้นต้นด้วย `Jarvis`)
  3. หากไม่ได้ Mention ให้ข้ามทันที (`return`) ไม่ส่งไปหา AI
  4. หาก Mention ให้ตัดคำว่า `@Jarvis` ออกจากคำถาม เพื่อให้ AI ได้คำถามที่สะอาด

---

## 📌 บทเรียนที่ 5: การเปลี่ยนชื่อโฟลเดอร์ทำให้ Python Virtual Environment (`.venv`) พัง
- **อาการ**: เมื่อเปลี่ยนชื่อโฟลเดอร์จาก `line-ai-agent` เป็น `ProjectJarvis` ใน Finder แล้วรันคำสั่ง python หรือ uvicorn จะฟ้องว่า `bad interpreter: no such file or directory`
- **สาเหตุ**: ตัว Python Virtual Environment บน macOS จะบันทึก Absolute Path ของโฟลเดอร์ไว้ในหัวไฟล์ Scripts (`.venv/bin/*`) เมื่อชื่อโฟลเดอร์เปลี่ยน Path เดิมจึงกลายเป็น Broken Link
- **วิธีแก้**: เมื่อเปลี่ยนชื่อโฟลเดอร์ ให้ลบและสร้าง `.venv` ใหม่ทันที:
  ```bash
  rm -rf .venv
  python3 -m venv .venv
  .venv/bin/pip install --no-compile -r requirements.txt
  ```

---

## 📌 บทเรียนที่ 6: คอมพิวเตอร์ Sleep หรือ Shutdown ทำให้บอตหลุดการเชื่อมต่อ
- **อาการ**: เมื่อพับหน้าจอ Mac Mini หรือปิดเครื่อง Jarvis ใน LINE จะไม่ตอบ
- **สาเหตุ**: เซิร์ฟเวอร์และ Ngrok รันอยู่บนเครื่อง Local เมื่อเครื่องหลับ Connection Socket จะถูกตัด
- **วิธีแก้**: ย้ายไปรันบน **Cloud Hosting ฟรีตลอด 24 ชั่วโมง (Render.com)**
  - เชื่อมต่อกับ GitHub Repo `KritSornchai/ProjectJarvis`
  - Render ให้ HTTPS URL ถาวร
  - ไม่ต้องเปิด Ngrok และปิดคอมพิวเตอร์ Mac Mini ได้เลย

---

## 📌 บทเรียนที่ 7: AI ไม่รู้ข่าวสารปัจจุบัน หรือไม่รู้วันเวลาปัจจุบัน
- **อาการ**: ถามเรื่องน้ำท่วมหรือเหตุการณ์ล่าสุด AI ตอบว่าไม่มีข้อมูล หรือไม่รู้ว่าวันนี้คือวันที่เท่าไหร่
- **สาเหตุ**: โมเดล LLM ถูกเทรนด้วยข้อมูลย้อนหลัง และไม่มีนาฬิกาภายในตัว
- **วิธีแก้**:
  1. คำนวณวันและเวลาไทย (UTC+7) แบบ Real-time แล้วใส่ลงใน **Dynamic System Instruction**
  2. เปิดใช้งานเครื่องมือ **`GoogleSearch()` (Google Search Grounding)** ทำให้ AI ออกไปเสิร์ช Google ค้นหาข่าวในวินาทีนั้นได้ทันทีแบบฟรี 100%
