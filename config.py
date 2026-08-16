import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# DeepSeek Models
CODER_MODEL = os.getenv("CODER_MODEL", "deepseek-v4-flash")
PLANNER_MODEL = os.getenv("PLANNER_MODEL", "deepseek-v4-flash")
REVIEWER_MODEL = os.getenv("REVIEWER_MODEL", "deepseek-v4-flash")

# DeepSeek API Config
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

# Executor Settings
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", "./workspace")).resolve()
EXEC_TIMEOUT_SECONDS = int(os.getenv("EXEC_TIMEOUT_SECONDS", "15"))

# API Settings
MAX_RETRIES_PER_TASK = int(os.getenv("MAX_RETRIES_PER_TASK", "3"))
