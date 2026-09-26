# 02. คู่มือการเชื่อมต่อ LINE Messaging API (LINE Developer Guide)

เอกสารนี้รวบรวมหลักการ วิธีการตั้งค่า และโค้ดสำหรับเชื่อมต่อกับ LINE Platform โดยเฉพาะ

---

## 1. การตั้งค่าบน LINE Developers Console และ LINE Official Account Manager

### ก. การขอรับ API Keys (บน [LINE Developers Console](https://developers.line.biz/))
1. สร้าง **Provider** และสร้าง Channel ชนิด **Messaging API**
2. **Channel Secret**: อยู่ในแท็บ `Basic settings`
3. **Channel Access Token (long-lived)**: อยู่ในแท็บ `Messaging API` เลื่อนลงไปล่างสุด กดปุ่ม **Issue**

### ข. การตั้งค่าระบบตอบกลับ (สำคัญมาก)
เข้าไปที่ **LINE Official Account Manager** ([manager.line.biz](https://manager.line.biz/)) ➔ Settings ➔ Response settings:
- **Auto-reply messages**: **Disabled (ปิด)** เพื่อไม่ให้ระบบบอตดีฟอลต์ของ LINE ตอบชนกับ AI
- **Webhooks**: **Enabled (เปิด)**
- **Greeting message**: สามารถเปิดหรือปิดได้ตามต้องการ

---

## 2. การจัดการความปลอดภัยและ Signature Verification

LINE Platform จะส่ง Header พิเศษชื่อ `X-Line-Signature` มากับทุก Webhook Request ซึ่งเป็นการเข้ารหัส HMAC-SHA256 ระหว่าง Request Body และ Channel Secret

โค้ดที่ถูกต้องในการตรวจสอบ (ใน `main.py`):
```python
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError

parser = WebhookParser(LINE_CHANNEL_SECRET)

@app.post("/callback")
async def callback(request: Request, background_tasks: BackgroundTasks):
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # ประมวลผลใน background task เพื่อตอบ 200 OK ให้ LINE ทันที
    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            background_tasks.add_task(process_message_event, event)

    return JSONResponse(content={"status": "OK"})
```

> **ข้อควรระวังสำคัญ**: LINE กำหนดว่าเซิร์ฟเวอร์ต้องตอบสถานะ `HTTP 200 OK` ภายในไม่กี่วินาทีหลังจากได้รับ Webhook หากใช้เวลานานเกินไป LINE จะมองว่า Webhook Timeout และพยายามยิงซ้ำ (Redelivery) ทำให้ตอบข้อความเบิ้ล ดังนั้นเราจึงใช้ **FastAPI BackgroundTasks** ในการแยกการคุยกับ AI ออกไปทำเบื้องหลัง

---

## 3. การแยกแยะแชตส่วนตัว (1-on-1) และกลุ่ม (Group / Room)

ในระบบ LINE ค่า `event.source.type` จะระบุประเภทห้องแชต:
- `"user"`: แชตส่วนตัว 1-on-1
- `"group"`: กลุ่ม LINE (มี `event.source.group_id`)
- `"room"`: ห้องแชตหลายคนแบบชั่วคราว (มี `event.source.room_id`)

### กฎการทำงาน:
1. **ในแชตส่วนตัว (`user`)**: ตอบทุกข้อความเสมอ
2. **ในกลุ่ม (`group` / `room`)**: ตอบเฉพาะเมื่อถูก Mention หรือ Tag เท่านั้น

### วิธีการตรวจจับ Mention ที่แม่นยำ (Hybrid Detection):
เรารองรับ 2 ทางคู่ขนาน:
1. **LINE Native Mention**: เช็คจาก Object `event.message.mention` ว่ามี mentionee ที่ `is_self == True` หรือไม่
2. **Text-based Mention**: เช็คว่าข้อความมีคำว่า `@Jarvis`, `@จาร์วิส` หรือขึ้นต้นด้วย `Jarvis` หรือไม่

```python
import re

def clean_mention_text(text: str) -> str:
    """ตัดคำว่า @Jarvis ออกเพื่อให้ AI ได้รับคำถามที่สะอาด"""
    cleaned = re.sub(r"@?(jarvis|จาร์วิส)[:,\s]*", "", text, flags=re.IGNORECASE).strip()
    return cleaned if cleaned else "สวัสดีครับ"

# ตรวจสอบในกลุ่ม:
if source_type in ["group", "room"]:
    session_id = getattr(event.source, "group_id", None) or getattr(event.source, "room_id", None)
    
    is_mentioned = False
    # 1. Native mention
    if hasattr(event.message, "mention") and event.message.mention:
        for m in event.message.mention.mentionees:
            if getattr(m, "is_self", False):
                is_mentioned = True
                break
    
    # 2. Text mention
    lower_text = user_text.lower()
    if "@jarvis" in lower_text or "@จาร์วิส" in lower_text or lower_text.startswith("jarvis"):
        is_mentioned = True

    if not is_mentioned:
        return  # ปล่อยผ่าน ไม่ตอบถ้าไม่ได้แท็ก Jarvis

    prompt_text = clean_mention_text(user_text)
```

---

## 4. ข้อจำกัดและข้อควรระวังเฉพาะของ LINE API

1. **Loading Animation (`ShowLoadingAnimationRequest`)**:
   - รองรับเฉพาะ **1-on-1 Chat (`source_type == "user"`) เท่านั้น!**
   - หากยิงคำสั่งนี้ใน Group หรือ Room ระบบของ LINE จะตอบกลับมาเป็น HTTP 400 Bad Request
   - ดังนั้นโค้ดต้องครอบเช็ค `if source_type == "user":` ก่อนเรียกใช้งานเสมอ
2. **โควตาข้อความ (Messaging Quota)**:
   - การส่งข้อความแบบตอบกลับผ่าน `reply_token` ด้วย `line_bot_api.reply_message(...)` **ไม่ถูกคิดในโควตาส่งข้อความรายเดือน (ฟรีไม่จำกัดจำนวนครั้ง)**
   - แต่ละ `reply_token` มีอายุการใช้งานสั้นมาก (ประมาณ 30-60 วินาที) และใช้งานได้เพียง 1 ครั้งเท่านั้น
