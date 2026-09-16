# Operations & Incident Runbook
**Project:** Affinity — AI-Based Startup Idea Validator  
**Document Version:** September 2026 · Milestones 1 & 2  

---

## 1. Local Environment Setup

### Prerequisites
- Python 3.10+
- Node.js 18+ & npm
- Git

### Step-by-Step Setup

```bash
# 1. Clone repository
git clone https://github.com/Yasaswini-ch/Development-of-AI-Based-Startup-Idea-Validator-with-Market-Analysis-Assistance.git
cd Development-of-AI-Based-Startup-Idea-Validator-with-Market-Analysis-Assistance

# 2. Backend setup
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm  # Required for local Competitor Discovery NER
cp .env.example .env
# Edit .env and supply your GROQ_API_KEY (and optional TAVILY_API_KEY)

# Run Backend
uvicorn main:app --host 127.0.0.1 --port 8000

# 3. Frontend setup (in a separate terminal)
cd ../frontend
npm install
cp .env.example .env  # Ensure VITE_API_URL=http://localhost:8000
npm run dev           # Accessible at http://localhost:5173
```

> [!WARNING]
> The backend server does **not** auto-reload by default (`uvicorn main.py --reload` is omitted in default dev instructions). If you edit Python code in `backend/`, you must restart the Uvicorn server process or test calls will run on stale code.

---

## 2. Production Deployment (Render)

Affinity is configured for zero-downtime deployment on **Render** using standard Web Services defined in [`render.yaml`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/render.yaml).

### Environment Variables Checklist

| Environment Variable | Service | Required? | Purpose |
|---|---|---|---|
| `GROQ_API_KEY` | Backend | **Yes** | Primary LLM key for Market Opportunity Agent |
| `TAVILY_API_KEY` | Backend | Optional | Primary Search API key (DuckDuckGo fallback used if absent) |
| `FRONTEND_ORIGIN` | Backend | **Yes** | CORS origin (e.g. `https://affinity-validator.onrender.com`) |
| `VITE_API_URL` | Frontend | **Yes** | Backend endpoint URL (e.g. `https://affinity-backend.onrender.com`) |

---

## 3. Incident Response & Troubleshooting Matrix

### Incident 1: Groq LLM Quota Exhaustion (`RateLimitError`)
- **Symptom:** Backend log contains `RateLimitError: Rate limit reached for model`.
- **Automated Behavior:** [`backend/agent/llm.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/llm.py) automatically catches the error and switches to the next fallback model in sequence:
  1. `groq/qwen/qwen3.8-27b`
  2. `groq/openai/gpt-oss-20b`
  3. `groq/openai/gpt-oss-120b`
- **Mitigation:**
  - If all models fail, `market_opportunity` returns `null` and `errors.marketOpportunity` populates.
  - The UI displays an inline `UnavailableCard` for Market Opportunity without crashing.
  - Wait 60 seconds for the free-tier per-minute quota to reset.

---

### Incident 2: Groq Model Deprecation (`model_not_found`)
- **Symptom:** Log outputs `litellm.NotFoundError: GroqException - The model does not exist or you do not have access to it`.
- **Root Cause:** Provider deprecated an old model ID (e.g., historical `qwen3.6-27b` deprecation).
- **Resolution:**
  - `_is_model_not_found_error()` in [`backend/agent/llm.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/llm.py) catches 404 errors and immediately skips to the next model in the fallback array.
  - Update `DEFAULT_MODEL` in `backend/agent/llm.py` and `.env` to the current active model ID listed on Groq's model console.

---

### Incident 3: Search API Failure or Missing Tavily Key
- **Symptom:** `TAVILY_API_KEY` is invalid, expired, or absent.
- **Automated Behavior:** [`backend/agent/retrieval.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/retrieval.py) seamlessly switches to the **zero-cost fallback chain**:
  1. DuckDuckGo Search (`duckduckgo-search`)
  2. Wikipedia API (`wikipedia`)
  3. Hacker News Search API (`hn`)
- **Verification:** The pipeline continues to produce real search results and validation reports without disruption.

---

### Incident 4: spaCy `en_core_web_sm` Model Missing
- **Symptom:** Backend crashes on startup with `OSError: [E050] Can't find model 'en_core_web_sm'`.
- **Resolution:**
  ```bash
  python -m spacy download en_core_web_sm
  ```

---

### Incident 5: Stale Frontend Results
- **Symptom:** Browser displays previous test outputs even after backend code updates.
- **Root Cause:** [`frontend/src/App.jsx`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/frontend/src/App.jsx) persists previous session validation results in `sessionStorage` (`affinity:lastValidation`) to prevent data loss on tab reload.
- **Resolution:** Open Browser DevTools Console and execute:
  ```javascript
  sessionStorage.clear();
  location.reload();
  ```

---

## 4. Operational Diagnostic Commands

### Check Backend Server Process (PowerShell)
```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*uvicorn*" }
```

### Force Kill Running Backend Server (PowerShell)
```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*uvicorn*" } | Stop-Process -Force
```

### Test `/validate` Endpoint Health via cURL
```bash
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{"idea": "Health test idea"}'
```
