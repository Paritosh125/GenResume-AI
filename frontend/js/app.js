let lastGeneratedData = null;
let selectedTemplate = "simple-ats"; // default template
const generateBtn = document.getElementById("generateBtn");
const downloadBtn = document.getElementById("downloadBtn");
const downloadMenu = document.getElementById("downloadMenu");


//  EXPERIENCE 
const experienceSection = document.getElementById("experience-section");
document.getElementById("addExperienceBtn").addEventListener("click", () => {
    experienceSection.appendChild(createBlock("experience"));
});

//  EDUCATION (MANDATORY) 
const educationSection = document.getElementById("education-section");
document.getElementById("addEducationBtn").addEventListener("click", () => {
    educationSection.appendChild(createBlock("education"));
});

// Add one education block by default
educationSection.appendChild(createBlock("education"));

//  PROJECTS 
const projectSection = document.getElementById("project-section");
document.getElementById("addProjectBtn").addEventListener("click", () => {
    projectSection.appendChild(createBlock("project"));
});

//  CERTIFICATIONS 
const certificationSection = document.getElementById("certification-section");
document.getElementById("addCertificationBtn").addEventListener("click", () => {
    certificationSection.appendChild(createBlock("certification"));
});

//  ACHIEVEMENTS 
const achievementSection = document.getElementById("achievement-section");
document.getElementById("addAchievementBtn").addEventListener("click", () => {
    achievementSection.appendChild(createBlock("achievement"));
});

//  GENERATE 
generateBtn.addEventListener("click", async () => {
    clearErrors();

    if (!validateRequiredFields()) {
        // alert("Please fill all required fields.");
        return;
    }

    // ===== Button UX START =====
    generateBtn.disabled = true;
    const originalText = generateBtn.innerText;
    generateBtn.innerText = "Generating...";
    // ===== Button UX END =====

    try {
        lastGeneratedData = collectFormData();

        // -------- AI SUMMARY --------
        try {
            const summary = await callAI("summary", {
                about: lastGeneratedData.about,
                skills: lastGeneratedData.skills
            });
            if (summary) lastGeneratedData.about = summary;
        } catch {
            console.warn("AI summary failed");
        }

        // -------- AI SKILLS GROUPING --------
        try {
            const skills = await callAI("skills", {
                skills: lastGeneratedData.skills
            });
            if (skills) lastGeneratedData.skills = skills;
        } catch {
            console.warn("AI skills failed");
        }

        // -------- AI PROJECTS --------
        for (let p of lastGeneratedData.projects) {
            if (p.description) {
                try {
                    const improved = await callAI("project", p);
                    if (improved) p.description = improved;
                } catch { }
            }
        }

        // -------- AI EXPERIENCE --------
        for (let e of lastGeneratedData.experience) {
            if (e.description) {
                try {
                    const improved = await callAI("experience", e);
                    if (improved) e.description = improved;
                } catch { }
            }
        }

        // -------- AI ACHIEVEMENTS --------
        for (let a of lastGeneratedData.achievements) {
            if (a.description) {
                try {
                    const improved = await callAI("achievement", a);
                    if (improved) a.description = improved;
                } catch { }
            }
        }

        await generateResumeHTML(lastGeneratedData);
        //new change
        showATSInput();

    } finally {
        // ===== Button UX RESET =====
        generateBtn.disabled = false;
        generateBtn.innerText = originalText;
    }
});


//  VALIDATION 
function validateRequiredFields() {
    let valid = true;
    let firstInvalidInput = null;


    const fullName = document.getElementById("fullName");
    const email = document.getElementById("email");
    const phone = document.getElementById("phone");
    const about = document.getElementById("about");
    const skills = document.getElementById("skills");

    // Full Name
    if (!fullName.value.trim()) {
        showError(fullName, "Name is required");
        valid = false;
        firstInvalidInput ??= fullName;
    } else {
        hideError(fullName);
    }

    // Email
    if (!email.value.trim()) {
        showError(email, "Email is required");
        valid = false;
        firstInvalidInput ??= email;
    } else if (!email.checkValidity()) {
        showError(email, "Enter a valid email address");
        valid = false;
        firstInvalidInput ??= email;
    } else {
        hideError(email);
    }

    // Phone
    if (!phone.value.trim()) {
        showError(phone, "Phone number is required");
        valid = false;
        firstInvalidInput ??= phone;
    } else if (!/^\d{10}$/.test(phone.value.trim())) {
        showError(phone, "Phone number must be exactly 10 digits");
        valid = false;
        firstInvalidInput ??= phone;
    } else {
        hideError(phone);
    }

    // About
    if (!about.value.trim()) {
        showError(about, "Professional summary is required");
        valid = false;
        firstInvalidInput ??= about;
    } else {
        hideError(about);
    }

    // Skills
    if (!skills.value.trim()) {
        showError(skills, "Skills are required");
        valid = false;
        firstInvalidInput ??= skills;
    } else if (!skills.value.includes(",")) {
        showError(skills, "Enter skills separated by commas");
        valid = false;
        firstInvalidInput ??= skills;
    } else {
        hideError(skills);
    }

    // Education (at least one valid entry)
    const educationBlocks = document.querySelectorAll(".education-block");
    let hasEducation = false;

    educationBlocks.forEach(block => {
        const inputs = block.querySelectorAll("input");
        const degree = inputs[0]?.value.trim();
        const institute = inputs[1]?.value.trim();
        const year = inputs[2]?.value.trim();

        if (degree && institute) {
            hasEducation = true;

            if (year && !/^\d{4}-\d{4}$/.test(year)) {
                showError(inputs[2], "Year format should be YYYY-YYYY");
                valid = false;
                firstInvalidInput ??= educationBlocks;
            } else {
                hideError(inputs[2]);
            }
        }
    });

    if (!hasEducation) {
        valid = false;
        alert("At least one education entry is required"); // only place alert is acceptable
    }

    if (!valid && firstInvalidInput) {
        firstInvalidInput.scrollIntoView({
            behavior: "smooth",
            block: "center"
        });

        firstInvalidInput.focus({ preventScroll: true });
    }


    return valid;
}


function showError(input, message) {
    const error = input.parentElement.querySelector(".error");
    if (!error) return;

    error.textContent = message;
    error.classList.remove("hidden");
}

function hideError(input) {
    const error = input.parentElement.querySelector(".error");
    if (!error) return;

    error.textContent = "";
    error.classList.add("hidden");
}


function clearErrors() {
    document.querySelectorAll(".error").forEach(e => e.textContent = "");
}

//  DATA COLLECTION 
function collectFormData() {
    return {
        personal: {
            fullName: fullName.value.trim(),
            email: email.value.trim(),
            phone: phone.value.trim(),
            linkedin: linkedin.value.trim(),
            github: github.value.trim()
        },
        about: about.value.trim(),
        skills: skills.value.trim(),
        projects: collect(".project-block", i => ({
            name: i[0].value.trim(),
            description: i[1].value.trim()
        })),
        experience: collect(".experience-block", i => ({
            organization: i[0].value.trim(),
            role: i[1].value.trim(),
            duration: i[2].value.trim(),
            description: i[3].value.trim()
        })),
        education: collect(".education-block", i => ({
            degree: i[0].value.trim(),
            institute: i[1].value.trim(),
            year: i[2].value.trim(),
            cgpa: i[3].value.trim()
        })),
        certifications: collect(".certification-block", i => ({
            name: i[0].value.trim(),
            issuer: i[1].value.trim(),
            year: i[2].value.trim()
        })),
        achievements: collect(".achievement-block", i => ({
            title: i[0].value.trim(),
            description: i[1].value.trim()
        }))
    };
}

function collect(selector, mapper) {
    const arr = [];
    document.querySelectorAll(selector).forEach(block => {
        const inputs = block.querySelectorAll("input, textarea");
        if (inputs[0].value.trim()) arr.push(mapper(inputs));
    });
    return arr;
}

//  TEMPLATE SWITCH 
document.querySelectorAll(".template-card").forEach(card => {
    card.addEventListener("click", () => {
        document.querySelectorAll(".template-card")
            .forEach(c => c.classList.remove("selected"));

        card.classList.add("selected");

        selectedTemplate = card.dataset.template;

        if (lastGeneratedData) {
            generateResumeHTML(lastGeneratedData);
        }
    });
});


//  AI CALL 
async function callAI(type, payload) {
    const response = await fetch("https://genresume-ai.onrender.com/ai/improve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, payload })
    });

    const result = await response.json();
    return result?.result || null;
}


//  RESUME GENERATION 
async function generateResumeHTML(data) {
    const res = await fetch(`templates/${selectedTemplate}.html`);
    let html = await res.text();

    html = html
        .replace("{{FULL_NAME}}", data.personal.fullName)
        .replace("{{EMAIL}}", data.personal.email)
        .replace("{{PHONE}}", data.personal.phone || "")
        .replace("{{LINKEDIN}}", data.personal.linkedin || "")
        .replace("{{GITHUB}}", data.personal.github || "")
        .replace("{{SUMMARY}}", data.about)
        .replace("{{SKILLS}}", formatSkills(data.skills))
        .replace("{{EDUCATION}}", formatEducation(data.education))
        .replace("{{PROJECTS}}", formatProjects(data.projects))
        .replace("{{EXPERIENCE}}", formatExperience(data.experience))
        .replace("{{CERTIFICATIONS}}", formatCertifications(data.certifications))
        .replace("{{ACHIEVEMENTS}}", formatAchievements(data.achievements));

    document.getElementById("resumePreview").innerHTML = html;


}

//  FORMATTERS 

function formatSkills(text) {
    if (!text) return "";

    // AI-grouped skills
    if (text.includes(":")) {
        return text
            .split("\n")
            .map(line => {
                const [domain, skills] = line.split(":");
                if (!domain || !skills) return "";
                return `<p><strong>${domain.trim()}:</strong> ${skills.trim()}</p>`;
            })
            .join("");
    }

    // Normal skills
    return `<p>${text}</p>`;
}

function formatEducation(list) {
    return list.map(e => `
        <p>
            <strong>${e.degree}</strong><br>
            ${e.institute} | ${e.year} | ${e.cgpa}
        </p>
    `).join("");
}

function formatProjects(list) {
    if (!list.length) return "";
    return `
        <section>
            <h2>Projects</h2>
            ${list.map(p => `
                <div class="item">
                    <h3>${p.name}</h3>
                    <p>${p.description}</p>
                </div>
            `).join("")}
        </section>
    `;
}

function formatExperience(list) {
    if (!list.length) return "";
    return `
        <section>
            <h2>Experience</h2>
            ${list.map(e => `
                <div class="item">
                    <h3>${e.organization} — ${e.role}</h3>
                    <span class="meta">${e.duration}</span>
                    <p>${e.description}</p>
                </div>
            `).join("")}
        </section>
    `;
}

function formatCertifications(list) {
    if (!list.length) return "";
    return `
        <section>
            <h2>Certifications</h2>
            ${list.map(c => `
                <div class="item">
                    <p><strong>${c.name}</strong> — ${c.issuer} (${c.year})</p>
                </div>
            `).join("")}
        </section>
    `;
}


function formatAchievements(list) {
    if (!list.length) return "";
    return `
        <section>
            <h2>Achievements</h2>
            ${list.map(a => `
                <div class="item">
                    <p><strong>${a.title}</strong><br>${a.description}</p>
                </div>
            `).join("")}
        </section>
    `;
}




//  BLOCK FACTORY 
function createBlock(type) {
    const div = document.createElement("div");
    div.className = `${type}-block`;

    // ===== Block Header =====
    const header = document.createElement("div");
    header.className = "block-header";

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "delete-block-btn";
    deleteBtn.textContent = "✕";

    deleteBtn.addEventListener("click", () => {
        div.remove();
    });

    header.appendChild(deleteBtn);

    // ===== Content =====
    const content = document.createElement("div");

    const map = {
        experience: `
            <input placeholder="Company / Organization">
            <input placeholder="Role / Position">
            <input placeholder="Duration">
            <textarea rows="3" placeholder="Work description"></textarea>
        `,
        project: `
            <input placeholder="Project Name">
            <textarea rows="3" placeholder="Project description"></textarea>
        `,
        education: `
            <input placeholder="Degree" >
            <input placeholder="Institute / University" >
            <input
                placeholder="Year (e.g. 2023-2025)"
                pattern="\d{4}-\d{4}"
                title="Format should be YYYY-YYYY"/>
            <input placeholder="CGPA / Percentage">
        `,
        certification: `
            <input placeholder="Certification Name">
            <input placeholder="Issuing Organization">
            <input placeholder="Year">
        `,
        achievement: `
            <input placeholder="Achievement Title">
            <textarea rows="2" placeholder="Description"></textarea>
        `
    };

    content.innerHTML = map[type] || "";

    // ===== Assemble =====
    div.appendChild(header);
    div.appendChild(content);
    div.appendChild(document.createElement("hr"));

    return div;
}


//Download Resume Functions
function downloadPDF() {
    const resume = document.getElementById("resumePreview");

    if (!resume || resume.innerHTML.trim() === "") {
        alert("Please generate resume first.");
        return;
    }

    const opt = {
        margin: 10,
        filename: `${lastGeneratedData.personal.fullName.replace(/\s+/g, "_")}_Resume.pdf`,
        image: { type: "jpeg", quality: 0.98 },
        html2canvas: {
            scale: 2,
            useCORS: true,
            scrollY: 0
        },
        jsPDF: {
            unit: "mm",
            format: "a4",
            orientation: "portrait"
        }
    };

    html2pdf().set(opt).from(resume).save();
}

document.getElementById("downloadPdfBtn")
    .addEventListener("click", downloadPDF);

// 
/* ========
   ATS LOGIC (AI ONLY)
======== */

const atsInputSection = document.getElementById("ats-input-section");
const atsRoleInput = document.getElementById("atsRoleInput");
const checkAtsBtn = document.getElementById("checkAtsBtn");
const atsOutputSection = document.getElementById("ats-output-section");
const atsScore = document.getElementById("atsScore");
const atsSuggestions = document.getElementById("atsSuggestions");
const atsError = document.getElementById("atsError");

/* Call this AFTER resume generation */
function showATSInput() {
    atsInputSection.classList.remove("hidden");
}

/* Enable button only if input exists */
atsRoleInput.addEventListener("input", () => {
    checkAtsBtn.disabled = atsRoleInput.value.trim() === "";
});

/* Extract resume text from preview */
function extractResumeText() {
    const preview = document.getElementById("resumePreview");
    return preview ? preview.innerText.trim() : "";
}

/* ATS CHECK */
checkAtsBtn.addEventListener("click", async () => {
    atsError.classList.add("hidden");
    atsOutputSection.classList.add("hidden");

    const jobRole = atsRoleInput.value.trim();
    if (!jobRole) return;

    checkAtsBtn.disabled = true;
    checkAtsBtn.textContent = "Analyzing…";

    try {
        const resumeText = extractResumeText();

        const res = await fetch("https://genresume-ai.onrender.com/ai/ats", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jobRole, resumeText })
        });

        if (!res.ok) throw new Error("Server error");

        const data = await res.json();

        if (
            typeof data.ats_score !== "number" ||
            !Array.isArray(data.suggestions)
        ) {
            throw new Error("Invalid AI response");
        }

        atsScore.textContent = data.ats_score;
        atsSuggestions.innerHTML = "";

        data.suggestions.forEach(s => {
            const div = document.createElement("div");
            div.className = "suggestion";
            div.innerHTML = `<h4>${s.title}</h4><p>${s.detail}</p>`;
            atsSuggestions.appendChild(div);
        });

        atsOutputSection.classList.remove("hidden");

    } catch (err) {
        atsError.textContent = "Something went wrong. Please try again.";
        atsError.classList.remove("hidden");
        console.error(err);
    } finally {
        checkAtsBtn.disabled = false;
        checkAtsBtn.textContent = "Check ATS Score";
    }
});
