# 📚 ProjectJarvis - Knowledge Management (KM) Base

เอกสารชุดนี้จัดทำขึ้นเพื่อรวบรวม **องค์ความรู้ (Knowledge), ทักษะทางเทคนิค (Skills), ข้อกำหนด (Specifications), สถาปัตยกรรม (Architecture) และบทเรียนสำคัญ (Lessons Learned)** ทั้งหมดในการพัฒนา **ProjectJarvis** เพื่อให้เจ้าของโปรเจกต์และ AI Agent ในอนาคตสามารถอ่านและต่อยอดการพัฒนาได้อย่างต่อเนื่อง ไร้รอยต่อ

---

## 📑 สารบัญเอกสาร (Documentation Sitemap)

| ลำดับ | ไฟล์เอกสาร | คำอธิบายเนื้อหา |
| :---: | :--- | :--- |
| **01** | [`01_Architecture_and_Design.md`](01_Architecture_and_Design.md) | ภาพรวมสถาปัตยกรรมระบบ, Data Flow, Zero-Cost Stack, และลำดับการทำงาน (Sequence Diagram) |
| **02** | [`02_LINE_Messaging_API_Guide.md`](02_LINE_Messaging_API_Guide.md) | การเชื่อมต่อ LINE Messaging API, Webhook Verification, การจัดการกลุ่ม (Group Mentions), และ Animation |
| **03** | [`03_Gemini_AI_Agent_Engineering.md`](03_Gemini_AI_Agent_Engineering.md) | วิศวกรรม AI Agent ด้วย Google GenAI SDK, Google Search Grounding, Dynamic Real-time Date, และ Multi-Model Fallback |
| **04** | [`04_Deployment_and_Operations.md`](04_Deployment_and_Operations.md) | การรันระบบทั้งแบบ Local Development (Ngrok) และ Cloud 24/7 (Render), วงจร Auto-Deploy CI/CD |
| **05** | [`05_Troubleshooting_and_Lessons_Learned.md`](05_Troubleshooting_and_Lessons_Learned.md) | รวมปัญหาที่เคยพบ สาเหตุ และวิธีแก้ (เช่น Quota 429, Python 3.9 venv, Folder Rename) เพื่อเป็นภูมิคุ้มกันในการพัฒนา |

---

## 🎯 ปรัชญาและข้อกำหนดหลักของโปรเจกต์ (Core Philosophy & Constraints)

1. **Zero-Cost First (ฟรี 100% เสมอ)**:
   - ไม่ใช้บริการที่ก่อให้เกิดค่าใช้จ่ายแอบแฝง
   - ใช้ LINE Messaging API (โควตา Reply Message ฟรี ไม่คิดโควตาส่งออก)
   - ใช้ Google Gemini API (Free Tier โควตาสูง)
   - โฮสต์บน Render.com (Free Web Service)
2. **High Reliability & Resilience (ความเสถียรและทนทาน)**:
   - มีระบบ Multi-Model Fallback เมื่อโมเดลใดโมเดลหนึ่งเต็มหรือมีปัญหา
   - ระบบกักเก็บ Context บทสนทนายังคงอยู่ข้ามโมเดล
3. **Natural & Grounded Personality**:
   - บุคลิกสุภาพ เฉลียวฉลาด คล่องแคล่วแบบ Jarvis
   - สลับภาษาไทย/อังกฤษตามภาษาที่ผู้ใช้สื่อสาร
   - สืบค้นข้อมูลสดใหม่ผ่าน Google Search Grounding เสมอเมื่อถามเรื่องปัจจุบัน/ข่าวสาร
