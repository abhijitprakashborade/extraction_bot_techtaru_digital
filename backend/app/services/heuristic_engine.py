"""
Deterministic Heuristic Extraction Engine
═══════════════════════════════════════════════════════════════════════════════

Fallback engine used when OPENAI_API_KEY is not configured (demo mode).
It performs real, deterministic text parsing with regex + keyword rules —
no LLM involved, no random values, nothing faked. Fields that cannot be
found are returned as `null`, mirroring the "never hallucinate" rule.

Engine identifier returned to the API layer: "heuristic-demo".
"""

import re
from typing import Any, Optional

from app.models.schemas import DocumentType

# ── Shared regexes ────────────────────────────────────────────────────────────

RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.\-]+")
RE_PHONE = re.compile(r"\+?\d[\d\s\-().]{7,18}\d")
RE_URL = re.compile(r"https?://[^\s)\]>]+|www\.[^\s)\]>]+")
RE_LINKEDIN = re.compile(r"(?:https?://)?(?:[\w-]+\.)?linkedin\.com/in/[\w\-/%]+", re.I)
RE_GITHUB = re.compile(r"(?:https?://)?(?:[\w-]+\.)?github\.com/[\w\-]+/?", re.I)
RE_DATE = re.compile(
    r"\b(?:\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s*[\d]{4}"
    r"|[\d]{4}[/\-.][\d]{1,2}[/\-.][\d]{1,2})\b",
    re.I,
)
RE_MONEY = re.compile(r"(?:(?:Rs\.?|INR|₹|\$|€|£|USD|EUR)\s*)?(\d{1,3}(?:[,\d]*\d)?(?:\.\d{1,2})?)")

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

SKILLS_VOCAB = [
    # languages
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust", "Kotlin",
    "Swift", "PHP", "Ruby", "SQL", "Bash", "R", "MATLAB", "Scala",
    # web/backend
    "React", "Next.js", "Angular", "Vue.js", "Node.js", "Express", "Django", "Flask",
    "FastAPI", "Spring Boot", "ASP.NET", "GraphQL", "REST API", "HTML", "CSS",
    "TailwindCSS", "Bootstrap",
    # data/ai
    "PyTorch", "TensorFlow", "Keras", "scikit-learn", "Pandas", "NumPy", "OpenCV",
    "LangChain", "LlamaIndex", "Hugging Face", "OpenAI API", "Google Gemini",
    "RAG", "Vector Databases", "Qdrant", "Pinecone", "FAISS", "NLP", "Computer Vision",
    "LLM", "Prompt Engineering", "Machine Learning", "Deep Learning", "Data Analysis",
    "Power BI", "Tableau", "Excel", "Apache Spark", "Kafka", "Airflow",
    # cloud/devops
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "CI/CD", "Git", "GitHub",
    "Terraform", "Linux", "Nginx", "Jenkins", "Ansible", "RabbitMQ", "Redis",
    "MongoDB", "PostgreSQL", "MySQL", "Firebase", "Supabase", "SQLite",
    "Microservices", "System Design", "Agile", "Scrum", "OOP", "Data Structures",
]

LANGUAGE_NAMES = [
    "English", "Hindi", "Marathi", "Spanish", "French", "German", "Mandarin",
    "Chinese", "Japanese", "Arabic", "Portuguese", "Russian", "Tamil", "Telugu",
    "Kannada", "Gujarati", "Bengali",
]


def _norm(v: Optional[str]) -> Optional[str]:
    v = v.strip() if v else None
    return v or None


# ══════════════════════════════════════════════════════════════════════════════
# Classification
# ══════════════════════════════════════════════════════════════════════════════

CLASSIFY_KEYWORDS: dict[DocumentType, list[str]] = {
    DocumentType.INVOICE: [
        "invoice", "bill to", "purchase order", "line item", "subtotal",
        "amount due", "payment terms", "po number", "gst", "tax",
    ],
    DocumentType.RESUME: [
        "curriculum vitae", "resume", "work experience", "professional summary",
        "education", "skills", "certification", "career objective",
    ],
    DocumentType.CONTRACT: [
        "agreement", "hereinafter", "party of the first part", "witnesseth",
        "nondisclosure", "nda", "governing law", "termination", "clause",
        "shall", "licensor", "licensee",
    ],
    DocumentType.BUSINESS_CARD: [
        "director", "manager", "chief", "officer", "founder", "consultant",
    ],
    DocumentType.MEDICAL_RECORD: [
        "diagnosis", "patient", "prescription", "dosage", "physician", "clinic",
    ],
}


def classify_document(text: str) -> tuple[DocumentType, float]:
    lower = text.lower()
    best_type, best_score = DocumentType.UNKNOWN, 0.0
    for doc_type, words in CLASSIFY_KEYWORDS.items():
        hits = sum(1 for w in words if w in lower)
        # some keywords appear in resumes too — weight hit ratio
        ratio = hits / len(words)
        if ratio > best_score and hits >= 2:
            best_type, best_score = doc_type, ratio

    # Cheap shape-based tiebreakers
    if best_type is DocumentType.UNKNOWN:
        if RE_EMAIL.search(text) and len(text) < 800 and RE_PHONE.search(text):
            best_type, best_score = DocumentType.BUSINESS_CARD, 0.5
        elif RE_DATE.search(text) and re.search(r"\d+\s*x\s*[\d.,]+", text, re.I):
            best_type, best_score = DocumentType.INVOICE, 0.5

    score = min(0.95, 0.35 + best_score)
    return best_type, round(score, 2)


# ══════════════════════════════════════════════════════════════════════════════
# Resume
# ══════════════════════════════════════════════════════════════════════════════

def _extract_resume(text: str) -> dict:
    data: dict[str, Any] = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # ── Contact ──
    contact = {}
    email = RE_EMAIL.search(text)
    contact["email"] = email.group(0) if email else None

    phones = [m.group(0).strip() for m in RE_PHONE.finditer(text)]
    phone = next(
        (p for p in phones if 9 <= len(re.sub(r"\D", "", p)) <= 14),
        None,
    )
    contact["phone"] = phone

    linkedin = RE_LINKEDIN.search(text)
    contact["linkedin_url"] = linkedin.group(0) if linkedin else None
    github = RE_GITHUB.search(text)
    contact["github_url"] = github.group(0) if github else None

    # name — first short line without digits/@, before 'resume/curriculum' words
    name = None
    non_url = [l for l in lines if not RE_URL.search(l) and "@" not in l and not any(c.isdigit() for c in l)]
    for l in non_url[:4]:
        words = l.split()
        if 1 < len(words) <= 5 and len(l) < 40 and not re.search(r"(resume|cv|vitae)", l, re.I):
            name = l
            break
    contact["full_name"] = name

    # location — a single line styled like "City, Region"
    loc = re.search(
        r"\b([A-Z][\w-]+(?:[ ][A-Z][\w-]+)?,\s*(?:[A-Z]{2}\b|[A-Z][\w-]+))[^\n]*", text)
    contact["location"] = _norm(loc.group(1)) if loc else None

    portfolio = next((u for u in RE_URL.findall(text) if "linkedin" not in u and "github" not in u), None)
    contact["portfolio_url"] = portfolio
    data["contact"] = contact

    # ── Summary ──
    m = re.search(
        r"(?:professional\s+summary|summary|objective|profile)\s*:?\s*\n{0,2}(.{60,500}?)(?:\n\s*\n|\n(?=[A-Z]))",
        text, re.I | re.S)
    data["professional_summary"] = _norm(m.group(1)) if m else None

    # ── Skills ──
    skills = []
    for kw in SKILLS_VOCAB:
        if kw.lower() in text.lower():
            skills.append(kw)
    data["skills"] = skills or []

    # technical skills categorised by line structure "Languages : ..."
    tech: dict[str, list[str]] = {}
    for m0 in re.finditer(r"(Languages?|Frameworks?|Tools?|Databases?|Cloud|Libraries?)\s*[:\-]\s*([^\n]+)", text, re.I):
        cat, items = m0.group(1).title(), [i.strip() for i in m0.group(2).split(",") if i.strip()]
        if items:
            tech[cat] = items
    data["technical_skills"] = tech

    # ── Education ──
    education = []
    edu_re = re.compile(
        r"(?:^|\n)\s*([^|\n]{3,80}?)\s*[,|–-]\s*((?:B\.?E\.?|B\.?Tech|B\.?Sc|B\.?Com|B\.?A\.?|M\.?E\.?|M\.?Tech|M\.?Sc|M\.?S\.?|M\.?Com|MBA|M\.?C\.?A\.?|Diploma|Ph\.?D)\b[^\n]{0,60})",
        re.I)
    for m0 in edu_re.finditer(text):
        education.append({
            "institution": _norm(m0.group(1)), "degree": _norm(m0.group(2)),
            "field_of_study": None, "start_date": None, "end_date": None,
            "gpa": None, "achievements": [],
        })
    if not education:
        m0 = re.search(r"((?:B\.?E\.?|B\.?Tech|M\.?Tech|MBA|M\.?Sc|Diploma)\b[^\n]{0,90})", text, re.I)
        if m0:
            education.append({
                "institution": None, "degree": _norm(m0.group(1)),
                "field_of_study": None, "start_date": None, "end_date": None,
                "gpa": None, "achievements": [],
            })
    data["education"] = education

    # ── Work experience — date-range lines ──
    work = []
    job_re = re.compile(
        r"(?m)^(?P<title>[^\n|]{2,60}?)\s*[,|\-–]\s*(?P<company>[^\n|]{2,60}?)\s*$"
    )
    month_src = "|".join(MONTHS)
    date_range = re.compile(
        rf"(?P<start>(?:{month_src})[a-z]*\.?\s*\d{{4}}|\d{{4}})"
        r"\s*(?:-|–|—|to|TO)\s*"
        rf"(?P<end>(?:{month_src})[a-z]*\.?\s*\d{{4}}|\d{{4}}|Present|Current)",
        re.I,
    )
    for m0 in date_range.finditer(text):
        seg_start = max(0, m0.start() - 160)
        head = text[seg_start:m0.start()].strip().splitlines()
        company = title = None
        for l in reversed([h.strip() for h in head if h.strip()]):
            jm = job_re.match(l)
            if jm:
                title = _norm(jm.group("title"))
                company = _norm(jm.group("company"))
                break
            if company is None and not RE_DATE.search(l) and not RE_URL.search(l) and "@" not in l:
                company = _norm(l)
                break
        end_raw = _norm(m0.group("end"))
        work.append({
            "company": company,
            "title": title,
            "start_date": _norm(m0.group("start")),
            "end_date": end_raw if end_raw and end_raw.lower() not in ("present", "current") else None,
            "is_current": bool(end_raw and end_raw.lower() in ("present", "current")),
            "location": None, "responsibilities": [], "technologies": [], "achievements": [],
        })
    data["work_experience"] = work

    # total experience years
    yrs = re.search(r"(\d{1,2}(?:\.\d)?)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:professional|relevant|industrial)?\s*(?:experience)?", text, re.I)
    data["total_experience_years"] = float(yrs.group(1)) if yrs else None

    # ── Certifications ──
    certs = []
    for m0 in re.finditer(
        r"(?m)^\s*(?:●|-|•|\*)?\s*(.{0,90}?(?:certif(?:ied|icate|ication))[^\n]{0,80})",
        text, re.I):
        name_v = re.sub(r"\s+", " ", m0.group(1)).strip(" -–")
        if name_v and not name_v.lower().startswith("certifications"):
            certs.append({"name": name_v, "issuing_organization": None,
                          "issue_date": None, "expiry_date": None, "credential_id": None})
    data["certifications"] = certs

    # ── Projects ──
    projects = []
    for m0 in re.finditer(r"(?m)^\s*(?:●|-|•|\*)?\s*(?:project\s*[:\-]\s*)?([A-Z][^\n|:]{3,60})\s*[-–:]\s*([^\n]{20,220})", text):
        projects.append({
            "name": _norm(m0.group(1)), "description": _norm(m0.group(2)),
            "technologies": [], "url": None, "start_date": None, "end_date": None,
        })
    data["projects"] = projects

    data["languages"] = [w for w in LANGUAGE_NAMES if re.search(r"\b" + w + r"\b", text, re.I)]

    return data


# ══════════════════════════════════════════════════════════════════════════════
# Invoice
# ══════════════════════════════════════════════════════════════════════════════

def _extract_invoice(text: str) -> dict:
    data: dict[str, Any] = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    m = None
    for m0 in re.finditer(
        r"(?im)^(?:tax\s+)?invoice\s*(?:no\.?|number|#|id)?[ \t]*[:#]?[ \t]*([A-Za-z0-9][A-Za-z0-9\-/]{2,20})[ \t]*$",
        text):
        if m0.group(1).lower() not in ("invoice", "no", "number"):
            m = m0
            break
    data["invoice_number"] = _norm(m.group(1)) if m else None

    inv_date = due_date = None
    for m0 in re.finditer(r"(invoice\s*date|date)\s*[:\-]?\s*([^\n]{0,40})", text, re.I):
        dm = RE_DATE.search(m0.group(2))
        if dm and not inv_date:
            inv_date = dm.group(0)
    for m0 in re.finditer(r"(due\s*date|payment\s*due|due\s*on)\s*[:\-]?\s*([^\n]{0,40})", text, re.I):
        dm = RE_DATE.search(m0.group(2))
        if dm:
            due_date = dm.group(0)
            break
    data["invoice_date"], data["due_date"] = inv_date, due_date

    def _amount(label_variants: list[str]) -> Optional[float]:
        for variant in label_variants:
            m0 = re.search(
                r"(?m)^\s*(?:" + variant + r"|.{0,20}" + variant + r")\s*[:\-]?\s*(?:Rs\.?|INR|₹|\$|€|£)?\s*([\d,]+(?:\.\d{1,2})?)",
                text, re.I)
            if m0:
                return float(m0.group(1).replace(",", ""))
        return None

    data["subtotal"] = _amount([r"sub\s*total"])
    data["tax_amount"] = _amount([r"tax\s*(?:amount)?\s*(?:\(\d+%\))?", r"(?:gst|vat)\s*(?:amount)?"])
    data["discount_amount"] = _amount([r"discount"])
    data["total_amount"] = (
        _amount([r"grand\s*total", r"total\s*due", r"amount\s*due", r"total\s*amount", r"^total\b"])
        or _amount([r"balance\s*due"])
    )

    cur = re.search(r"(Rs\.?|INR|₹|\$|€|£|USD|EUR)", text)
    currency = {"₹": "INR", "$": "USD", "€": "EUR", "£": "GBP"}.get(cur.group(1), cur.group(1)) if cur else None
    data["currency"] = currency

    m = re.search(r"(?:payment\s*terms?)\s*[:\-]?\s*([^\n]{2,40})", text, re.I)
    data["payment_terms"] = _norm(m.group(1)) if m else None
    m = re.search(r"(?:p\.?o\.?|purchase\s*order)\s*(?:number|no\.?|#)?\s*[:#]?\s*([A-Za-z0-9\-/]{3,20})", text, re.I)
    data["po_number"] = _norm(m.group(1)) if m else None

    # ── vendor / client ──
    vendor, client = {}, {}

    def _party_block(after: str, limit: int = 240) -> str:
        m0 = re.search(after + r"\s*\n{0,1}(.{0,%d})" % limit, text, re.I | re.S)
        return m0.group(1) if m0 else ""

    vb = _party_block(r"from\s*[:\-]?\s*(?:\n+)?")
    cb = _party_block(r"(?:bill(?:ed)?\s*to|bill\s*to|to)\s*[:\-]?\s*(?:\n+)?")
    ship = _party_block(r"ship(?:ped)?\s*to")

    for block in (vb, ship):
        if block and not vendor.get("name"):
            first = block.strip().splitlines()[0].strip()
            if len(first) < 70 and not RE_DATE.search(first):
                vendor["name"] = _norm(first)
    cb_lines = [l.strip() for l in cb.splitlines() if l.strip()]
    if cb_lines and len(cb_lines[0]) < 70 and not RE_DATE.search(cb_lines[0]):
        client["name"] = cb_lines[0]

    cm_email = RE_EMAIL.search(cb)
    client["email"] = cm_email.group(0) if cm_email else None
    vm_email = RE_EMAIL.search(vb)
    vendor["email"] = vm_email.group(0) if vm_email else None

    data["vendor"], data["client"] = vendor, client

    # ── line items — rows of "qty unit desc price total" ──
    items = []
    for line in lines:
        m0 = re.match(
            r"^(.{3,50}?)\s{2,}(\d+(?:\.\d+)?)\s*(?:x\s*)?(?:pc?s?|units?|hrs?|kg|nos?\.?)?\s+(\d{1,3}(?:[,\d]*\d)?(?:\.\d{1,2})?)\s+(\d{1,3}(?:[,\d]*\d)?(?:\.\d{1,2})?)\s*$",
            line)
        if m0:
            desc, qty, price, total = m0.groups()
            items.append({
                "description": _norm(desc),
                "quantity": float(qty),
                "unit_price": float(price.replace(",", "")),
                "total_price": float(total.replace(",", "")),
                "tax_rate": None, "unit": None,
            })
    # fallback: tabs in pdf-table rows
    if not items:
        for line in lines:
            if line.count("\t") >= 2:
                cells = [c.strip() for c in line.split("\t")]
                nums = [c for c in cells if re.fullmatch(r"[\d.,]+", c)]
                if len(nums) >= 2 and cells[-1] in nums:
                    items.append({
                        "description": _norm(" ".join(c for c in cells[:-2] if c)),
                        "quantity": float(nums[0].replace(",", "")) if nums[0] else None,
                        "unit_price": float(nums[1].replace(",", "")),
                        "total_price": float(nums[-1].replace(",", "")),
                        "tax_rate": None, "unit": None,
                    })
    data["line_items"] = items

    m = re.search(r"(?:notes?|remarks?)\s*[:\-]\s*([^\n]{5,200})", text, re.I)
    data["notes"] = _norm(m.group(1)) if m else None

    return data


# ══════════════════════════════════════════════════════════════════════════════
# Business card
# ══════════════════════════════════════════════════════════════════════════════

def _extract_business_card(text: str) -> dict:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    email = RE_EMAIL.search(text)
    phones = [p.strip() for p in (m.group(0) for m in RE_PHONE.finditer(text))
              if len(re.sub(r"\D", "", p)) >= 9]

    def _find_url(pred) -> Optional[str]:
        for u in RE_URL.findall(text):
            if pred(u.lower()):
                return u
        return None

    website = _find_url(lambda u: "linkedin" not in u and "github" not in u) or \
        (re.search(r"\b([\w-]+\.(?:com|io|net|org|in|co))\b", text).group(1)
         if re.search(r"\b([\w-]+\.(?:com|io|net|org|in|co))\b", text) else None)

    linkedin = RE_LINKEDIN.search(text)

    company_re = re.compile(r"(pvt\.?|ltd\.?|inc\.?|llc|llp|solutions|technologies|systems|labs|services|consultancy|associates)", re.I)
    role_re = re.compile(
        r"\b(director|founder|co-?founder|chief|c[etf]o|officer|engineer|developer|analyst|"
        r"manager|consultant|president|architect|designer|intern|head\s+of)\b", re.I)

    clean = [
        l for l in lines
        if not RE_URL.search(l)
        and (email is None or email.group(0) not in l)
        and not company_re.search(l)
        and len(re.sub(r"\D", "", l)) < 4
    ]

    title_val = next((l for l in clean if role_re.search(l) and len(l) < 60
                      and not l[:-1].strip().endswith(":")), None)
    name_val = next((l for l in clean if l != title_val
                     and 1 < len(l.split()) <= 5 and len(l) < 40), None)

    # company — prefer an explicit company-ish line; else the line after the title
    company = next((l for l in lines if company_re.search(l) and "@" not in l and len(l) < 70), None)
    if company is None and title_val:
        idx = next((i for i, l in enumerate(lines) if l == title_val), None)
        if idx is not None and idx + 1 < len(lines) and lines[idx + 1] != name_val and "@" not in lines[idx + 1] \
                and not role_re.search(lines[idx + 1]):
            company = lines[idx + 1]

    return {
        "full_name": name_val,
        "title": title_val,
        "company": company,
        "email": email.group(0) if email else None,
        "phone": phones[0] if phones else None,
        "mobile": phones[1] if len(phones) > 1 else None,
        "website": website,
        "address": next((l for l in lines if re.search(
            r"\b(floor|level|suite|street|st\.?|road|rd\.?|avenue|ave?\.?|park|tower|block|nagar|sector|plaza|building)\b",
            l, re.I)), None),
        "linkedin": linkedin.group(0) if linkedin else None,
        "twitter": None,
        "department": next((l for l in lines if re.search(r"\b(department|dept\.?|division)\b", l, re.I)), None),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Contract
# ══════════════════════════════════════════════════════════════════════════════

def _extract_contract(text: str) -> dict:
    first = text.strip().splitlines()[0] if text.strip() else ""
    m = re.search(r"(NON[-\s]?DISCLOSURE|EMPLOYMENT|SERVICE|SAAS|LEASE|PURCHASE|PARTNERSHIP|LICEN[SC]E|VENDOR)(\s+AGREEMENT)?", first, re.I)
    ctype = _norm(m.group(0)) if m else (re.search(r"\b(agreement|contract)\b", first, re.I) and first[:60]) or None

    def _date_after(pattern: str) -> Optional[str]:
        m0 = re.search(pattern + r"\s*[:\-]?\s*(.{0,40})", text, re.I)
        if m0:
            dm = RE_DATE.search(m0.group(1))
            return dm.group(0) if dm else None
        return None

    parties = []
    for m0 in re.finditer(r"(?:between|by and between)(.{0,220}?)(?:and)(.{0,220}?)(?:\.|,|\n|shall)", text, re.I | re.S):
        for seg in (m0.group(1), m0.group(2)):
            seg = seg.strip().replace("\n", " ")
            seg = re.sub(r"\s+", " ", seg)
            if seg and len(seg) < 180:
                parties.append({
                    "name": seg[:120] or None, "role": None, "address": None,
                    "representative": None, "signature_date": None,
                })

    governing = re.search(r"govern(?:ed)?\s*by\s+(?:the\s+)?laws?\s+of\s+([^,\.\n]{3,50})", text, re.I)
    jur = re.search(r"jurisdiction\s+(?:of\s+)?([^,\.\n]{5,50})", text, re.I)

    obligations = []
    for m0 in re.finditer(r"(?m)^\s*(?:The\s+)?([A-Z][\w\- ]{2,40})\s+shall\s+([^\n]{15,220})", text):
        obligations.append({
            "party": _norm(m0.group(1)), "description": _norm(m0.group(2)),
            "due_date": None,
        })

    notice_days = re.search(r"(?:notice|prior\s+notice)\s+of\s+(\d+)\s*(?:days?)|(?:written\s+notice)\b[^\n]{0,40}?(\d+)\s*(?:days?)", text, re.I)
    nd = int(next(v for v in (notice_days.group(1), notice_days.group(2)) if v)) if notice_days else None

    total = re.search(r"(?:total\s+(?:contract\s+)?(?:value|amount|fee)\s+of|consideration\s+of)\s*(?:Rs\.?|INR|₹|\$|€|£)?\s*([\d,]+(?:\.\d{1,2})?)", text, re.I)

    return {
        "contract_title": _norm(text.strip().splitlines()[0][:80]) if text.strip() else None,
        "contract_type": ctype,
        "effective_date": _date_after(r"effective\s+(?:date|from|as\s+of)"),
        "expiry_date": _date_after(r"(?:expir(?:es?|y)|valid\s+(?:until|through)).{0,20}?(?:date)?"),
        "parties": parties[:4],
        "governing_law": governing.group(1).strip() if governing else None,
        "jurisdiction": jur.group(1).strip() if jur else None,
        "payment_terms": next((l for l in text.splitlines() if re.search(r"(payment terms?)", l, re.I)), None),
        "total_value": float(total.group(1).replace(",", "")) if total else None,
        "currency": "INR" if re.search(r"(Rs\.?|INR|₹)", text) else ("USD" if "$" in text else None),
        "obligations": obligations[:10],
        "termination_notice_days": nd,
        "key_clauses": [l.strip()[:100] for l in text.splitlines() if re.match(r"^\s*\d+(\.\d+)*\.\s+[A-Z]", l)][:12],
        "confidentiality": bool(re.search(r"confidential", text, re.I)),
        "non_compete": bool(re.search(r"non[-\s]?compet(?:e|ition)", text, re.I)),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Generic (CUSTOM / UNKNOWN)
# ══════════════════════════════════════════════════════════════════════════════

def _extract_generic(text: str, custom_fields: Optional[list[str]]) -> dict:
    if custom_fields:
        out = {}
        for field in custom_fields:
            field_variants = [field.replace("_", " "), field.replace("_", "-"), field]
            found = None
            for variant in field_variants:
                m0 = re.search(
                    r"(?i)" + re.escape(variant) + r"\s*[:\-]?\s*([^\n]{1,120})", text)
                if m0:
                    found = m0.group(1).strip()
                    break
            out[field] = found or None
        return out

    out = {}
    for m0 in re.finditer(r"(?m)^\s*([A-Za-z][\w \-/()]{2,40})\s*[:\-]\s*([^\n]{1,160})", text):
        key = re.sub(r"\s+", "_", m0.group(1).strip().lower())
        val = m0.group(2).strip()
        val = re.sub(r"\s+", " ", val)
        if key and val and key not in out:
            out[key] = val
        if len(out) >= 40:
            break
    return out


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

_DISPATCH = {
    DocumentType.RESUME: _extract_resume,
    DocumentType.INVOICE: _extract_invoice,
    DocumentType.CONTRACT: _extract_contract,
    DocumentType.BUSINESS_CARD: _extract_business_card,
}


def extract_structured(
    text: str,
    document_type: DocumentType,
    custom_fields: Optional[list[str]] = None,
) -> tuple[dict, dict[str, float], list[str]]:
    """
    Returns (data, field_confidence, warnings).

    Heuristic confidence: 0.95 top-level fields matched by strong regex,
    0.75 for weaker section heuristics, 0.0 for null fields (absent).
    """
    warnings: list[str] = []
    fn = _DISPATCH.get(document_type)
    if fn is None:
        data = _extract_generic(text, custom_fields)
        if not data:
            data = {"document_summary": text[:300]}
        if custom_fields:
            data = {k: v for k, v in data.items()}
    else:
        data = fn(text)

    if not data or all(v in (None, [], {}) for v in data.values()):
        warnings.append(
            "No relevant data could be extracted from the input (heuristic engine found nothing)"
        )

    confidence: dict[str, float] = {}
    for key, value in data.items():
        if value in (None, "", [], {}):
            confidence[key] = 0.0
        elif key in ("contact", "line_items", "work_experience", "parties", "obligations"):
            confidence[key] = 0.75
        else:
            confidence[key] = 0.95

    return data, confidence, warnings


def extract_batch_one(text: str, index: int) -> tuple[dict, dict[str, float], list[str]]:
    """Single-item batch helper used by the API layer when in demo mode."""
    doc_type, conf = classify_document(text)
    return (*extract_structured(text, doc_type), doc_type, conf)
