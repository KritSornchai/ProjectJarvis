from user_storage import user_storage
import os
import re
import logging
import urllib.request
import urllib.parse
from html import unescape
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Focused search trigger patterns (prevents over-triggering on casual conversation)
SEARCH_PATTERNS = [
    re.compile(r"(?i)\b(search|lookup|google for|latest news|breaking news|weather today|oil price|gold price)\b"),
    re.compile(r"(ค้นหา|ค้นข้อมูล|เสิร์ช|ช่วยค้น|หาข้อมูล|เช็คข่าว|ข่าวล่าสุด|ข่าวน้ำท่วม|สภาพอากาศ|พยากรณ์อากาศ|ราคาน้ำมัน|ราคาทอง|ตารางสอบ|กำหนดการสอบ)")
]

def needs_search(text: str) -> bool:
    """Check if the user message specifically requests external live data/search"""
    return any(p.search(text) for p in SEARCH_PATTERNS)

def perform_web_search(query: str, max_results: int = 5) -> str:
    """Lightweight, 100% free web search with strict 2.0s timeout to prevent delays"""
    try:
        clean_q = re.sub(r"@?(jarvis|จาร์วิส)[:,\s]*", "", query, flags=re.IGNORECASE).strip()
        encoded = urllib.parse.quote_plus(clean_q)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        snippets = re.findall(r'<a class="result__snippet[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)
        results = [unescape(re.sub(r'<.*?>', '', s)).strip() for s in snippets[:max_results]]
        valid_results = [r for r in results if len(r) > 15]
        if valid_results:
            return "\n".join(f"- {r}" for r in valid_results)
    except Exception as e:
        logger.info(f"Web search skipped/timed out: {e}. Falling back to internal Gemini intelligence.")
    return ""

def get_system_instruction(user_id: Optional[str] = None) -> str:
    """Returns dynamic system instruction with real-time Bangkok date and time context"""
    tz_bkk = timezone(timedelta(hours=7))
    now = datetime.now(tz_bkk)
    thai_year = now.year + 543
    date_str = now.strftime(f"%d/%m/{thai_year} (ค.ศ. %Y) เวลา %H:%M น.")

    prompt = f"""คุณคือ Jarvis (จาร์วิส) AI ผู้ช่วยส่วนตัวอัจฉริยะของผู้ใช้
วันเวลาปัจจุบันในประเทศไทยคือ: {date_str}


ความถูกต้องของข้อมูลและการป้องกันข้อมูลเท็จ (Anti-Hallucination):
- หากเป็นข้อมูลเฉพาะเจาะจง เช่น วันที่สอบ ตารางสอบ ประกาศทางการ หรือตัวเลขสถิติ หากไม่มีข้อมูลยืนยันแน่ชัด ห้ามคาดเดาหรือสร้างตัวเลข/วันที่ขึ้นมาเองอย่างเด็ดขาด
- ให้แจ้งตามตรงอย่างสุภาพว่ายังไม่พบข้อมูลที่ยืนยันอย่างเป็นทางการ และแนะนำแหล่งข้อมูลทางการที่น่าเชื่อถือ (เช่น เว็บไซต์ศูนย์ทดสอบ atc.chula.ac.th สำหรับ CU-TEP)

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
    if user_id:
        profile_context = user_storage.get_context_for_prompt(user_id)
        prompt += f"\n{profile_context}\n"

    return prompt

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

    async def get_response(self, user_id: str, message_text: str, display_name: Optional[str] = None) -> str:
        """Process incoming user message with isolated per-user file storage & summarization"""
        session_id = user_id

        # Ensure user file is initialized on first touch
        user_storage.get_or_create_user(session_id, display_name=display_name)

        # Command to reset memory for this specific user
        if message_text.strip().lower() in ["/reset", "รีเซ็ต", "ลืมการคุยก่อนหน้านี้"]:
            user_storage.clear_history(session_id)
            return "กระผมได้รีเซ็ตความทรงจำบทสนทนาเรียบร้อยแล้วครับ มีอะไรให้ Jarvis รับใช้เพิ่มเติมไหมครับ?"

        # Check for profile & cross-device quick commands (passcode linking, profile view)
        quick_reply = user_storage.handle_quick_commands(session_id, message_text)
        if quick_reply:
            return quick_reply

        # Check for Isolated Conversation Summarization command
        if re.search(r"(สรุป(บทสนทนา|เรื่องที่คุย|ทั้งหมด|การคุย)|summarize|summary)", message_text.lower()):
            transcript = user_storage.get_all_conversations_text(session_id)
            if not transcript or len(transcript.strip().split("\n")) < 2:
                return "ขณะนี้ยังไม่มีประวัติการสนทนาเพียงพอสำหรับการสรุปรวบยอดครับ เริ่มพูดคุยหรือปรึกษาเรื่องต่างๆ กับกระผมได้เลยครับ!"

            summary_prompt = (
                f"คุณคือ Jarvis AI ผู้ช่วยส่วนตัวอัจฉริยะ\n"
                f"ต่อไปนี้คือประวัติการสนทนาทั้งหมดระหว่างคุณกับผู้ใช้รายนี้ (และเฉพาะรายนี้เท่านั้น ห้ามอ้างอิงข้อมูลผู้อื่น):\n\n"
                f"{transcript}\n\n"
                f"คำสั่ง: โปรดสรุปรวบยอดเนื้อหาบทสนทนาทั้งหมดอย่างกระชับ ชัดเจน เป็นระบบ จัดหมวดหมู่ด้วย Bullet Points:\n"
                f"1. สรุปประเด็นหลักที่พูดคุยกัน\n"
                f"2. สิ่งที่ผู้ใช้สั่งให้จำ หรือกิจวัตร/ภารกิจสำคัญ (Action Items)\n"
                f"3. ข้อสังเกตหรือคำแนะนำเพิ่มเติมจาก Jarvis\n"
                f"ตอบกลับด้วยน้ำเสียงสุภาพ จงรักภักดี และเฉลียวฉลาด"
            )
            for model_name in self.models:
                try:
                    logger.info(f"Generating isolated summary using {model_name} for {session_id}")
                    resp = self.client.models.generate_content(
                        model=model_name,
                        contents=[types.Content(role="user", parts=[types.Part.from_text(text=summary_prompt)])],
                        config=types.GenerateContentConfig(
                            temperature=0.4,
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                        )
                    )
                    reply_text = resp.text.strip()
                    user_storage.append_conversation(session_id, "user", message_text)
                    user_storage.append_conversation(session_id, "model", reply_text)
                    return reply_text
                except Exception as e:
                    logger.warning(f"Model {model_name} failed for summary: {e}")
                    continue

        # Check if user asks to remember new facts/routines
        clean_msg = message_text.strip()
        if any(w in clean_msg for w in ["ช่วยจำว่า", "จำว่าผม", "บันทึกว่าผม", "จำไว้ว่า"]):
            extracted = re.sub(r"^(ช่วย)?(จำ|บันทึก)(ว่า|ไว้ว่า)?(ผม|ฉัน)?", "", clean_msg).strip()
            if extracted:
                user_storage.add_note(session_id, extracted)
                if any(k in extracted for k in ["กินยา", "ทานยา"]):
                    if "เย็น" in extracted or "ค่ำ" in extracted:
                        user_storage.update_routine(session_id, "evening", f"อย่าลืม{extracted}ครับ")
                    elif "เช้า" in extracted:
                        user_storage.update_routine(session_id, "morning", f"อย่าลืม{extracted}ครับ")

        # Load isolated persistent history from this user's JSON file
        history = user_storage.get_recent_history_contents(session_id, max_turns=15)

        system_instruction = get_system_instruction(user_id=session_id)

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
                # Append both user message and model response to user's dedicated file
                user_storage.append_conversation(session_id, "user", message_text)
                user_storage.append_conversation(session_id, "model", reply_text)
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
