# DataPilot 

An autonomous, self-correcting data analysis assistant with a premium web UI.  
Give it a CSV and a plain-English question — it plans, writes code, executes, reviews, and self-corrects until the job is done.

---

## How It Works

```
CSV + Prompt ──▶ Profiler ──▶ Planner (DeepSeek Flash) ──▶ Coder (DeepSeek Pro)
                                                                │
                                                          ┌─────▼─────┐
                                                          │  Executor  │
                                                          │ (sandbox)  │
                                                          └─────┬─────┘
                                                                │
                                                          ┌─────▼─────┐
                                                          │ Reviewer   │◀── retry loop
                                                          │(DS Flash)  │     (up to 3x)
                                                          └───────────┘
```

1. **Profiler** — extracts schema, data types, missing values, and sample rows from the CSV (no raw data sent to LLMs).  
2. **Planner** *(DeepSeek Flash)* — breaks the user's request into an ordered list of atomic analysis steps.  
3. **Coder** *(DeepSeek Pro)* — writes a standalone Python script for each step.  
4. **Executor** — runs each script in a sandboxed `workspace/` directory with a timeout.  
5. **Reviewer** *(DeepSeek Flash)* — checks stdout/stderr + output artifacts; approves or rejects with retry suggestions.

Steps 3–5 loop up to 3 times per step with self-correction feedback.

---

## Features

- **Premium Web UI**: A sleek, dark-themed, glassmorphism web interface built with Vanilla HTML/JS/CSS (no Node.js required).
- **Real-time Streaming**: Watch the AI agents plan and execute in real-time via Server-Sent Events (SSE).
- **Interactive Outputs**: Generated charts and datasets are instantly rendered in the browser.
- **Fully Cloud-LLM**: 100% powered by the DeepSeek API. No local GPU required.
- **Docker Ready**: Designed to be easily deployed to Azure Container Apps (free tier) in a single lightweight container.

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/kalpit-22/data_analysis_tool_DS.git
cd data_analysis_tool_DS
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the root directory:

```env
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_FLASH_MODEL=deepseek-chat
DEEPSEEK_PRO_MODEL=deepseek-coder
```

*(Note: Use `deepseek-chat` for Flash and `deepseek-coder` or the V4 equivalents for Pro depending on your account tier).*

### 3. Run the Web Server

```bash
uvicorn api:app --port 8000 --host 127.0.0.1
```

Open **http://127.0.0.1:8000** in your browser. Drag and drop a CSV, type your analysis request, and launch!

---

## Cross-Platform Docker Deployment (Recommended)

To ensure a perfectly identical environment whether you're developing on a Mac or Windows machine, DataPilot is fully configured for Docker Compose.

1. **Start the environment**:
```bash
docker compose up --build
```
This single command will:
- Build the Python 3.11-slim container
- Automatically load your `.env` configuration
- Expose the app on `http://127.0.0.1:8000`
- Mount the local `workspace/` and `uploads/` directories so files persist

2. **Stop the environment**:
```bash
docker compose down
```

---

## Project Structure

```
DataPilot/
├── api.py               # FastAPI Web Backend (SSE + Static files)
├── frontend/            # Vanilla HTML/JS/CSS web interface
├── main.py              # CLI Orchestrator (Fallback)
├── profiler.py          # CSV schema extraction
├── planner.py           # Planning agent (DeepSeek Flash)
├── coder.py             # Code generation agent (DeepSeek Pro)
├── executor.py          # Sandboxed script runner
├── reviewer.py          # Output review agent (DeepSeek Flash)
├── requirements.txt     # Python dependencies
├── Dockerfile           # Multi-stage Docker config
├── .dockerignore        
├── .gitignore
├── uploads/             # Temporary CSV uploads (auto-cleared)
└── workspace/           # Generated outputs (sandbox)
```

---

## License

MIT
