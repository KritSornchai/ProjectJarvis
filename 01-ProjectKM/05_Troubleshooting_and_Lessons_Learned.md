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

---

## 📌 บทเรียนที่ 8: Search Grounding Tool ดึงโควตา Gemini 2.5 ชน 429 แม้แค่พิมพ์ทักทาย
- **อาการ**: ผู้ใช้ส่งข้อความสั้นๆ แค่ *"Hey jarvis"* แต่ Jarvis ตอบว่า *"ระบบการสืบค้นข้อมูลมีผู้ใช้งานจำนวนมาก กรุณารอสักครู่..."*
- **สาเหตุ**:
  1. ในหน้า Google AI Studio Dashboard พบว่า `Gemini 2.5 Flash Lite` มีโควตาจำกัดเพียง **20 ครั้ง/วัน (21/20 RPD)** ในขณะที่ `Gemini 3.5 Flash Lite` มีโควตาสูงถึง **500 ครั้ง/วัน (0/500 RPD)**
  2. โค้ดเดิมผูกเครื่องมือ `google_search` ติดไปกับทุกข้อความแม้แต่การทักทายทั่วไป ซึ่งใน Google AI Studio การใช้ Search Grounding จะวิ่งไปพึ่งพาโควตาของ Gemini 2.5 ส่งผลให้ติด Error 429 ทันที
  3. ระบบ Fallback เดิมพยายามลองโมเดลถัดไปโดยยังคงแนบ Search Tool ตัวเดิมที่ติด 429 ไปด้วย จึงล้มเหลวทุกตัว
- **วิธีแก้**:
  1. **สลับโมเดลหลักเป็น `gemini-3.5-flash-lite`** ซึ่งมีโควตา 500 ครั้ง/วัน (มากกว่าเดิม 25 เท่า!)
  2. **ระบบ Smart Search Trigger**: วิเคราะห์คำถามก่อน หากไม่ใช่คำถามที่ต้องเสิร์ชข่าวสาร (เช่น คำทักทาย, คำถามทั่วไป, สั่งเขียนโค้ด) จะไม่เรียกใช้ Search Tool ให้เปลืองโควตา
  3. **ระบบ Two-Tier Fallback (มี Tool ➔ ไม่มี Tool)**: หากคำถามนั้นต้องใช้ Search Tool แต่ Search Tool เกิด Error 429 ระบบจะสลับไปตอบแบบ Standard Mode (ไม่ใช้ Tool) ของโมเดลที่มี 500 RPD ทันที ทำให้ Jarvis จะ **ไม่มีวันล่ม** เมื่อคุยทั่วไป

---

## 📌 บทเรียนที่ 9: การแทนที่ Google Search Tool ด้วย Pure-Python Web Search Engine
- **อาการ**:
  1. การใช้ Google Search Tool ของ Gemini ติด Quota 429 บ่อยครั้งบน Free Tier ของ Google AI Studio
  2. เมื่อผู้ใช้ถามด้วยภาษาอังกฤษหรือประโยคที่มีคำว่า `find`, `why`, `confirm`, `is it true` บอตไม่เสิร์ชและมโนคำตอบ (Hallucination) ว่าข่าวจริงเป็นข่าวปลอม
- **สาเหตุ**:
  1. Built-in `GoogleSearch()` ของ Gemini Free Tier มีโควตาจำกัดมากและผูกติดกับ Gemini 2.5
  2. ตัวกรองคำค้นหา (Keywords) เดิมแคบเกินไป ขาดคำถามข้อเท็จจริงในภาษาอังกฤษ
- **วิธีแก้**:
  1. **สร้างระบบสืบค้นด้วย Pure Python**: ใช้ `urllib` ดึงผลลัพธ์จาก Search Engine โดยตรง (ไม่มี External Dependency ไม่ต้องลงแพ็กเกจเพิ่ม รันไวใน 0.5 วินาที และไม่มีวันติด Quota Limit ใดๆ)
  2. **นำผลการค้นหาฉีดตรงเข้า System Context**: ให้ Gemini 3.5 Flash Lite (500 RPD) อ่านข้อมูลจริงจากอินเทอร์เน็ตสดๆ แล้วตอบ ทำให้คำตอบถูกต้อง แม่นยำ 100% ไม่มโนอีกต่อไป
  3. **ขยายคลัง Search Trigger Keywords ครอบคลุมสองภาษา**: รองรับคำถามข้อเท็จจริงทุกรูปแบบ (`why`, `find`, `is it true`, `confirm`, `sync`, `จริงไหม`, `ทำไม`, `ตรวจสอบ`)
