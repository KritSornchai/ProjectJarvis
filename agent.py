import os
import re
import logging
from typing import Dict, List
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Search trigger keywords
SEARCH_KEYWORDS = [
    "ค้น", "เสิร์ช", "หาข่าว", "ข่าว", "วันนี้", "ล่าสุด", "สภาพอากาศ", "ราคาน้ำมัน", "สถานการณ์",
    "search", "google", "news", "today", "latest", "weather", "update", "current"
]

def needs_search(text: str) -> bool:
    """Check if the user message requires real-time search grounding"""
    lower = text.lower()
    return any(k in lower for k in SEARCH_KEYWORDS)

def get_system_instruction() -> str:
    """Returns dynamic system instruction with real-time Bangkok date and time context"""
    tz_bkk = timezone(timedelta(hours=7))
    now = datetime.now(tz_bkk)
    thai_year = now.year + 543
    date_str = now.strftime(f"%d/%m/{thai_year} (ค.ศ. %Y) เวลา %H:%M น.")

    return f"""คุณคือ Jarvis (จาร์วิส) AI ผู้ช่วยส่วนตัวอัจฉริยะของผู้ใช้
วันเวลาปัจจุบันในประเทศไทยคือ: {date_str}

บทบาทและลักษณะนิสัย:
- สุภาพ ฉลาด คล่องแคล่ว เป็นมิตร และพร้อมช่วยเหลือในทุกเรื่อง
- ตอบคำถามอย่างกระชับ ตรงประเด็น เข้าใจง่าย และใช้ภาษาไทยอย่างเป็นธรรมชาติ
- จดจำบริบทการสนทนาและช่วยคิด วิเคราะห์ วางแผนงาน หรือให้คำปรึกษาได้ดี
- หากข้อความยาว ให้จัดเป็นข้อย่อย (bullet points) เพื่อให้อ่านใน LINE ได้สะดวกสบาย

ความสามารถในการสืบค้นข้อมูลข่าวสาร:
- คุณสามารถค้นหาข้อมูลบน Google Search เพื่อเข้าถึงข้อมูลล่าสุด ข่าวสาร หรือเหตุการณ์ปัจจุบัน
- หากผู้ใช้ถามถึงวันที่หรือปีที่ยังมาไม่ถึง (อนาคต) ให้แจ้งอย่างสุภาพว่ายังมาไม่ถึง
- หากผู้ใช้ไม่ระบุปี ให้เทียบกับวันเวลาปัจจุบันหรือถามเพื่อความแน่ใจอย่างสุภาพ

กฎภาษาและการตอบ:
- ถ้าผู้ใช้ถามเป็นภาษาอังกฤษ ให้ตอบเป็นภาษาอังกฤษอย่างคล่องแคล่ว
- ถ้าผู้ใช้ถามเป็นภาษาไทย ให้ตอบเป็นภาษาไทย
- ตอบด้วยความมั่นใจ หากเรื่องใดไม่แน่ใจให้แจ้งตามตรงและแนะนำแนวทางตรวจสอบเพิ่มเติม
- ปรับน้ำเสียงให้ดูเหมือน Jarvis จาก Iron Man ที่มีความจงรักภักดีและเฉลียวฉลาด
"""

# Free tier models prioritized by highest daily quota (Gemini 3.5 Flash Lite has 500 RPD)
DEFAULT_MODEL_FALLBACKS = [
    "gemini-3.5-flash-lite",   # 500 requests / day!
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",   # 20 requests / day
    "gemini-3.8-flash",
]

class AgentManager:
    def __init__(self, api_key: str, primary_model: str = "gemini-3.5-flash-lite", model_name: str = None):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)

        chosen_primary = model_name or primary_model or "gemini-3.5-flash-lite"
        models = [chosen_primary]
        for m in DEFAULT_MODEL_FALLBACKS:
            if m not in models:
                models.append(m)
        self.models = models

        self.histories: Dict[str, List[types.Content]] = {}
        self.max_history_turns = 20

    def reset_memory(self, session_id: str):
        """Reset conversation memory for a user or group"""
        if session_id in self.histories:
            del self.histories[session_id]

    async def get_response(self, user_id: str, message_text: str) -> str:
        """Process incoming user message and return response with smart search & multi-tier fallback"""
        session_id = user_id

        # Command to reset memory
        if message_text.strip().lower() in ["/reset", "รีเซ็ต", "ลืมการคุยก่อนหน้านี้"]:
            self.reset_memory(session_id)
            return "กระผมได้รีเซ็ตความทรงจำบทสนทนาเรียบร้อยแล้วครับ มีอะไรให้ Jarvis รับใช้เพิ่มเติมไหมครับ?"

        history = self.histories.get(session_id, [])

        user_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=message_text)]
        )
        current_request_contents = history + [user_content]

        last_error = None
        system_instruction = get_system_instruction()
        should_search = needs_search(message_text)

        # Loop through candidate models
        for model_name in self.models:
            # Plan A: If message requests real-time search, attempt with Google Search tool
            if should_search:
                try:
                    logger.info(f"Calling Gemini ({model_name}) WITH Google Search for session {session_id}")
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=current_request_contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            tools=[types.Tool(google_search=types.GoogleSearch())],
                            temperature=0.7,
                        )
                    )
                    reply_text = response.text.strip() if response.text else "รับทราบครับ"
                    logger.info(f"Gemini (with search) succeeded: {reply_text[:60]}")
                    self._save_history(session_id, current_request_contents, reply_text)
                    return reply_text
                except Exception as e:
                    logger.warning(f"Model {model_name} with search failed: {e}. Falling back to standard mode...")
                    last_error = e

            # Plan B: Standard generation without tools (High 500 RPD quota, extremely fast)
            try:
                logger.info(f"Calling Gemini ({model_name}) WITHOUT tools for session {session_id}")
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=current_request_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    )
                )
                reply_text = response.text.strip() if response.text else "รับทราบครับ"
                logger.info(f"Gemini standard mode succeeded: {reply_text[:60]}")
                self._save_history(session_id, current_request_contents, reply_text)
                return reply_text
            except Exception as e:
                logger.warning(f"Model {model_name} standard mode failed: {e}. Trying next model...")
                last_error = e
                continue

        # If all models and plans fail
        logger.error(f"All Gemini models exhausted. Last error: {last_error}")
        return "ขออภัยครับ ตอนนี้โควตาการประมวลผลเต็มชั่วคราว กรุณารอสักครู่แล้วลองส่งข้อความใหม่อีกครั้งครับ"

    def _save_history(self, session_id: str, current_request_contents: list, reply_text: str):
        model_content = types.Content(
            role="model",
            parts=[types.Part.from_text(text=reply_text)]
        )
        new_history = current_request_contents + [model_content]
        if len(new_history) > self.max_history_turns * 2:
            new_history = new_history[-(self.max_history_turns * 2):]
        self.histories[session_id] = new_history
