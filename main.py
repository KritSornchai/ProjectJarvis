import os
import sys
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    ShowLoadingAnimationRequest,
)

from agent import AgentManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_ACCESS_TOKEN:
    logger.warning("LINE credentials are not fully set in .env")

if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY is not set in .env")

# Initialize LINE parser & API configuration
parser = WebhookParser(LINE_CHANNEL_SECRET)
line_configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

# Initialize AI Agent Manager
agent = AgentManager(api_key=GEMINI_API_KEY, model_name=MODEL_NAME) if GEMINI_API_KEY else None

app = FastAPI(title="ProjectJarvis", version="1.0.0")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "agent": "Jarvis",
        "webhook_endpoint": "/callback"
    }

import re

def clean_mention_text(text: str) -> str:
    """Removes @Jarvis / @จาร์วิส prefix or mentions from the message text"""
    cleaned = re.sub(r"@?(jarvis|จาร์วิส)[:,\s]*", "", text, flags=re.IGNORECASE).strip()
    return cleaned if cleaned else "สวัสดีครับ"

async def process_message_event(event: MessageEvent):
    """Handles incoming message event asynchronously"""
    source_type = event.source.type  # 'user', 'group', or 'room'
    user_id = getattr(event.source, "user_id", "unknown")
    reply_token = event.reply_token
    user_text = event.message.text.strip()

    # Determine session ID and whether Jarvis should respond
    if source_type in ["group", "room"]:
        session_id = getattr(event.source, "group_id", None) or getattr(event.source, "room_id", None) or user_id

        # 1. Check if the bot was mentioned officially via LINE native Mention
        is_mentioned = False
        if hasattr(event.message, "mention") and event.message.mention:
            for mentionee in event.message.mention.mentionees:
                if getattr(mentionee, "is_self", False):
                    is_mentioned = True
                    break

        # 2. Check if user typed @Jarvis, @จาร์วิส, or started with Jarvis
        lower_text = user_text.lower()
        if "@jarvis" in lower_text or "@จาร์วิส" in lower_text or lower_text.startswith("jarvis"):
            is_mentioned = True

        # In a group or room, ignore messages that don't tag or mention Jarvis
        if not is_mentioned:
            logger.debug(f"Ignored group message (not mentioned): {user_text}")
            return

        # Clean the @Jarvis tag from prompt
        prompt_text = clean_mention_text(user_text)
    else:
        # In 1-on-1 private chat, always respond
        session_id = user_id
        prompt_text = user_text

    logger.info(f"Processing message for session {session_id} (source: {source_type}): {prompt_text}")

    with ApiClient(line_configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        # 1. Show loading animation only in 1-on-1 chats (LINE does not support it for group chats)
        if source_type == "user":
            try:
                line_bot_api.show_loading_animation(
                    ShowLoadingAnimationRequest(
                        chatId=user_id,
                        loadingSeconds=20
                    )
                )
            except Exception as e:
                logger.warning(f"Could not trigger loading animation: {e}")

        # 2. Get AI Agent response
        if agent is None:
            reply_text = "ขออภัยครับ ยังไม่ได้ตั้งค่า GEMINI_API_KEY ในระบบ กรุณาตรวจสอบไฟล์ .env ครับ"
        else:
            try:
                reply_text = await agent.get_response(user_id=session_id, message_text=prompt_text)
            except Exception as e:
                logger.error(f"Error generating AI response: {e}")
                reply_text = "ขออภัยครับ Jarvis ไม่สามารถประมวลผลข้อความนี้ได้ในขณะนี้"

        # 3. Reply back to LINE
        try:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    replyToken=reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
            logger.info(f"Replied to {session_id} successfully.")
        except Exception as e:
            logger.error(f"Error replying message: {e}")

@app.post("/callback")
async def callback(request: Request, background_tasks: BackgroundTasks):
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid LINE signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Error parsing LINE webhook: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            # Process in background task so webhook responds 200 OK immediately to LINE
            background_tasks.add_task(process_message_event, event)

    return JSONResponse(content={"status": "OK"})
