import os
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from google.genai import types

logger = logging.getLogger(__name__)

USERS_DIR = os.path.join(os.path.dirname(__file__), "data", "users")
MONGODB_URI = os.getenv("MONGODB_URI", "").strip()

def get_bangkok_time() -> datetime:
    tz_bkk = timezone(timedelta(hours=7))
    return datetime.now(tz_bkk)

def get_time_period() -> Tuple[str, str]:
    """Returns (period_key, description) based on current Bangkok hour"""
    hour = get_bangkok_time().hour
    if 5 <= hour < 12:
        return "morning", "ช่วงเช้า (เวลาเริ่มต้นวันใหม่)"
    elif 12 <= hour < 17:
        return "afternoon", "ช่วงบ่าย (เวลาทำงานและลุยภารกิจ)"
    elif 17 <= hour < 22:
        return "evening", "ช่วงเย็น/ค่ำ (เวลาอาหารเย็นและเตรียมพักผ่อน)"
    else:
        return "night", "ช่วงดึก (เวลาพักผ่อนนอนหลับ)"

class UserStorageManager:
    """
    Enterprise-grade Dual-Mode Storage:
    - Primary: MongoDB Atlas Cloud Database (Permanent, survives redeploys forever)
    - Fallback: Local JSON Files in data/users/ (Zero config, local development)
    """
    def __init__(self, users_dir: str = USERS_DIR, mongodb_uri: str = MONGODB_URI):
        self.users_dir = users_dir
        os.makedirs(self.users_dir, exist_ok=True)
        self.use_mongo = False
        self.mongo_client = None
        self.db = None
        self.collection = None

        if mongodb_uri:
            try:
                from pymongo import MongoClient
                self.mongo_client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=4000)
                # Verify connection
                self.mongo_client.admin.command('ping')
                self.db = self.mongo_client["project_jarvis"]
                self.collection = self.db["users"]
                self.collection.create_index("user_id", unique=True)
                self.use_mongo = True
                logger.info("Connected to MongoDB Atlas Cloud Database successfully (Enterprise Mode)")
                self._migrate_local_files_to_mongo()
            except Exception as e:
                logger.warning(f"Failed to connect to MongoDB Atlas ({e}). Falling back to local file storage.")
                self.use_mongo = False
        else:
            logger.info("MONGODB_URI not configured. Operating in Local File Storage Mode.")

        self._ensure_default_pann()

    def _ensure_default_pann(self):
        """Ensures default seed data for creator Pann is present in active storage"""
        pann_id = "Ua713f09450dfef5e75cb83df0b6b326c"
        now_iso = get_bangkok_time().isoformat()
        pann_seed = {
            "user_id": pann_id,
            "display_name": "Pann",
            "first_seen": now_iso,
            "last_seen": now_iso,
            "profile": {
                "preferred_name": "คุณ Pann",
                "passcode": "JARVIS-PANN",
                "routines": {
                    "morning": "เตรียมตัวเริ่มต้นวันใหม่ วางแผนภารกิจประจำวัน และดื่มน้ำให้เพียงพอครับ",
                    "evening": "อย่าลืมทานยาหลังอาหารเย็นเพื่อสุขภาพที่ดีของท่านครับ"
                },
                "notes": [
                    "ผู้สร้างและเจ้านายของ Jarvis",
                    "มีกิจวัตรสำคัญคือต้องทานยาตอนเย็นเป็นประจำ"
                ]
            },
            "conversations": []
        }

        if self.use_mongo:
            try:
                if not self.collection.find_one({"user_id": pann_id}):
                    self.collection.insert_one(pann_seed)
                    logger.info("Seeded Pann profile into MongoDB Atlas")
            except Exception as e:
                logger.error(f"Error seeding MongoDB: {e}")
        else:
            file_path = self._get_user_file_path(pann_id)
            if not os.path.exists(file_path):
                self._save_local_file(pann_id, pann_seed)
                logger.info(f"Initialized seed profile for Pann at {file_path}")

    def _migrate_local_files_to_mongo(self):
        """Automatically uploads any local JSON user files to MongoDB on first cloud connect"""
        if not self.use_mongo or not os.path.exists(self.users_dir):
            return
        migrated = 0
        for fname in os.listdir(self.users_dir):
            if fname.endswith(".json"):
                fpath = os.path.join(self.users_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    uid = data.get("user_id")
                    if uid and not self.collection.find_one({"user_id": uid}):
                        self.collection.insert_one(data)
                        migrated += 1
                except Exception as e:
                    logger.warning(f"Error migrating {fname} to MongoDB: {e}")
        if migrated > 0:
            logger.info(f"Migrated {migrated} local user files to MongoDB Atlas cloud database")

    def _get_user_file_path(self, user_id: str) -> str:
        safe_id = re.sub(r"[^A-Za-z0-9_\-]", "_", user_id)
        return os.path.join(self.users_dir, f"{safe_id}.json")

    def _load_local_file(self, user_id: str) -> Optional[Dict[str, Any]]:
        path = self._get_user_file_path(user_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading local user file for {user_id}: {e}")
        return None

    def _save_local_file(self, user_id: str, data: Dict[str, Any]):
        path = self._get_user_file_path(user_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving local user file for {user_id}: {e}")

    def get_or_create_user(self, user_id: str, display_name: Optional[str] = None) -> Dict[str, Any]:
        """Loads user data from MongoDB or local storage, or creates a new isolated record"""
        now_iso = get_bangkok_time().isoformat()
        effective_name = display_name if display_name else "ผู้ใช้"

        if self.use_mongo:
            try:
                user = self.collection.find_one({"user_id": user_id})
                if user is None:
                    new_user = {
                        "user_id": user_id,
                        "display_name": effective_name,
                        "first_seen": now_iso,
                        "last_seen": now_iso,
                        "profile": {
                            "preferred_name": f"คุณ {effective_name}",
                            "passcode": f"JARVIS-{user_id[-6:].upper()}",
                            "routines": {},
                            "notes": []
                        },
                        "conversations": []
                    }
                    self.collection.insert_one(new_user)
                    logger.info(f"[MongoDB] Created new user: {user_id} ({effective_name})")
                    return new_user
                else:
                    updates = {"last_seen": now_iso}
                    if display_name and user.get("display_name") in ["ผู้ใช้", "unknown", None]:
                        updates["display_name"] = display_name
                        if user.get("profile", {}).get("preferred_name") in ["คุณ ผู้ใช้", "ท่าน"]:
                            updates["profile.preferred_name"] = f"คุณ {display_name}"
                    self.collection.update_one({"user_id": user_id}, {"$set": updates})
                    user.update(updates)
                    return user
            except Exception as e:
                logger.error(f"MongoDB get_or_create_user error: {e}")

        # Local File Storage Fallback
        data = self._load_local_file(user_id)
        if data is None:
            data = {
                "user_id": user_id,
                "display_name": effective_name,
                "first_seen": now_iso,
                "last_seen": now_iso,
                "profile": {
                    "preferred_name": f"คุณ {effective_name}",
                    "passcode": f"JARVIS-{user_id[-6:].upper()}",
                    "routines": {},
                    "notes": []
                },
                "conversations": []
            }
            self._save_local_file(user_id, data)
            logger.info(f"[LocalFile] Created new user: {user_id} ({effective_name})")
        else:
            data["last_seen"] = now_iso
            if display_name and data.get("display_name") in ["ผู้ใช้", "unknown", None]:
                data["display_name"] = display_name
                if data.get("profile", {}).get("preferred_name") in ["คุณ ผู้ใช้", "ท่าน"]:
                    data["profile"]["preferred_name"] = f"คุณ {display_name}"
            self._save_local_file(user_id, data)
        return data

    def append_conversation(self, user_id: str, role: str, message: str, max_stored: int = 100):
        """Appends conversation turn atomically to MongoDB or local JSON file"""
        turn = {
            "timestamp": get_bangkok_time().strftime("%d/%m/%Y %H:%M:%S"),
            "role": role,
            "message": message
        }

        if self.use_mongo:
            try:
                self.collection.update_one(
                    {"user_id": user_id},
                    {
                        "$push": {
                            "conversations": {
                                "$each": [turn],
                                "$slice": -max_stored
                            }
                        },
                        "$set": {"last_seen": get_bangkok_time().isoformat()}
                    },
                    upsert=True
                )
                return
            except Exception as e:
                logger.error(f"MongoDB append_conversation error: {e}")

        # Local File Fallback
        data = self.get_or_create_user(user_id)
        conversations = data.setdefault("conversations", [])
        conversations.append(turn)
        if len(conversations) > max_stored:
            data["conversations"] = conversations[-max_stored:]
        self._save_local_file(user_id, data)

    def get_recent_history_contents(self, user_id: str, max_turns: int = 15) -> List[types.Content]:
        """Constructs Google GenAI Content history strictly from this user's cloud/local record"""
        convs = []
        if self.use_mongo:
            try:
                user = self.collection.find_one({"user_id": user_id}, {"conversations": {"$slice": - (max_turns * 2)}})
                if user and user.get("conversations"):
                    convs = user["conversations"]
            except Exception as e:
                logger.error(f"MongoDB get_recent_history_contents error: {e}")

        if not convs:
            data = self._load_local_file(user_id)
            if data and data.get("conversations"):
                convs = data["conversations"][- (max_turns * 2):]

        contents = []
        for c in convs:
            role = "user" if c["role"] == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=c["message"])]
                )
            )
        return contents

    def get_all_conversations_text(self, user_id: str, limit: int = 60) -> str:
        """Extracts plain text transcript of this user's conversation for summarization"""
        convs = []
        if self.use_mongo:
            try:
                user = self.collection.find_one({"user_id": user_id}, {"conversations": {"$slice": -limit}})
                if user and user.get("conversations"):
                    convs = user["conversations"]
            except Exception as e:
                logger.error(f"MongoDB get_all_conversations_text error: {e}")

        if not convs:
            data = self._load_local_file(user_id)
            if data and data.get("conversations"):
                convs = data["conversations"][-limit:]

        lines = []
        for c in convs:
            sender = "ผู้ใช้" if c["role"] == "user" else "Jarvis"
            lines.append(f"[{c.get('timestamp', '')}] {sender}: {c['message']}")
        return "\n".join(lines)

    def clear_history(self, user_id: str):
        """Clears conversation history for this specific user"""
        if self.use_mongo:
            try:
                self.collection.update_one({"user_id": user_id}, {"$set": {"conversations": []}})
                return
            except Exception as e:
                logger.error(f"MongoDB clear_history error: {e}")

        data = self.get_or_create_user(user_id)
        data["conversations"] = []
        self._save_local_file(user_id, data)

    def update_preferred_name(self, user_id: str, name: str):
        if self.use_mongo:
            try:
                self.collection.update_one({"user_id": user_id}, {"$set": {"profile.preferred_name": name}})
                return
            except Exception as e:
                logger.error(f"MongoDB update_preferred_name error: {e}")

        data = self.get_or_create_user(user_id)
        data.setdefault("profile", {})["preferred_name"] = name
        self._save_local_file(user_id, data)

    def update_routine(self, user_id: str, period: str, routine_text: str):
        if self.use_mongo:
            try:
                self.collection.update_one(
                    {"user_id": user_id},
                    {"$set": {f"profile.routines.{period}": routine_text}}
                )
                return
            except Exception as e:
                logger.error(f"MongoDB update_routine error: {e}")

        data = self.get_or_create_user(user_id)
        routines = data.setdefault("profile", {}).setdefault("routines", {})
        routines[period] = routine_text
        self._save_local_file(user_id, data)

    def add_note(self, user_id: str, note_text: str):
        if self.use_mongo:
            try:
                self.collection.update_one(
                    {"user_id": user_id},
                    {"$addToSet": {"profile.notes": note_text}}
                )
                return
            except Exception as e:
                logger.error(f"MongoDB add_note error: {e}")

        data = self.get_or_create_user(user_id)
        notes = data.setdefault("profile", {}).setdefault("notes", [])
        if note_text not in notes:
            notes.append(note_text)
            self._save_local_file(user_id, data)

    def link_passcode(self, current_user_id: str, passcode: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Finds any user record with this passcode and merges/links profile into current device"""
        clean_code = passcode.strip().upper()

        source_profile = None
        source_convs = []

        if self.use_mongo:
            try:
                src = self.collection.find_one({"profile.passcode": clean_code})
                if src:
                    source_profile = src.get("profile", {})
                    source_convs = src.get("conversations", [])
            except Exception as e:
                logger.error(f"MongoDB link_passcode error: {e}")

        if not source_profile:
            # Fallback search in local files
            for fname in os.listdir(self.users_dir):
                if fname.endswith(".json"):
                    fpath = os.path.join(self.users_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            u = json.load(f)
                            if u.get("profile", {}).get("passcode", "").upper() == clean_code:
                                source_profile = u.get("profile", {})
                                source_convs = u.get("conversations", [])
                                break
                    except Exception:
                        continue

        if not source_profile:
            return False, f"ไม่พบข้อมูลโปรไฟล์ที่มีรหัสลับ '{passcode}' ครับ กรุณาตรวจสอบรหัสอีกครั้ง", {}

        # Merge profile into current_user_id
        current_data = self.get_or_create_user(current_user_id)
        current_data["profile"] = {
            "preferred_name": source_profile.get("preferred_name", current_data["display_name"]),
            "passcode": source_profile.get("passcode", clean_code),
            "routines": source_profile.get("routines", {}),
            "notes": source_profile.get("notes", [])
        }
        if source_convs and not current_data.get("conversations"):
            current_data["conversations"] = source_convs[-20:]

        if self.use_mongo:
            try:
                self.collection.update_one(
                    {"user_id": current_user_id},
                    {"$set": {"profile": current_data["profile"], "conversations": current_data.get("conversations", [])}}
                )
            except Exception as e:
                logger.error(f"MongoDB save link_passcode error: {e}")

        self._save_local_file(current_user_id, current_data)

        name = current_data["profile"].get("preferred_name", "ท่าน")
        msg = (
            f"เชื่อมต่อข้อมูลสำเร็จครับยินดีต้อนรับกลับครับ {name}!\n"
            f"กระผมได้ดึงความทรงจำ ประวัติ และตารางกิจวัตรทั้งหมดมายังอุปกรณ์เครื่องนี้เรียบร้อยแล้วครับ "
            f"มีเรื่องไหนให้กระผมรับใช้เพิ่มเติมไหมครับ?"
        )
        return True, msg, current_data

    def handle_quick_commands(self, user_id: str, text: str) -> Optional[str]:
        """Interprets explicit profile management commands"""
        clean_text = text.strip()

        # 1. Passcode linking
        link_match = re.search(r"(?:รหัสลับ|passcode|ยืนยันตัวตน|ผูกบัญชี)[:\s]+([A-Za-z0-9\-_]+)", clean_text, re.IGNORECASE)
        if link_match:
            code = link_match.group(1)
            success, msg, _ = self.link_passcode(user_id, code)
            return msg

        # 2. View profile
        if any(k in clean_text.lower() for k in ["โปรไฟล์", "profile", "ข้อมูลของผม"]):
            data = self.get_or_create_user(user_id)
            prof = data.get("profile", {})
            name = prof.get("preferred_name", data.get("display_name", "ไม่ระบุ"))
            code = prof.get("passcode", "-")
            routines = prof.get("routines", {})
            r_morning = routines.get("morning", "ไม่มี")
            r_evening = routines.get("evening", "ไม่มี")
            notes = "\n".join(f"- {n}" for n in prof.get("notes", [])) or "- ไม่มี"
            conv_count = len(data.get("conversations", []))
            storage_type = "MongoDB Atlas Cloud (ถาวรตลอดชีพ)" if self.use_mongo else "Local Persistent File"

            return (
                f"👤 [ข้อมูลโปรไฟล์ของคุณในระบบ LINE OA]\n"
                f"• LINE User ID: `{user_id}`\n"
                f"• ชื่อที่เรียก: {name}\n"
                f"• รหัสยืนยันตัวตนข้ามเครื่อง: {code}\n"
                f"• ฐานข้อมูล: {storage_type}\n"
                f"• กิจวัตรตอนเช้า: {r_morning}\n"
                f"• กิจวัตรตอนเย็น: {r_evening}\n"
                f"• บันทึกการสนทนา: {conv_count} ข้อความล่าสุด\n"
                f"• ข้อมูลสำคัญที่บันทึกไว้:\n{notes}\n\n"
                f"💡 สามารถพิมพ์ 'สรุปบทสนทนา' เพื่อให้ผมสรุปสิ่งที่คุยกันทั้งหมดได้ครับ"
            )

        return None

    def get_context_for_prompt(self, user_id: str) -> str:
        """Builds personalized context injected into system instructions for this specific user"""
        period_key, period_desc = get_time_period()
        data = self.get_or_create_user(user_id)
        prof = data.get("profile", {})

        name = prof.get("preferred_name", data.get("display_name", "ท่าน"))
        routines = prof.get("routines", {})
        current_routine = routines.get(period_key, "")
        notes_list = prof.get("notes", [])
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
        """Returns list of (user_id, preferred_name, routine_text) across cloud and local storage"""
        recipients = []
        if self.use_mongo:
            try:
                cursor = self.collection.find({f"profile.routines.{period}": {"$exists": True, "$ne": ""}})
                for u in cursor:
                    uid = u.get("user_id")
                    routine = u.get("profile", {}).get("routines", {}).get(period)
                    name = u.get("profile", {}).get("preferred_name", u.get("display_name", "ท่าน"))
                    if uid and routine:
                        recipients.append((uid, name, routine))
                if recipients:
                    return recipients
            except Exception as e:
                logger.error(f"MongoDB get_proactive_push_recipients error: {e}")

        # Local File Fallback
        if os.path.exists(self.users_dir):
            for fname in os.listdir(self.users_dir):
                if fname.endswith(".json"):
                    fpath = os.path.join(self.users_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            u = json.load(f)
                            routine = u.get("profile", {}).get("routines", {}).get(period)
                            if routine:
                                uid = u.get("user_id")
                                name = u.get("profile", {}).get("preferred_name", u.get("display_name", "ท่าน"))
                                if uid:
                                    recipients.append((uid, name, routine))
                    except Exception as e:
                        logger.warning(f"Could not read user file {fname}: {e}")
        return recipients

# Global singleton
user_storage = UserStorageManager()
