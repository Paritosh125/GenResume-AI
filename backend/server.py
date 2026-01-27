from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
import os
import json

# ================= SETUP =================
load_dotenv()

HF_TOKEN = os.getenv("OPENAI_API_KEY")
if not HF_TOKEN:
    raise RuntimeError("OPENAI_API_KEY not found in environment variables")

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_TOKEN
)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ================= PROMPT FACTORY =================
def base_rules(tone):
    return f"""
You are a professional resume editor.

Rules:
- Improve language only
- Do NOT add new information
- Do NOT change facts
- Do NOT add headings or explanations
- Output ONLY the rewritten content
- Keep ATS-friendly
- Tone: {tone if tone else "professional"}
"""

def build_prompt(prompt_type, payload):
    base_rules = """
You are a professional ATS-focused resume editor.

STRICT RULES:
- Improve language and clarity only.
- Do NOT add new information.
- Do NOT infer, assume, or invent details.
- Do NOT add metrics, technologies, or experience unless explicitly present.
- Do NOT change facts, meaning, or intent.
- Remove emojis, slang, filler words, and irrelevant text.
- If input is weak or vague, rewrite minimally without embellishment.
- If input is already professional, make only minor grammatical improvements.
- Do NOT add headings, labels, explanations, or formatting.
- Output ONLY the final rewritten text.
- Keep output concise, professional, and ATS-friendly.
"""


    # -------- SUMMARY --------
    if prompt_type == "summary":
        return f"""
You are a professional resume writer.

Rules:
- Do NOT list or mention specific skills or technologies
- Do NOT include comma-separated tools or languages
- Do NOT invent experience, tools, companies, or metrics
- Do NOT exaggerate role or seniority
- You MAY add professional context, career focus, and learning intent
- Preserve all factual details from the user
- Keep it ATS-friendly, concise, and professional
- 4–6 lines maximum
- Output ONLY the final rewritten summary text

User summary:
{payload}
"""



    # -------- SKILLS (GROUPING LATER) --------
    if prompt_type == "skills":
        return f"""
You are a professional resume editor.

Rules:
- Strictly Organize ONLY the skills explicitly provided in the input
- Do NOT add tools as category with skill as 'git' if not provided in input
- Do NOT add any Note 
- Organize ONLY the provided skills into appropriate categories
- Strictly Do NOT add, infer, or invent any skills
- Do NOT create empty categories
- Do NOT include categories with no skills
- Ignore soft skills, hobbies, or personal traits
- Do NOT repeat skills across categories
- Classify conservatively and accurately
- Capitalize first letter of each skill

Classification guidance:
- Programming Languages: C, C++, Java, Python, JavaScript, etc.
- Frontend: HTML, CSS, JavaScript, React, etc.
- Backend: Node.js, PHP, Django, etc.
- Databases: MySQL, PostgreSQL, MongoDB, etc.
- Tools: Git, Docker, Postman, etc.
- Cloud/DevOps: AWS, Azure, CI/CD, etc.

Strict Output format (ONLY include relevant categories):
Category Name: skill1, skill2

Do not create empty categories with none value
Do not give Note if user provides irrelevant skill not according to our rules

Input skills:
{payload}
"""


    # -------- PROJECT (DESCRIPTION ONLY) --------
    if prompt_type == "project":
         return f"""{base_rules}

Rewrite the following project description into a strong, resume-ready 2–3 concise lines.

STRICT RULES:
- Improve clarity and impact only
- Do NOT add new technologies or features
- Do NOT exaggerate or invent results
- Avoid vague phrases (e.g., "worked on", "helped", "learned")
- Focus on what was built, how it was built, or what problem it solved
- Keep it ATS-optimized and technical

IMPORTANT:
- Do NOT mention the project name
- Do NOT add labels or headings
- Output ONLY the rewritten description text

Text:
{payload.get("description", "")}
"""



    # -------- EXPERIENCE --------
    if prompt_type == "experience":
        return f"""{base_rules}

Rewrite the following work experience description into clear, resume-ready language
in 2–3 concise lines.

STRICT RULES:
- Improve wording and structure only
- Do NOT add new responsibilities, tools, or achievements
- Do NOT invent metrics, impact, or leadership claims
- Avoid vague phrases (e.g., "worked on", "was responsible for")
- Focus on actual tasks, technologies, or processes mentioned
- Keep it professional and ATS-optimized

IMPORTANT:
- Do NOT add job title, company name, or duration
- Do NOT add labels or headings
- Output ONLY the rewritten description text

Text:
{payload.get("description", "")}
"""


    # -------- ACHIEVEMENT (TITLE + DESCRIPTION) --------
    if prompt_type == "achievement":
        return f"""{base_rules}

Rewrite the following achievement into ONE clear, resume-ready line.

STRICT RULES:
- Improve clarity and professionalism only
- Do NOT add rankings, numbers, scale, or impact unless explicitly mentioned
- Do NOT invent competition size, metrics, or recognition level
- Keep wording factual and concise
- Use strong but honest action verbs

IMPORTANT:
- Do NOT add headings or labels
- Output ONLY the final rewritten line

Achievement Title:
{payload.get("title", "")}

Achievement Description:
{payload.get("description", "")}
"""


    return None


# ================= AI ENDPOINT =================
@app.route("/ai/improve", methods=["POST"])
def improve():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    prompt_type = data.get("type")
    payload = data.get("payload")

    prompt = build_prompt(prompt_type, payload)
    if not prompt:
        return jsonify({"error": "Unsupported type"}), 400

    try:
        completion = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct:novita",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        output = completion.choices[0].message.content.strip()
        return jsonify({"result": output})

    except Exception as e:
        return jsonify({"error": "AI failure", "details": str(e)}), 500

# ================= HEALTH =================
@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# ================= ATS PROMPT =================
@app.route("/ai/ats", methods=["POST"])
def ats():
    data = request.json
    job_role = data.get("jobRole")
    resume_text = data.get("resumeText")

    if not job_role or not resume_text:
        return jsonify({"error": "Invalid input"}), 400

    prompt = f"""
You are an ATS resume evaluator.

Analyze the resume against the job role: "{job_role}"

Return STRICT JSON ONLY in this format:
{{
  "ats_score": number (0-100),
  "suggestions": [
    {{
      "title": "Short improvement title",
      "detail": "Clear actionable improvement suggestion"
    }}
  ]
}}

Resume:
{resume_text}
"""

    try:
        completion = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct:novita",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        content = completion.choices[0].message.content.strip()
        return jsonify(json.loads(content))

    except Exception as e:
        return jsonify({"error": "AI failure"}), 500



# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

