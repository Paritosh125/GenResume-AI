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
- 4-6 lines maximum
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

Rewrite the following project description into a strong, resume-ready 2-3 concise lines.

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
in 2-3 concise lines.

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


# ================================================================
# JOB ROLE VALIDATION
# ================================================================

_NON_JOB_WORDS = {
    "cat", "dog", "fish", "bird", "cow", "pig", "rat", "hen", "fox",
    "lion", "bear", "wolf", "duck", "frog", "deer", "goat", "lamb",
    "mule", "pony", "crab", "slug", "worm", "bee", "ant", "fly",
    "pizza", "bread", "cake", "rice", "milk", "beer", "wine", "cola",
    "red", "blue", "green", "black", "white", "pink", "grey", "gray",
    "hello", "world", "test", "demo", "sample", "foo", "bar", "baz",
    "nothing", "nobody", "noone", "none", "null", "void", "undefined",
    "asdf", "qwer", "zxcv", "qwerty", "asdfgh", "zxcvbn",
    "asd", "aasd", "aasddas", "testtest", "abcd", "abcde", "xyz", "xyzabc",
}

_JOB_KEYWORDS = {
    "developer", "engineer", "manager", "designer", "analyst",
    "intern", "frontend", "backend", "fullstack", "devops",
    "data", "software", "web", "mobile", "product", "qa",
    "cloud", "security", "mern", "react", "node", "android", "ios",
    "architect", "lead", "senior", "junior", "associate", "consultant",
    "specialist", "coordinator", "director", "officer", "administrator",
    "technician", "scientist", "researcher", "programmer", "coder",
    "ui", "ux", "sre", "ml", "ai", "nlp", "embedded", "blockchain",
    "cyber", "network", "database", "dba", "scrum", "agile",
    "hr", "finance", "marketing", "sales", "content", "writer",
    "editor", "illustrator",
}


def _has_excessive_consonants(token):
    vowels = set("aeiou")
    run = 0
    for ch in token.lower():
        if ch.isalpha():
            if ch in vowels:
                run = 0
            else:
                run += 1
                if run >= 4:
                    return True
    return False


def _is_gibberish_token(token):
    t = token.lower()
    if len(t) < 2:
        return True
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return True
    vowels = sum(1 for c in letters if c in "aeiou")
    vowel_ratio = vowels / len(letters)
    if vowel_ratio < 0.20 and len(t) <= 6:
        return True
    if re.search(r"(.)\1\1", t):
        return True
    if _has_excessive_consonants(t):
        return True
    return False


def validate_job_role(role):
    """Returns (is_valid: bool, reason: str). reason is '' when valid."""
    r = role.strip()

    if not r:
        return False, "Job role cannot be empty."
    if len(r) < 3:
        return False, "Job role is too short. Try something like 'Frontend Developer'."
    if len(r) > 120:
        return False, "Job role is too long. Please keep it under 120 characters."
    if not re.search(r"[A-Za-z]", r):
        return False, "Job role must contain alphabetic characters."

    tokens = re.findall(r"[A-Za-z]{2,}", r.lower())
    if not tokens:
        return False, "Job role appears to contain no recognisable words."

    for tok in tokens:
        if tok in _NON_JOB_WORDS:
            return False, (
                '"{}" does not look like a job role. '
                "Try something like 'Software Engineer' or 'Data Analyst'.".format(tok)
            )

    if all(_is_gibberish_token(t) for t in tokens):
        return False, (
            "Job role appears to be random text. "
            "Try something like 'Backend Developer' or 'Product Manager'."
        )

    if any(tok in _JOB_KEYWORDS for tok in tokens):
        return True, ""

    meaningful = [t for t in tokens if len(t) >= 3 and not _is_gibberish_token(t)]
    if len(meaningful) >= 2:
        return True, ""
    if len(meaningful) == 1 and len(meaningful[0]) >= 5:
        return True, ""

    return False, (
        "Job role looks too vague or unrecognised. "
        "Try examples like 'Frontend Developer', 'Software Engineer', or 'Data Analyst'."
    )


# ================================================================
# ARTIFACT / GARBAGE TEXT DETECTION
# ================================================================

_EXACT_ARTIFACT_PATTERNS = [
    r"lorem ipsum",
    r"untitled design",
    r"placeholder",
    r"click to edit",
    r"your text here",
    r"insert your",
    r"dummy text",
    r"replace this",
    r"sample text",
    r"edit this",
    r"type here",
    r"add your",
]

_BASE64_LIKE   = re.compile(r"[A-Za-z0-9+/]{30,}={0,2}")
_CSS_HEX       = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_EMBEDDED_URL  = re.compile(r"https?://\S+")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_ZERO_WIDTH    = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")


def _count_garbage_tokens(text):
    clean = _CONTROL_CHARS.sub(" ", _ZERO_WIDTH.sub("", text))
    words = re.findall(r"\S+", clean)
    total_words = len(words)
    if total_words == 0:
        return {"total_words": 0, "garbage_ratio": 1.0, "signals": ["empty"]}

    signals = []

    for pat in _EXACT_ARTIFACT_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            signals.append("exact_phrase:{}".format(pat))

    b64_hits = len(_BASE64_LIKE.findall(clean))
    if b64_hits > 0:
        signals.append("base64_blobs:{}".format(b64_hits))

    css_hits = len(_CSS_HEX.findall(clean))
    if css_hits > 2:
        signals.append("css_hex:{}".format(css_hits))

    ctrl_count = len(_CONTROL_CHARS.findall(text))
    if ctrl_count > 5:
        signals.append("control_chars:{}".format(ctrl_count))

    zw_count = len(_ZERO_WIDTH.findall(text))
    if zw_count > 3:
        signals.append("zero_width_chars:{}".format(zw_count))

    url_hits = len(_EMBEDDED_URL.findall(clean))
    if url_hits > 2:
        signals.append("embedded_urls:{}".format(url_hits))

    garbage_token_count = 0
    for w in words:
        stripped = re.sub(r"[^A-Za-z0-9]", "", w)
        if len(stripped) == 0:
            continue
        if stripped.isdigit():
            continue
        if stripped.isalpha() and len(stripped) <= 20:
            continue
        if len(stripped) > 12 and re.search(r"\d", stripped) and re.search(r"[A-Za-z]", stripped):
            garbage_token_count += 1
        if len(w) > 40:
            garbage_token_count += 1

    garbage_ratio = garbage_token_count / total_words
    if garbage_ratio > 0.08:
        signals.append("high_garbage_token_ratio:{:.2f}".format(garbage_ratio))

    alpha_words = [w.lower() for w in words if re.sub(r"[^A-Za-z]", "", w)]
    if len(alpha_words) > 20:
        unique_ratio = len(set(alpha_words)) / len(alpha_words)
        if unique_ratio < 0.35:
            signals.append("low_lexical_density:{:.2f}".format(unique_ratio))

    non_ascii = sum(1 for c in text if ord(c) > 127)
    non_ascii_ratio = non_ascii / max(len(text), 1)
    if non_ascii_ratio > 0.15:
        signals.append("high_non_ascii:{:.2f}".format(non_ascii_ratio))

    return {"total_words": total_words, "garbage_ratio": garbage_ratio, "signals": signals}


def detect_artifacts(text):
    """Returns (artifact_detected: bool, signals: list)."""
    result = _count_garbage_tokens(text)
    signals = result["signals"]
    return len(signals) > 0, signals


# ================================================================
# RESUME STRUCTURE SANITY CHECK
# ================================================================

_RESUME_SIGNALS = [
    "education", "experience", "skills", "project",
    "internship", "university", "bachelor", "contact",
    "work", "employment", "certification", "achievement",
    "summary", "objective", "profile",
]


def is_plausible_resume(text):
    lower = text.lower()
    hits = sum(1 for sig in _RESUME_SIGNALS if sig in lower)
    return hits >= 2


# ================================================================
# SAFE JSON PARSING FROM LLM OUTPUT
# ================================================================

def safe_parse_llm_json(content):
    """
    Extract a JSON object from LLM output that may contain prose or fences.
    Coerces ats_score from string to int if the LLM returns "74" instead of 74.
    Returns a dict on success, or None on failure.
    """
    content = content.strip()
    content = re.sub(r"```(?:json)?", "", content).strip()

    result = None
    try:
        result = json.loads(content)
    except Exception:
        pass

    if result is None:
        match = re.search(r"(\{[\s\S]*\})", content)
        if match:
            try:
                result = json.loads(match.group(1))
            except Exception:
                pass

    if result is None:
        return None

    # Coerce ats_score if returned as a string e.g. "74" or "74.0"
    raw_score = result.get("ats_score")
    if isinstance(raw_score, str):
        try:
            result["ats_score"] = int(float(raw_score))
        except (ValueError, TypeError):
            return None

    return result


def _safe_score(result):
    """
    Extract, coerce, and clamp ats_score to [0, 100].
    Returns an int or None if missing/invalid.
    """
    if result is None:
        return None
    raw = result.get("ats_score")
    if raw is None:
        return None
    try:
        return max(0, min(100, int(float(raw))))
    except (ValueError, TypeError):
        return None


# ================================================================
# ATS ENDPOINT — AI-generated resume text
# ================================================================

@app.route("/ai/ats", methods=["POST"])
def ats():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            "status": "error",
            "error_code": "BAD_REQUEST",
            "message": "Invalid request body."
        }), 400

    job_role    = (data.get("jobRole")    or "").strip()
    resume_text = (data.get("resumeText") or "").strip()

    valid, reason = validate_job_role(job_role)
    if not valid:
        return jsonify({
            "status": "error",
            "error_code": "INVALID_JOB_ROLE",
            "message": reason
        }), 400

    if not resume_text or len(resume_text) < 50:
        return jsonify({
            "status": "error",
            "error_code": "EMPTY_RESUME",
            "message": "Resume text is too short or empty. Please generate your resume first."
        }), 400

    prompt = (
        'You are an ATS resume evaluator.\n\n'
        'Analyze the resume against the job role: "{}"\n\n'
        'Return STRICT JSON ONLY — no explanation, no markdown, no preamble:\n'
        '{{\n'
        '  "ats_score": <integer 0-100>,\n'
        '  "suggestions": [\n'
        '    {{"title": "Short improvement title", '
        '"detail": "Clear actionable suggestion. Do NOT invent skills or facts not in the resume."}}\n'
        '  ]\n'
        '}}\n\n'
        'Resume:\n{}'
    ).format(job_role, resume_text)

    try:
        completion = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct:novita",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        content = completion.choices[0].message.content.strip()
        result  = safe_parse_llm_json(content)
        score   = _safe_score(result)

        if result is None or score is None:
            return jsonify({
                "status": "error",
                "error_code": "AI_PARSE_FAILURE",
                "message": "AI returned an unexpected response. Please try again."
            }), 500

        return jsonify({
            "status": "ok",
            "ats_score": score,
            "warnings": [],
            "suggestions": result.get("suggestions") or [],
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "error_code": "AI_FAILURE",
            "message": "AI analysis failed. Please try again.",
            "details": str(e)
        }), 500


# ================================================================
# ATS ENDPOINT — PDF upload
# ================================================================

@app.route("/ai/ats-upload", methods=["POST"])
def ats_upload():
    file = request.files.get("resume")
    job_role = (request.form.get("jobRole") or "").strip()

    if not file or not job_role:
        return jsonify({
            "status": "error",
            "error": "invalid_input",
            "message": "Missing resume file or job role"
        }), 400

    # ---------------- JOB ROLE VALIDATION ----------------
    if len(job_role) < 3 or not any(c.isalpha() for c in job_role):
        return jsonify({
            "status": "error",
            "error": "invalid_job_role",
            "message": "Please enter a valid job role (e.g., Software Engineer)"
        }), 400

    # ---------------- PDF CHECK ----------------
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({
            "status": "error",
            "error": "invalid_file",
            "message": "Only PDF files are allowed"
        }), 400

    try:
        import pdfplumber

        with pdfplumber.open(file.stream) as pdf:
            resume_text = ""
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    resume_text += text

        resume_text = resume_text.strip()

        # ❌ IMAGE-BASED PDF
        if not resume_text:
            return jsonify({
                "status": "error",
                "error": "image_pdf",
                "message": "This PDF appears to be image-based or scanned.",
                "fix": [
                    "Export from Word or Google Docs",
                    "Avoid scanned resumes",
                    "Ensure text is selectable"
                ]
            }), 400

        # ---------------- TEMPLATE DETECTION ----------------
        warnings = []

        import re
        if re.search(r"lorem|ipsum|placeholder|dummy", resume_text, re.I):
            warnings.append({
                "type": "template",
                "title": "Hidden template text detected",
                "detail": "Your resume contains hidden placeholder text that ATS can read.",
                "fix": [
                    "Remove template text in Canva/Word",
                    "Re-export clean PDF"
                ]
            })

        # ---------------- AI CALL ----------------
        prompt = f"""
Analyze this resume for ATS score for job role: {job_role}

Return JSON:
{{
 "ats_score": number,
 "suggestions": [{{"title": "...", "detail": "..."}}]
}}

Resume:
{resume_text}
"""

        completion = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct:novita",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        import json
        content = completion.choices[0].message.content.strip()

        try:
            result = json.loads(content)
        except:
            return jsonify({
                "status": "error",
                "error": "ai_parse_error",
                "message": "AI response invalid"
            }), 500

        return jsonify({
            "status": "success",
            "ats_score": result.get("ats_score", 70),
            "suggestions": result.get("suggestions", []),
            "warnings": warnings
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": "server_error",
            "message": str(e)
        }), 500

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
