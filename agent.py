import os
import re
import logging
import urllib.request
import urllib.parse
from html import unescape
from typing import Dict, List
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Search trigger keywords (Thai and English)
SEARCH_KEYWORDS = [
    # Thai keywords
    "ค้น", "เสิร์ช", "หา", "ข่าว", "วันนี้", "ล่าสุด", "สภาพอากาศ", "ราคาน้ำมัน", "สถานการณ์",
    "จริงไหม", "ทำไม", "เช็ค", "ตรวจสอบ", "คืออะไร", "เมื่อไหร่", "อัปเดต", "ซิงค์", "ยกเลิก",
    # English keywords
    "search", "google", "find", "news", "today", "latest", "weather", "update", "current",
    "why", "what", "is it true", "confirm", "when", "how", "sync", "ending", "discontinue",
    "tell me", "check", "information", "happened"
]

def needs_search(text: str) -> bool:
    """Check if the user message requires real-time search grounding"""
    lower = text.lower()
    return any(k in lower for k in SEARCH_KEYWORDS)

def perform_web_search(query: str, max_results: int = 5) -> str:
    """Lightweight, 100% free web search using DuckDuckGo HTML without external dependencies"""
    try:
        clean_q = re.sub(r"@?(jarvis|จาร์วิส)[:,\s]*", "", query, flags=re.IGNORECASE).strip()
        encoded = urllib.parse.quote_plus(clean_q)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        snippets = re.findall(r'<a class=\"result__snippet[^\"]*\"[^>]*>(.*?)</a>', html, re.DOTALL)
        results = [unescape(re.sub(r'<.*?>', '', s)).strip() for s in snippets[:max_results]]
        valid_results = [r for r in results if len(r) > 15]
        if valid_results:
            return "\n".join(f"- {r}" for r in valid_results)
    except Exception as e:
        logger.warning(f"Web search failed: {e}")
    return ""

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
- คุณสามารถค้นหาข้อมูลบนอินเทอร์เน็ต เพื่อเข้าถึงข้อมูลล่าสุด ข่าวสาร หรือเหตุการณ์ปัจจุบัน
- เมื่อได้รับข้อมูลผลการค้นหา ให้ใช้อ้างอิงข้อเท็จจริงเสมอ และตอบคำถามทันที ห้ามตอบเพียงแค่รับทราบ
- หากผู้ใช้ถามถึงวันที่หรือปีที่ยังมาไม่ถึง (อนาคต) ให้แจ้งอย่างสุภาพว่ายังมาไม่ถึง
- หากผู้ใช้ไม่ระบุปี ให้เทียบกับวันเวลาปัจจุบันหรือถามเพื่อความแน่ใจอย่างสุภาพ

กฎภาษาและการตอบ:
- ถ้าผู้ใช้ถามเป็นภาษาอังกฤษ ให้ตอบเป็นภาษาอังกฤษอย่างคล่องแคล่ว
- ถ้าผู้ใช้ถามเป็นภาษาไทย ให้ตอบเป็นภาษาไทย
- ตอบด้วยความมั่นใจ หากเรื่องใดไม่แน่ใจให้แจ้งตามตรงและแนะนำแนวทางตรวจสอบเพิ่มเติม
- ปรับน้ำเสียงให้ดูเหมือน Jarvis จาก Iron Man ที่มีความจงรักภักดีและเฉลียวฉลาด
"""

DEFAULT_MODEL_FALLBACKS = [
    "gemini-3.5-flash-lite",   # 500 requests / day!
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
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
        """Process incoming user message and return response with robust real-time search & fallback"""
        session_id = user_id

        # Command to reset memory
        if message_text.strip().lower() in ["/reset", "รีเซ็ต", "ลืมการคุยก่อนหน้านี้"]:
            self.reset_memory(session_id)
            return "กระผมได้รีเซ็ตความทรงจำบทสนทนาเรียบร้อยแล้วครับ มีอะไรให้ Jarvis รับใช้เพิ่มเติมไหมครับ?"

        history = self.histories.get(session_id, [])

        system_instruction = get_system_instruction()

        # Check if real-time web search should be performed
        if needs_search(message_text):
            logger.info(f"Triggering web search for: {message_text[:60]}")
            search_snippets = perform_web_search(message_text)
            if search_snippets:
                logger.info(f"Search retrieved {len(search_snippets)} chars of context")
                system_instruction += (
                    f"\n\n[ข้อมูลข้อเท็จจริงล่าสุดที่ค้นหาได้จากอินเทอร์เน็ต]:\n{search_snippets}\n\n"
                    "คำสั่ง: โปรดใช้ข้อมูลข้างต้นในการตอบคำถามอย่างถูกต้อง แม่นยำ และตอบกลับทันที (ห้ามตอบแค่รับทราบ)"
                )

        user_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=message_text)]
        )
        current_request_contents = history + [user_content]

        last_error = None

        # Loop through candidate models (Standard generation with injected search context)
        for model_name in self.models:
            try:
                logger.info(f"Calling Gemini ({model_name}) for session {session_id}")
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
                logger.info(f"Gemini responded successfully: {reply_text[:60]}")
                self._save_history(session_id, current_request_contents, reply_text)
                return reply_text
            except Exception as e:
                logger.warning(f"Model {model_name} failed: {e}. Trying next model...")
                last_error = e
                continue

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
