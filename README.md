# ⭐ DocIQ Extractor

<p align="center">
  <img src="https://img.shields.io/badge/OpenAI-Structured_Outputs-412991?logo=openai&logoColor=white" alt="OpenAI">
  <a href="https://github.com/abhijitprakashborade/extraction_bot_techtaru_digital/actions/workflows/ci.yml">
    <img src="https://github.com/abhijitprakashborade/extraction_bot_techtaru_digital/actions/workflows/ci.yml/badge.svg" alt="CI">
  </a>
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white" alt="Pydantic">
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/license-MIT-22c55e" alt="MIT">
</p>

<p align="center">
  Turn <strong>resumes, invoices, contracts &amp; business cards</strong> into clean, validated, confidence-scored JSON<br>
  powered by <strong>OpenAI Structured Outputs</strong> + <strong>Pydantic v2</strong>
</p>

---

## ✨ Highlights

| | |
|---|---|
| 📄 **Multi-format** | PDF, DOCX, TXT, PNG, JPG (Tesseract OCR) |
| 🤖 **Auto-classify** | Detects document type before extraction |
| 🔒 **Strict schema** | API-enforced JSON — zero hallucinations |
| 📊 **Confidence scores** | Per-field 0–100%, colour-coded in UI |
| 🛡️ **Guardrails** | Missing data → `null`, never invented |
| 🗃️ **History & export** | SQLite + JSON / CSV download |
| 📦 **Batch API** | Up to 5 documents in parallel |
| 🐳 **Docker ready** | One-command deploy with nginx |
| 🔌 **Demo mode** | Works without an API key (regex engine) |

---

## 🚀 Quick Start

### ⚡ Windows — one click

```bash
git clone https://github.com/abhijitprakashborade/extraction_bot_techtaru_digital.git
cd extraction_bot_techtaru_digital
START_ALL.bat
```

Open → **http://localhost:5173**

---

### Local (manual)

```bash
# 1. Backend
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 2. Frontend (new terminal)
cd frontend
npm install && npm run dev
```

| | URL |
|---|---|
| 🌐 App | http://localhost:5173 |
| 📖 Swagger | http://localhost:8000/docs |

---

### 🐳 Docker

```bash
echo "OPENAI_API_KEY=sk-..." > .env
docker-compose up --build
```

---

## 🔌 API Examples

```bash
# Extract from file
curl -X POST http://localhost:8000/api/v1/extract/file \
  -F "file=@resume.pdf" -F "document_type=RESUME"

# Extract from text
curl -X POST http://localhost:8000/api/v1/extract/text \
  -H "Content-Type: application/json" \
  -d '{"text": "John Doe\njohn@example.com", "document_type": "RESUME"}'

# Batch (up to 5)
curl -X POST http://localhost:8000/api/v1/extract/batch \
  -H "Content-Type: application/json" \
  -d '[{"text": "Invoice #1001...", "document_type": "INVOICE"}]'
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(empty = demo mode)* | OpenAI key |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model |
| `MAX_FILE_SIZE_MB` | `10` | Upload limit |
| `RATE_LIMIT_PER_MINUTE` | `20` | Per-client limit |
| `MAX_RETRIES` | `3` | Retries on 429/5xx |
| `DATABASE_URL` | `sqlite+aiosqlite:///./extraction_history.db` | History DB |

---

## 🛠️ Stack

**Backend:** FastAPI · Pydantic v2 · SQLAlchemy 2 · pdfplumber · Tesseract OCR
**Frontend:** React 18 · Vite · TailwindCSS · Framer Motion · Recharts · TanStack Query

---

## 🤝 Contributing

```bash
git checkout -b feature/your-feature
git commit -m 'feat: add amazing feature'
git push origin feature/your-feature
# open a Pull Request
```

To add a new document type: add a Pydantic model in `schemas.py`, register it in `_SCHEMA_MAP`, update the `DocumentType` enum, and add business rules in `_apply_business_rule_warnings()`.

---

## 📄 License

MIT © 2025

<p align="center"><sub>Built with ❤️ using FastAPI · OpenAI Structured Outputs · React 18 · Pydantic v2</sub></p>
