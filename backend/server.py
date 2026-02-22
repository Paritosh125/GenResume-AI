from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
import pdfplumber
import os
import json
import re

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

    # (unchanged prompt branches)
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
        return jsonify({"error": "AI failure", "details": str(e)}), 500
    
# 
import re
import json
import pdfplumber
from flask import request, jsonify

@app.route("/ai/ats-upload", methods=["POST"])
def ats_upload():

    file = request.files.get("resume")
    job_role = (request.form.get("jobRole") or "").strip()

    if not file or not job_role:
        return jsonify({
            "error": "Invalid input",
            "detail": "Missing resume file or job role"
        }), 400

    # ==========================================================
    # 🔒 STRONG JOB ROLE VALIDATION
    # ==========================================================

    def is_gibberish(text: str) -> bool:
        letters = re.findall(r"[A-Za-z]", text)
        if not letters:
            return True

        vowels = sum(1 for c in letters if c.lower() in "aeiou")
        vowel_ratio = vowels / len(letters)

        tokens = re.findall(r"[A-Za-z]{2,}", text.lower())

        # Too few vowels + short tokens → likely nonsense
        if vowel_ratio < 0.25 and all(len(t) < 4 for t in tokens):
            return True

        # Repeated characters like "aaaa", "xxxx"
        if re.search(r"(.)\1\1", text):
            return True

        return False


    def is_valid_job_role(role: str):
        r = role.strip()

        if not re.search(r"[A-Za-z]", r):
            return False, "Job role must contain alphabetic characters."

        tokens = re.findall(r"[A-Za-z]{2,}", r.lower())

        if not tokens:
            return False, "Invalid job role."

        blacklist = {
            "asd", "asdf", "aasd", "aasddas",
            "qwe", "qwerty", "xyz", "testtest"
        }

        if any(tok in blacklist for tok in tokens):
            return False, "Job role looks like random text."

        # Known job-related keywords
        job_keywords = {
            "developer", "engineer", "manager", "designer",
            "analyst", "intern", "frontend", "backend",
            "fullstack", "devops", "data", "software",
            "web", "mobile", "product", "qa",
            "cloud", "security", "mern", "react",
            "node", "android", "ios", "architect"
        }

        if any(tok in job_keywords for tok in tokens):
            return True, ""

        meaningful = [t for t in tokens if len(t) >= 3]

        if len(meaningful) >= 2:
            return True, ""

        if len(meaningful) == 1 and len(meaningful[0]) >= 5:
            return True, ""

        if is_gibberish(r):
            return False, "Job role appears to be gibberish."

        return False, (
            "Job role looks vague. Try examples like "
            "'Frontend Developer', 'Software Engineer', or 'Data Analyst'."
        )

    valid, reason = is_valid_job_role(job_role)
    if not valid:
        return jsonify({
            "error": "Invalid job role",
            "detail": reason
        }), 400

    # ==========================================================
    # 📄 PDF VALIDATION
    # ==========================================================

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are allowed."}), 400

    try:
        with pdfplumber.open(file.stream) as pdf:
            resume_text = ""
            for page in pdf.pages:
                resume_text += page.extract_text() or ""

        resume_text = resume_text.strip()

        if not resume_text:
            return jsonify({
                "error": "This PDF appears to be image-based or scanned. "
                         "Please upload a text-based PDF."
            }), 400

        # ==========================================================
        # 🧠 BASIC RESUME SANITY CHECK
        # ==========================================================

        if len(resume_text) < 300:
            return jsonify({
                "error": "Resume content too short or invalid. "
                         "Please upload a complete resume."
            }), 400

        resume_signals = [
            "education", "experience", "skills",
            "project", "internship", "university",
            "bachelor", "contact"
        ]

        if not any(sig in resume_text.lower() for sig in resume_signals):
            return jsonify({
                "error": "Uploaded document does not appear to be a valid resume."
            }), 400

        # ==========================================================
        # ⚠ TEMPLATE / PLACEHOLDER DETECTION
        # ==========================================================

        template_patterns = [
            r"lorem ipsum",
            r"untitled design",
            r"placeholder",
            r"click to edit",
            r"your text here",
            r"insert your",
            r"dummy text",
            r"replace this"
        ]

        template_detected = any(
            re.search(pattern, resume_text, re.IGNORECASE)
            for pattern in template_patterns
        )

        # ==========================================================
        # 🤖 AI EVALUATION
        # ==========================================================

        prompt = f"""
You are an ATS resume evaluator.

Ignore placeholder/template artifacts like 'Lorem ipsum' if present.

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

        completion = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct:novita",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        content = completion.choices[0].message.content.strip()

        # Safe JSON parsing
        try:
            result = json.loads(content)
        except:
            match = re.search(r"(\{[\s\S]*\})", content)
            if match:
                result = json.loads(match.group(1))
            else:
                return jsonify({
                    "error": "AI returned invalid JSON response."
                }), 500

        # ==========================================================
        # 🔔 Integrate Template Notice into Suggestions
        # ==========================================================

        if template_detected:
            notice = {
                "title": "Hidden template text detected",
                "detail": (
                    "Hidden placeholder text (e.g., 'Lorem ipsum') was found in your PDF. "
                    "Remove template layers and re-export a clean text-based PDF."
                )
            }

            suggestions = result.get("suggestions", [])
            if not any(
                notice["title"].lower() == s.get("title", "").lower()
                for s in suggestions
            ):
                suggestions.insert(0, notice)

            result["suggestions"] = suggestions

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": "AI processing failed.",
            "details": str(e)
        }), 500

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
