import os
import logging
from typing import Dict, List
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_INSTRUCTION = """คุณคือ Jarvis (จาร์วิส) AI ผู้ช่วยส่วนตัวอัจฉริยะของผู้ใช้
บทบาทและลักษณะนิสัย:
- สุภาพ ฉลาด คล่องแคล่ว เป็นมิตร และพร้อมช่วยเหลือในทุกเรื่อง
- ตอบคำถามอย่างกระชับ ตรงประเด็น เข้าใจง่าย และใช้ภาษาไทยอย่างเป็นธรรมชาติ
- จดจำบริบทการสนทนาและช่วยคิด วิเคราะห์ วางแผนงาน หรือให้คำปรึกษาได้ดี
- หากข้อความยาวเกินไป ให้จัดเป็นข้อย่อย (bullet points) เพื่อให้อ่านใน LINE ได้สะดวกสบาย

กฎภาษาและการตอบ:
- ถ้าผู้ใช้ถามเป็นภาษาอังกฤษ ให้ตอบเป็นภาษาอังกฤษอย่างคล่องแคล่ว
- ถ้าผู้ใช้ถามเป็นภาษาไทย ให้ตอบเป็นภาษาไทย
- ตอบด้วยความมั่นใจ หากเรื่องใดไม่แน่ใจให้แจ้งตามตรงและแนะนำแนวทางตรวจสอบเพิ่มเติม
- ปรับน้ำเสียงให้ดูเหมือน Jarvis จาก Iron Man ที่มีความจงรักภักดีและเฉลียวฉลาด
"""


# Free tier models with high quota limits
DEFAULT_MODEL_FALLBACKS = [
    "gemini-2.5-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-3.8-flash",
]

class AgentManager:
    def __init__(self, api_key: str, primary_model: str = "gemini-2.5-flash-lite", model_name: str = None):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)
        
        chosen_primary = model_name or primary_model or "gemini-2.5-flash-lite"
        models = [chosen_primary]
        for m in DEFAULT_MODEL_FALLBACKS:
            if m not in models:
                models.append(m)
        self.models = models

        # Store conversation history: session_id -> list of types.Content
        self.histories: Dict[str, List[types.Content]] = {}
        # Maximum turns to retain per session
        self.max_history_turns = 20

    def reset_memory(self, session_id: str):
        """Reset conversation memory for a user or group"""
        if session_id in self.histories:
            del self.histories[session_id]

    async def get_response(self, user_id: str, message_text: str) -> str:
        """Process incoming user message and return response with automatic model fallback"""
        session_id = user_id

        # Command to reset memory
        if message_text.strip().lower() in ["/reset", "รีเซ็ต", "ลืมการคุยก่อนหน้านี้"]:
            self.reset_memory(session_id)
            return "กระผมได้รีเซ็ตความทรงจำบทสนทนาเรียบร้อยแล้วครับ มีอะไรให้ Jarvis รับใช้เพิ่มเติมไหมครับ?"

        # Get existing history or create empty list
        history = self.histories.get(session_id, [])

        # Create new user content
        user_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=message_text)]
        )
        current_request_contents = history + [user_content]

        last_error = None

        # Try models in priority order with fallback
        for model_name in self.models:
            try:
                logger.info(f"Calling Gemini with model: {model_name} for session {session_id}")
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=current_request_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=DEFAULT_SYSTEM_INSTRUCTION,
                        temperature=0.7,
                    )
                )

                reply_text = response.text.strip() if response.text else "รับทราบครับ"

                # Update history with user message and model response
                model_content = types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=reply_text)]
                )
                new_history = current_request_contents + [model_content]

                # Keep only last max_history_turns * 2 items
                if len(new_history) > self.max_history_turns * 2:
                    new_history = new_history[-(self.max_history_turns * 2):]

                self.histories[session_id] = new_history
                return reply_text

            except Exception as e:
                err_str = str(e)
                logger.warning(f"Model {model_name} failed: {err_str[:200]}. Trying next fallback model...")
                last_error = e
                continue

        # If all models fail
        logger.error(f"All Gemini models exhausted. Last error: {last_error}")
        return "ขออภัยครับ ตอนนี้โควตาการประมวลผลของระบบเต็มชั่วคราว กรุณารอสักครู่แล้วส่งข้อความใหม่อีกครั้งครับ"
