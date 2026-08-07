# DataPilot 🚀

An autonomous, self-correcting data analysis assistant powered by a dual-LLM architecture.  
Give it a CSV and a plain-English question — it plans, writes code, executes, reviews, and self-corrects until the job is done.

---

## How It Works

```
CSV + Prompt ──▶ Profiler ──▶ Planner (local Qwen3-8B) ──▶ Coder (DeepSeek V4 Pro)
                                                                    │
                                                              ┌─────▼─────┐
                                                              │  Executor  │
                                                              │ (sandbox)  │
                                                              └─────┬─────┘
                                                                    │
                                                              ┌─────▼─────┐
                                                              │ Reviewer   │◀── retry loop
                                                              │(Qwen3-8B) │     (up to 3x)
                                                              └───────────┘
```

1. **Profiler** — extracts schema, data types, missing values, and sample rows from the CSV (no raw data sent to LLMs).  
2. **Planner** *(local, Qwen3-8B-AWQ)* — breaks the user's request into an ordered list of atomic analysis steps.  
3. **Coder** *(cloud, DeepSeek V4 Pro)* — writes a standalone Python script for each step.  
4. **Executor** — runs each script in a sandboxed `workspace/` directory with a timeout.  
5. **Reviewer** *(local, Qwen3-8B-AWQ)* — checks stdout/stderr + output artifacts; approves or rejects with retry suggestions.

Steps 3–5 loop up to 3 times per step with self-correction feedback.

---

## Quick Start

### Prerequisites

| Requirement | Details |
|---|---|
| **Python** | 3.10+ |
| **GPU** | NVIDIA GPU with CUDA drivers (for local vLLM server) |
| **OS** | WSL2 + Ubuntu recommended (or native Linux for vLLM) |
| **API Key** | [DeepSeek](https://platform.deepseek.com) API key |

### 1. Clone & install

```bash
git clone https://github.com/your-username/DataPilot.git
cd DataPilot
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your DEEPSEEK_API_KEY
```

### 3. Launch the local vLLM server

In a **separate terminal** (WSL2/Ubuntu with GPU):

```bash
pip install vllm==0.8.5
vllm serve Qwen/Qwen3-8B-AWQ \
  --quantization awq_marlin \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.9
```

> [!NOTE]
> First launch downloads the model from Hugging Face (~4 GB for AWQ).  
> The full-precision Qwen3-8B needs ~15 GB VRAM — use the AWQ variant for 12 GB cards.

### 4. Verify setup

```bash
python verify_setup.py
```

Both the local vLLM and cloud DeepSeek checks should show `PASS`.

### 5. Run DataPilot

```bash
python main.py
```

You'll be prompted for:
1. **CSV file path** — path to your dataset
2. **Analysis request** — what you want to know, in plain English

Or pass them directly via CLI flags:

```bash
python main.py --csv sales_data.csv --request "Show revenue by region as a bar chart"
```

Outputs (charts, aggregated CSVs, generated scripts) are saved to the `workspace/` directory.

---

## Example

```
$ python main.py

📂 Enter the path to your CSV file: enterprise_sales_data.csv
🔍 What would you like to analyze? Describe in plain English:
> Show me total revenue by region as a bar chart and profit by category as a bar chart

==================================================
      DataPilot: Autonomous Analysis Initialization
==================================================

[+] Profiling dataset schema...
[+] Generating analysis plan from local Planner Agent...
    Generated 4 step(s):
    1. Aggregate total revenue by region
    2. Plot total revenue by region as a bar chart
    3. Aggregate total profit by category
    4. Plot total profit by category as a bar chart

>>> [Step 1/4] Aggregate total revenue by region  ✅
>>> [Step 2/4] Plot total revenue by region        ✅
>>> [Step 3/4] Aggregate total profit by category  ✅
>>> [Step 4/4] Plot total profit by category       ✅

[+] SUCCESS: DataPilot successfully completed all planned steps!
```

---

## Project Structure

```
DataPilot/
├── main.py              # Orchestrator — ties the full pipeline together
├── profiler.py          # CSV schema extraction (pandas-based, no LLM)
├── planner.py           # Planning agent (local Qwen3-8B-AWQ via vLLM)
├── coder.py             # Code generation agent (cloud DeepSeek V4 Pro)
├── executor.py          # Sandboxed script runner with timeout
├── reviewer.py          # Output review agent (local Qwen3-8B-AWQ)
├── verify_setup.py      # Health check for both LLM backends
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
├── .gitignore
└── workspace/           # Generated outputs (gitignored)
```

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API key (required) | — |
| `DEEPSEEK_BASE_URL` | DeepSeek API base URL | `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | Cloud model name | `deepseek-v4-pro` |
| `LOCAL_LLM_BASE_URL` | Local vLLM server URL | `http://localhost:8000/v1` |
| `LOCAL_LLM_MODEL` | Local model name | `Qwen/Qwen3-8B-AWQ` |
| `WORKSPACE_DIR` | Sandbox output directory | `./workspace` |
| `EXEC_TIMEOUT_SECONDS` | Per-script execution timeout | `15` |
| `MAX_RETRIES_PER_TASK` | Self-correction retry limit | `3` |

---

## GPU & Performance Notes

- **12 GB VRAM (e.g. RTX 4070 Super):** use `Qwen/Qwen3-8B-AWQ` with `--quantization awq_marlin`. Plain `awq` is ~4.5× slower.
- **16 GB+ VRAM:** you can use the full `Qwen/Qwen3-8B` model and increase `--max-model-len`.
- Keep the project on the native WSL filesystem (`~/DataPilot`), not `/mnt/c/...` — much faster disk I/O for model loading.
- Qwen3's thinking mode is disabled for Planner/Reviewer agents to avoid wasted tokens on `<think>` blocks.

---

## License

MIT
