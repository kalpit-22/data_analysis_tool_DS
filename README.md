# DataPilot

An autonomous data analysis assistant with a web interface. Provide a CSV file and a natural language question. The system plans the analysis, writes code, executes it, and reviews the output until the task is complete.

---

## How It Works

```text
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

1. **Profiler**: Extracts schema, data types, missing values, and sample rows from the CSV without sending raw data to the LLM.
2. **Planner** (DeepSeek Flash): Breaks the request into an ordered list of atomic analysis steps.
3. **Coder** (DeepSeek Pro): Writes a standalone Python script for each step.
4. **Executor**: Runs each script in a sandboxed `workspace/` directory with a timeout.
5. **Reviewer** (DeepSeek Flash): Checks stdout/stderr and output artifacts, approving or rejecting with retry suggestions.

Steps 3 through 5 repeat up to 3 times per step using self-correction feedback.

---

## Features

- **Web Interface**: Built with vanilla HTML, JavaScript, and CSS. No Node.js required.
- **Password Protection**: Built-in authentication to secure the application using an environment variable.
- **Pro Mode Toggle**: Option to run analysis with DeepSeek Pro directly from the UI.
- **Real-time Streaming**: Watch the agents plan and execute in real-time via Server-Sent Events (SSE).
- **Interactive Outputs**: Generated charts and datasets are rendered in the browser.
- **DeepSeek Integration**: Powered by the DeepSeek API.
- **Docker Support**: Configured for Docker Compose to ensure a consistent environment across different systems.

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
APP_PASSWORD=your_secure_password
```

Note: The default application password is `DataPilot123!`. Use `deepseek-chat` for Flash and `deepseek-coder` or the V4 equivalents for Pro depending on your account tier.

### 3. Run the Web Server

```bash
uvicorn api:app --port 8000 --host 127.0.0.1
```

Open **http://127.0.0.1:8000** in your browser. Enter the application password, upload a CSV, type your analysis request, and start the process.

---

## Cross-Platform Docker Deployment (Recommended)

DataPilot is configured for Docker Compose to ensure an identical environment on Mac, Windows, or Linux.

1. **Start the environment**:
```bash
docker compose up --build
```
This command will:
- Build the Python 3.11-slim container.
- Load the `.env` configuration.
- Expose the application on `http://127.0.0.1:8000`.
- Mount the local `workspace/` and `uploads/` directories for persistent files.

2. **Stop the environment**:
```bash
docker compose down
```

---

## Project Structure

```text
DataPilot/
├── api.py               # FastAPI Web Backend (SSE, Authentication, Static files)
├── frontend/            # Vanilla HTML/JS/CSS web interface
├── main.py              # CLI Orchestrator (Fallback)
├── profiler.py          # CSV schema extraction
├── planner.py           # Planning agent (DeepSeek Flash)
├── coder.py             # Code generation agent (DeepSeek Pro)
├── executor.py          # Sandboxed script runner
├── reviewer.py          # Output review agent (DeepSeek Flash)
├── requirements.txt     # Python dependencies
├── Dockerfile           # Multi-stage Docker config
├── docker-compose.yml   # Docker Compose configuration
├── .dockerignore        
├── .gitignore
├── uploads/             # Temporary CSV uploads (auto-cleared)
└── workspace/           # Generated outputs (sandbox)
```

---

## License

MIT
