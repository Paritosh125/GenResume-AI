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
@app.route("/ai/ats-upload", methods=["POST"])
def ats_upload():
    """
    Robust ATS upload endpoint:
    - Validates job role (stronger heuristics + gibberish detection)
    - Validates PDF presence and basic text extraction
    - Detects template/artifact placeholders and returns structured warning
    - Calls LLM only when inputs look sane
    """

    file = request.files.get("resume")
    job_role = (request.form.get("jobRole") or "").strip()

    if not file or not job_role:
        return jsonify({"error": "Invalid input", "detail": "Missing file or job role"}), 400

    # -----------------------
    # Job-role validation
    # -----------------------
    def _is_gibberish(s: str) -> bool:
        """Heuristic to detect random/gibberish strings (low vowel ratio, repeated chars)."""
        letters = re.findall(r"[A-Za-z]", s)
        if not letters:
            return True
        vowels = sum(1 for c in letters if c.lower() in "aeiou")
        vowel_ratio = vowels / len(letters)
        # if too few vowels (likely consonant mush) and tokens are short -> gibberish
        tokens = re.findall(r"[A-Za-z]{2,}", s)
        if vowel_ratio < 0.25 and all(len(t) < 4 for t in tokens):
            return True
        # repeated characters like "aaaa" or "xxx" are suspicious
        if re.search(r"(.)\1\1", s):
            return True
        return False

    def is_valid_job_role(role: str):
        """
        Returns (ok: bool, detail: str).
        Rules (heuristics):
        - Must contain alphabetic chars
        - Reject common garbage tokens
        - Accept immediately if contains known job tokens (developer, engineer, frontend, etc.)
        - Accept if has 2+ meaningful words (length>=3)
        - Accept single descriptive word length >= 5
        - Reject gibberish (low vowel_ratio, repeated chars)
        - Otherwise reject as "vague"
        """
        r = (role or "").strip()
        if not r:
            return False, "Empty job role"

        if not re.search(r"[A-Za-z]", r):
            return False, "Job role should contain alphabetic characters"

        tokenized = re.findall(r"[A-Za-z]{2,}", r.lower())
        if not tokenized:
            return False, "Job role looks invalid"

        # quick blacklist of obvious nonsense
        blacklist = {"asd", "asdf", "aasd", "aasddas", "qwe", "qwerty", "testtest", "xyz", "lorem"}
        if any(tok in blacklist for tok in tokenized):
            return False, "Job role looks like random text"

        # whitelist / job tokens
        job_tokens = {
            "developer", "engineer", "manager", "designer", "analyst", "intern",
            "frontend", "backend", "fullstack", "devops", "data", "software", "web", "mobile",
            "product", "qa", "test", "research", "administrator", "architect", "consultant",
            "security", "cloud", "mern", "react", "node", "android", "ios", "sde", "sdet", "pm"
        }
        if any(tok in job_tokens for tok in tokenized):
            return True, ""

        # meaningful words
        meaningful = [tok for tok in tokenized if len(tok) >= 3 and tok not in {"the","and","for","with","in","of"}]
        if len(meaningful) >= 2:
            return True, ""

        if len(meaningful) == 1 and len(meaningful[0]) >= 5:
            return True, ""

        # reject obvious gibberish
        if _is_gibberish(r):
            return False, "Job role looks like random or gibberish text"

        return False, ("Job role looks vague or too short. Try examples like 'Frontend Developer', "
                       "'Software Engineer', or 'Data Analyst'.")

    ok, reason = is_valid_job_role(job_role)
    if not ok:
        return jsonify({"error": "Invalid job role", "detail": reason}), 400

    # -----------------------
    # PDF check
    # -----------------------
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF allowed"}), 400

    try:
        # Extract text from PDF using the file stream (works with Flask FileStorage)
        with pdfplumber.open(file.stream) as pdf:
            resume_text = ""
            for page in pdf.pages:
                resume_text += page.extract_text() or ""

        resume_text = (resume_text or "").strip()

        if not resume_text:
            return jsonify({
                "error": "This PDF appears to be image-based or scanned. Please upload a text-based PDF (exported from Word or Google Docs)."
            }), 400

        # -----------------------
        # Basic resume sanity checks
        # -----------------------
        # Minimum length: short docs (e.g., 'cat dog') are rejected
        if len(resume_text) < 300:
            return jsonify({"error": "Resume content too short or invalid. Please upload a full resume."}), 400

        # Basic presence of resume-like keywords (helps reject non-resume PDFs)
        resume_signals = ["education", "experience", "skills", "project", "internship", "university", "bachelor", "cv", "contact"]
        if not any(sig in resume_text.lower() for sig in resume_signals):
            # don't be harsh — give helpful detail
            return jsonify({"error": "Uploaded document does not look like a resume. Please upload a resume PDF."}), 400

        # -----------------------
        # Template / placeholder detection
        # -----------------------
        template_patterns = [
            r"lorem ipsum", r"untitled design", r"placeholder", r"click to edit", r"your text here",
            r"insert your", r"sample text", r"replace this", r"dummy text"
        ]
        template_detected = False
        found_patterns = []
        for pat in template_patterns:
            if re.search(pat, resume_text, re.IGNORECASE):
                template_detected = True
                found_patterns.append(pat)

        # -----------------------
        # Call the LLM (AI) with a small instruction to ignore placeholders
        # -----------------------
        prompt = f"""
You are an ATS resume evaluator.

If the resume contains placeholder/template artifacts (e.g., 'Lorem ipsum', 'Untitled design', 'Click to edit'), ignore them when forming suggestions. Do NOT generate suggestions based solely on template placeholders.

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

        # Attempt to parse JSON from model output robustly
        try:
            result = json.loads(content)
        except Exception:
            # Try to extract JSON substring if model wrapped text
            import re as _re
            m = _re.search(r"(\{[\s\S]*\})", content)
            if m:
                try:
                    result = json.loads(m.group(1))
                except Exception:
                    return jsonify({"error": "AI returned non-JSON output", "details": "Could not parse model response"}), 500
            else:
                return jsonify({"error": "AI returned non-JSON output", "details": "Could not find JSON in model response"}), 500

        # -----------------------
        # Attach template warning if detected (frontend can render this)
        # -----------------------
        if template_detected:
            result.setdefault("template_warning", {})
            result["template_warning"]["title"] = "Hidden template or placeholder text detected"
            result["template_warning"]["detail"] = (
                "We detected template/placeholder text (e.g., 'Lorem ipsum' or 'Untitled design') inside the uploaded PDF. "
                "This text may be invisible in some editors but can be read by ATS systems and impact parsing. "
                "Recommendations: open your original design (Canva/Figma/Word), remove placeholder layers, re-export as a text-based PDF, "
                "then re-upload. You can also test by copying all text (Ctrl+A) and pasting into Notepad to see hidden content."
            )
            result["template_warning"]["found_patterns"] = found_patterns

        return jsonify(result)

    except Exception as e:
        # debugging helper (remove or sanitize for production)
        return jsonify({"error": "AI failure", "details": str(e)}), 500

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
