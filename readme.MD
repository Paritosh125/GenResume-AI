# 🤖📄 GenResume AI  
**AI-Powered Resume Builder & ATS Analyzer**

GenResume AI is a smart, ATS-focused resume builder that converts raw user input into clean, professional resumes and provides AI-based ATS score predictions with actionable improvement suggestions.  
The goal is to simplify resume creation while keeping it **ATS-friendly, fast, and beginner-friendly**.

---

## ✨ Features

- 📄 **ATS-Friendly Resume Templates**  
  Carefully designed templates optimized for Applicant Tracking Systems

- ✍️ **AI Resume Content Enhancement**  
  Converts raw, unstructured input into professional resume language

- 👀 **Live Resume Preview**  
  Instantly preview resumes before downloading

- 📊 **ATS Score Prediction**  
  AI-based resume evaluation against a selected job role

- 🧠 **Actionable Improvement Suggestions**  
  Clear, role-specific recommendations to improve ATS compatibility

- 📥 **PDF Resume Export**  
  Download resumes in clean, printable PDF format

- 🧪 **Input Validation**  
  Prevents empty or incorrect submissions for better UX

---

## 🛠 Tech Stack

### Frontend
- HTML5  
- CSS3  
- Vanilla JavaScript  

### Backend
- Python (Flask)  
- Hugging Face Inference API  
- LLaMA 3.1 Instruct Model  

### Deployment
- Backend: Render (Free Tier)  
- Frontend: Vercel (Free Tier)

---

## 🧩 System Overview

1. User selects an ATS-friendly resume template  
2. User enters raw resume details  
3. AI restructures and enhances the content  
4. Resume preview is generated  
5. User downloads resume as PDF  
6. User optionally checks ATS score  
7. AI provides score and improvement suggestions  

---

## 📂 Project Structure

```text
GenResume-AI/
│
├── backend/
│   ├── server.py
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── index.html
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── app.js
│   ├── templates/
│   └── assets/
```

---

## ⚙️ Setup Instructions (Local)

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/Paritosh125/genresume-ai.git
cd genresume-ai
```

### 2️⃣ Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

Create a `.env` file:

```env
HUGGINGFACE_API_KEY=your_api_key_here
```

Run the backend:

```bash
python server.py
```

Backend runs on:

```
http://localhost:10000
```

---

### 3️⃣ Frontend Setup

- Open `frontend/index.html` directly in the browser  
  **OR**
- Deploy using Vercel

---

## 🌐 Live Demo

- **Backend Health Endpoint**  
  https://genresume-ai.onrender.com/health

- **Frontend**  
  https://gen-resume-ai.vercel.app/

---

## ⚠️ Disclaimer

> **Note:** ATS scores shown are AI-generated predictions and may differ from actual ATS systems used by companies.

---

## 🚀 Future Scope

- More categorized resume templates  
- Resume tone selection (formal, professional, creative)  
- Role-based resume optimization  
- Portfolio website generation  
- Support for non-technical job profiles  
- Additional export formats (DOCX, TXT)  
- User accounts and resume history  

---

## 📚 References

- Hugging Face Inference API  
- Meta LLaMA 3.1  
- Flask Documentation  
- ATS Resume Best Practices  

---

## 🙌 Acknowledgements

- Hugging Face for AI inference APIs  
- Open-source community for tools and inspiration  

---

## 📬 Author

**Paritosh Sandhan**  
Internship Project – AI Resume Builder  
Tech Focus: AI + Web Development  
