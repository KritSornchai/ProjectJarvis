# 03. วิศวกรรมระบบ AI Agent (Gemini AI Engineering)

เอกสารนี้รวบรวมหลักการออกแบบสมอง AI การจัดการ Context Memory การสืบค้นข้อมูลสด และกลยุทธ์การป้องกันข้อผิดพลาดจาก Quota Limit

---

## 1. การเลือกใช้ SDK และโมเดล (SDK & Model Architecture)

เราเลือกใช้ **Google GenAI SDK อย่างเป็นทางการตัวล่าสุด (`google-genai`)** แทน SDK รุ่นเก่า (`google-generativeai`) 

### ตารางวิเคราะห์โมเดลและโควตา Free Tier:

| โมเดล (Model) | สถานะ / โควตา Free Tier | ความเหมาะสม |
| :--- | :--- | :--- |
| `gemini-2.5-flash` | **จำกัดเพียง 20 Requests / วัน** | ❌ ไม่เหมาะกับ Production (ชน 429 ง่ายมาก) |
| `gemini-2.5-flash-lite` | **โควตาสูง ตอบสนองไวมาก (< 1 วินาที)** |  **โมเดลหลัก (Primary)** |
| `gemini-3.5-flash-lite` | โควตาสูง มีความฉลาดด้านการใช้เครื่องมือสูง |  **โมเดลสำรองอันดับ 1** |
| `gemini-flash-lite-latest` | อัปเดตชี้ไปที่ตัวเสถียรล่าสุดอัตโนมัติ |  **โมเดลสำรองอันดับ 2** |
| `gemini-flash-latest` | โมเดลมาตรฐานคุณภาพสูง |  **โมเดลสำรองอันดับ 3** |
| `gemini-3.8-flash` | โมเดลเรือธงความสามารถสูง |  **โมเดลสำรองอันดับ 4** |

---

## 2. กลยุทธ์ Multi-Model Auto-Fallback & ประวัติความจำข้ามโมเดล

หนึ่งในปัญหาใหญ่ของ Free Tier คือ **Error 429 RESOURCE_EXHAUSTED** เมื่อการใช้งานในชั่วโมงนั้นสูงขึ้น เราจึงออกแบบระบบ **Auto-Fallback** ที่ทนทาน:

```python
DEFAULT_MODEL_FALLBACKS = [
    "gemini-2.5-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-3.8-flash",
]
```

### การคงสภาพความจำ (Stateful Memory Persistence):
แทนที่จะผูก Session กับ Object เฉพาะโมเดล เราจัดเก็บประวัติการสนทนาในรูปแบบโครงสร้างข้อมูลกลาง:
```python
# session_id -> List[types.Content]
self.histories[session_id] = [
    types.Content(role="user", parts=[types.Part.from_text(text=...)]),
    types.Content(role="model", parts=[types.Part.from_text(text=...)])
]
```
**ข้อดีมหาศาล**: หากโมเดลแรกเกิด Error 429 ระบบจะนำ `history` ก้อนเดียวกันนี้ ส่งต่อไปให้โมเดลตัวถัดไปประมวลผลทันที ผู้ใช้งานใน LINE จะไม่รู้สึกว่าระบบติดขัด และคุยต่อเนื่องได้ทันที

---

## 3. การเชื่อมต่อ Google Search Grounding (สืบค้น Real-time)

การตอบคำถามเรื่องข่าวสาร สถานการณ์ปัจจุบัน (เช่น ข่าวน้ำท่วม, ราคาน้ำมัน, ผลบอล) จำเป็นต้องอาศัยข้อมูลสด เราเปิดใช้งาน **Google Search Grounding** ของ Google:

```python
from google.genai import types

response = client.models.generate_content(
    model=model_name,
    contents=current_request_contents,
    config=types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.7,
    )
)
```

**พฤติกรรมของ AI**:
- เมื่อถูกถามเรื่องสดใหม่ AI จะสร้าง Query วิ่งไปค้น Google แล้วอ่านเว็บข่าวดังๆ แบบเรียลไทม์
- นำข้อมูลข้อเท็จจริงมาสรุปเป็นภาษาไทยอย่างกระชับ
- **ยังคงฟรี 100%** ภายใต้โควตา Free Tier ของ Gemini Flash

---

## 4. ระบบรับรู้วันและเวลาไทยแบบ Dynamic (Bangkok Date & Time Awareness)

AI ส่วนใหญ่มักมีปัญหาไม่รู้วันที่ปัจจุบัน หรือสับสนปี พ.ศ. กับ ค.ศ. เราแก้ปัญหานี้ด้วยการสร้าง **Dynamic System Instruction** ในทุกๆ Request:

```python
def get_system_instruction() -> str:
    tz_bkk = timezone(timedelta(hours=7))
    now = datetime.now(tz_bkk)
    thai_year = now.year + 543
    date_str = now.strftime(f"%d/%m/{thai_year} (ค.ศ. %Y) เวลา %H:%M น.")

    return f"""คุณคือ Jarvis (จาร์วิส) AI ผู้ช่วยส่วนตัวอัจฉริยะของผู้ใช้
วันเวลาปัจจุบันในประเทศไทยคือ: {date_str}
...
"""
```

**ผลลัพธ์ที่ได้**:
- หากผู้ใช้ถาม: *"วันที่ 26 กันยายน น้ำท่วมเป็นไง"* ➔ Jarvis จะรู้ทันทีว่าวันนี้คือ 26 กันยายน และเสิร์ชข่าวของวันนี้
- หากผู้ใช้ถาม: *"ปี 2575 จะเป็นไง"* ➔ Jarvis จะรู้ทันทีว่าปี 2575 ยังมาไม่ถึง และตอบอย่างถูกต้องตามหลักตรรกะ

---

## 5. การจัดการหน่วยความจำ (Memory Retention & Truncation)
- **Sliding Window**: เพื่อไม่ให้ค่า Token บวมจนเกินลิมิต ระบบจะรักษาบทสนทนาไว้สูงสุด 20 รอบการคุยล่าสุด (`max_history_turns = 20`) หากเกินจะตัดข้อความเก่าสุดออก
- **Reset Command**: เมื่อผู้ใช้พิมพ์ `/reset` หรือ `รีเซ็ต` ระบบจะลบประวัติของ session นั้นออกทันที เพื่อเริ่มบริบทใหม่
