#!/usr/bin/env python3
"""
Health check script to verify both Local and Render Webhook endpoints.
Usage:
    python 01-ProjectKM/scripts/check_health.py
"""
import requests
import json

ENDPOINTS = [
    {"name": "Local Uvicorn Server", "url": "http://127.0.0.1:8000/"},
    {"name": "Cloud Server (Render)", "url": "https://projectjarvis-av8i.onrender.com/"},
]

print("🏥 Checking Jarvis Health Status...\n")
for ep in ENDPOINTS:
    name = ep["name"]
    url = ep["url"]
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            print(f"✅ {name}: ONLINE (HTTP 200)")
            print(f"   Response: {json.dumps(res.json(), ensure_ascii=False)}")
        else:
            print(f"⚠️ {name}: Returned HTTP {res.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"⚪ {name}: OFFLINE (Connection Refused - ไม่ได้เปิดอยู่)")
    except Exception as e:
        print(f"❌ {name}: ERROR ({e})")
    print("-" * 50)
