import os
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "user_profiles.json")

def get_bangkok_time() -> datetime:
    tz_bkk = timezone(timedelta(hours=7))
    return datetime.now(tz_bkk)

def get_time_period() -> Tuple[str, str]:
    """Returns (period_key, human_readable_description) based on current Bangkok hour"""
    hour = get_bangkok_time().hour
    if 5 <= hour < 12:
        return "morning", "ช่วงเช้า (เวลาเริ่มต้นวันใหม่)"
    elif 12 <= hour < 17:
        return "afternoon", "ช่วงบ่าย (เวลากลางวันและลุยภารกิจ)"
    elif 17 <= hour < 22:
        return "evening", "ช่วงเย็น/ค่ำ (เวลาอาหารเย็นและเตรียมพักผ่อน)"
    else:
        return "night", "ช่วงดึก (เวลาพักผ่อนนอนหลับ)"

class ProfileManager:
    def __init__(self, data_file: str = DATA_FILE):
        self.data_file = data_file
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.line_to_profile: Dict[str, str] = {}
        self._load()

    def _get_default_profiles(self) -> Dict[str, Dict[str, Any]]:
        return {
            "pann": {
                "profile_id": "pann",
                "name": "คุณ Pann",
                "passcode": "JARVIS-PANN",
                "line_user_ids": [],
                "routines": {
                    "morning": "เตรียมตัวเริ่มต้นวันใหม่ วางแผนภารกิจประจำวัน และดื่มน้ำให้เพียงพอครับ",
                    "evening": "อย่าลืมทานยาหลังอาหารเย็นเพื่อสุขภาพที่ดีของท่านครับ"
                },
                "notes": [
                    "ผู้สร้างและเจ้านายของ Jarvis",
                    "มีกิจวัตรสำคัญคือต้องทานยาตอนเย็นเป็นประจำ"
                ],
                "created_at": get_bangkok_time().isoformat(),
                "updated_at": get_bangkok_time().isoformat()
            }
        }

    def _load(self):
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.profiles = json.load(f)
            else:
                self.profiles = self._get_default_profiles()
                self._save()

            # Build line_user_id -> profile_id reverse lookup index
            self.line_to_profile = {}
            for pid, pdata in self.profiles.items():
                for uid in pdata.get("line_user_ids", []):
                    self.line_to_profile[uid] = pid
            logger.info(f"Loaded {len(self.profiles)} user profiles with {len(self.line_to_profile)} linked LINE IDs")
        except Exception as e:
            logger.error(f"Failed to load user profiles: {e}")
            self.profiles = self._get_default_profiles()

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.profiles, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save user profiles: {e}")

    def get_profile_by_line_id(self, line_user_id: str) -> Optional[Dict[str, Any]]:
        pid = self.line_to_profile.get(line_user_id)
        if pid and pid in self.profiles:
            return self.profiles[pid]
        return None

    def get_profile_by_passcode(self, passcode: str) -> Optional[Dict[str, Any]]:
        clean_code = passcode.strip().upper()
        for pid, pdata in self.profiles.items():
            if pdata.get("passcode", "").upper() == clean_code:
                return pdata
        return None

    def link_line_id(self, line_user_id: str, passcode: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Links a LINE User ID to a profile using a secret passcode (Cross-device linking)"""
        profile = self.get_profile_by_passcode(passcode)
        if not profile:
            return False, f"ไม่พบโปรไฟล์ที่มีรหัสลับ '{passcode}' ครับ กรุณาตรวจสอบรหัสผ่านอีกครั้ง", None

        # Add line_user_id if not already present
        line_ids = profile.setdefault("line_user_ids", [])
        if line_user_id not in line_ids:
            line_ids.append(line_user_id)
            profile["updated_at"] = get_bangkok_time().isoformat()
            self.line_to_profile[line_user_id] = profile["profile_id"]
            self._save()
            logger.info(f"Linked LINE ID {line_user_id} to profile {profile['profile_id']}")

        name = profile.get("name", "ท่าน")
        msg = (
            f"เชื่อมต่อข้อมูลสำเร็จครับยินดีต้อนรับกลับครับ {name}!\n"
            f"กระผมได้ดึงความทรงจำ ประวัติ และตารางกิจวัตรทั้งหมดมายังอุปกรณ์เครื่องนี้เรียบร้อยแล้วครับ "
            f"มีเรื่องไหนให้กระผมรับใช้เพิ่มเติมไหมครับ?"
        )
        return True, msg, profile

    def update_routine(self, line_user_id: str, period: str, routine_text: str) -> bool:
        profile = self.get_profile_by_line_id(line_user_id)
        if not profile:
            return False
        routines = profile.setdefault("routines", {})
        routines[period] = routine_text
        profile["updated_at"] = get_bangkok_time().isoformat()
        self._save()
        return True

    def add_note(self, line_user_id: str, note_text: str) -> bool:
        profile = self.get_profile_by_line_id(line_user_id)
        if not profile:
            return False
        notes = profile.setdefault("notes", [])
        if note_text not in notes:
            notes.append(note_text)
            profile["updated_at"] = get_bangkok_time().isoformat()
            self._save()
        return True

    def handle_quick_commands(self, line_user_id: str, text: str) -> Optional[str]:
        """Interprets explicit profile management commands (e.g., link, passcode, status)"""
        clean_text = text.strip()

        # 1. Check for passcode linking: e.g. "ยืนยันตัวตน JARVIS-PANN", "ผูกบัญชี JARVIS-PANN", "passcode: JARVIS-PANN"
        link_match = re.search(r"(?:รหัสลับ|passcode|ยืนยันตัวตน|ผูกบัญชี)[:\s]+([A-Za-z0-9\-_]+)", clean_text, re.IGNORECASE)
        if link_match:
            code = link_match.group(1)
            success, reply_msg, _ = self.link_line_id(line_user_id, code)
            return reply_msg

        # 2. Check for profile status query: "โปรไฟล์ของผม", "ดูข้อมูลของผม", "my profile"
        if clean_text.lower() in ["โปรไฟล์ของผม", "ดูโปรไฟล์", "ข้อมูลของผม", "my profile", "เช็คโปรไฟล์"]:
            profile = self.get_profile_by_line_id(line_user_id)
            if not profile:
                return (
                    "ยังไม่มีการเชื่อมต่อโปรไฟล์กับบัญชี LINE นี้ครับ\n"
                    "หากคุณมีรหัสลับยืนยันตัวตนเดิม พิมพ์:\n"
                    "`ยืนยันตัวตน <รหัสลับ>` (เช่น `ยืนยันตัวตน JARVIS-PANN`)\n"
                    "เพื่อดึงความทรงจำข้ามเครื่องมาเชื่อมต่อได้ทันทีครับ"
                )
            name = profile.get("name", "ไม่ระบุ")
            code = profile.get("passcode", "-")
            routines = profile.get("routines", {})
            r_evening = routines.get("evening", "ไม่มี")
            r_morning = routines.get("morning", "ไม่มี")
            notes = "\n".join(f"- {n}" for n in profile.get("notes", [])) or "- ไม่มี"

            return (
                f"👤 [ข้อมูลโปรไฟล์ของคุณ]\n"
                f"• ชื่อที่เรียก: {name}\n"
                f"• รหัสยืนยันตัวตนข้ามเครื่อง: {code}\n"
                f"• กิจวัตรตอนเช้า: {r_morning}\n"
                f"• กิจวัตรตอนเย็น: {r_evening}\n"
                f"• ข้อมูลสำคัญที่บันทึกไว้:\n{notes}\n\n"
                f"💡 คุณสามารถแจ้งให้ผมเปลี่ยนชื่อ หรือแก้ไขกิจวัตรได้ตลอดเวลาครับ"
            )

        return None

    def get_context_for_prompt(self, line_user_id: str) -> str:
        """Constructs personalized time-aware context to be injected into Gemini system instructions"""
        period_key, period_desc = get_time_period()
        profile = self.get_profile_by_line_id(line_user_id)

        if not profile:
            # If not yet linked, check if there's only 1 default profile (e.g. Pann) in 1-on-1 private chat
            # Automatically associate the first active line_user_id with the primary profile if empty!
            if "pann" in self.profiles and not self.profiles["pann"].get("line_user_ids"):
                self.link_line_id(line_user_id, "JARVIS-PANN")
                profile = self.profiles["pann"]

        if not profile:
            return (
                f"\n[บริบทช่วงเวลาปัจจุบัน]:\n"
                f"- ขณะนี้เป็น {period_desc}\n"
                f"- ผู้ใช้ยังไม่ได้ระบุชื่อหรือผูกรหัสโปรไฟล์ ให้ทักทายอย่างสุภาพและเป็นมิตร"
            )

        name = profile.get("name", "ท่าน")
        routines = profile.get("routines", {})
        current_routine = routines.get(period_key, "")
        notes_list = profile.get("notes", [])
        notes_str = "\n".join(f"  * {n}" for n in notes_list) if notes_list else "  * ไม่มี"

        routine_instruction = ""
        if current_routine:
            routine_instruction = (
                f"- กิจวัตรที่ต้องดูแลใน{period_desc}: \"{current_routine}\"\n"
                f"  -> คำสั่ง: ในการตอบข้อความ ให้กล่าวทักทายตามช่วงเวลาอย่างสุภาพ และสอดแทรกการเตือนกิจวัตรนี้อย่างเป็นธรรมชาติ (เช่น ถามสารทุกข์สุกดิบ และเตือนอย่าลืมกินยาตอนเย็น)"
            )
        else:
            routine_instruction = f"- ไม่มีกิจวัตรพิเศษที่ต้องเตือนใน{period_desc}"

        return (
            f"\n[ข้อมูลโปรไฟล์และบริบทเวลาของผู้ใช้]:\n"
            f"- ชื่อผู้ใช้: {name} (ต้องเรียกผู้ใช้ด้วยชื่อนี้อย่างสุภาพ เช่น 'คุณ {name}' หรือ 'ท่าน')\n"
            f"- ช่วงเวลาปัจจุบัน: {period_desc}\n"
            f"{routine_instruction}\n"
            f"- สิ่งสำคัญที่ผู้ใช้เคยแจ้งให้จำ:\n{notes_str}\n"
            f"- หากผู้ใช้บอกให้เปลี่ยนชื่อ หรือบอกกิจวัตรใหม่ ให้รับทราบและยืนยันอย่างสุภาพเสมอ"
        )

    def get_proactive_push_recipients(self, period: str) -> List[Tuple[str, str, str]]:
        """Returns list of (line_user_id, user_name, routine_text) for proactive scheduled alerts"""
        recipients = []
        for pid, pdata in self.profiles.items():
            routine = pdata.get("routines", {}).get(period)
            if routine:
                name = pdata.get("name", "ท่าน")
                for uid in pdata.get("line_user_ids", []):
                    recipients.append((uid, name, routine))
        return recipients

# Global singleton instance
profile_manager = ProfileManager()
