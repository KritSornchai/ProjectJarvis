#!/usr/bin/env python3
"""
Test script for Gemini API connection and Google Search Grounding.
Usage:
    python 01-ProjectKM/scripts/test_gemini.py
"""
import os
import sys
from dotenv import load_dotenv

# Load .env from project root
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(env_path)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ ERROR: GEMINI_API_KEY is not set in .env")
    sys.exit(1)

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("❌ ERROR: google-genai is not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

client = genai.Client(api_key=api_key)
model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

print(f"🔄 Testing Gemini connection with model: {model_name} ...")
try:
    response = client.models.generate_content(
        model=model_name,
        contents="ทดสอบระบบ: ช่วยรายงานวันที่และเวลาปัจจุบันแบบสั้นๆ 1 ประโยค",
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.7,
        )
    )
    print("✅ SUCCESS! Response received:")
    print("--------------------------------------------------")
    print(response.text.strip())
    print("--------------------------------------------------")
except Exception as e:
    print(f"❌ FAILED: {e}")
