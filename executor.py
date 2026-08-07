"""
Phase 4: Safe Execution Sandbox.

Runs Coder-generated scripts as subprocesses inside WORKSPACE_DIR, with a
hard timeout, and verifies expected output artifacts exist afterward.

Cross-platform notes (this runs on native Windows in the split setup):
  - Always force UTF-8 on subprocess stdout/stderr to avoid cp1252 decode
    errors when generated code prints non-ASCII data (currency symbols,
    accented names, etc).
  - Never assume forward-slash paths in generated code; the Coder agent's
    system prompt should instruct it to use pathlib.Path everywhere.
"""

import os
import shutil
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", "./workspace")).resolve()
TIMEOUT_SECONDS = int(os.getenv("EXEC_TIMEOUT_SECONDS", "15"))


def prepare_workspace(csv_path: str) -> None:
    """
    Cleans the workspace directory and copies the input CSV there, preserving the original filename.
    """
    # Ensure a clean workspace
    if WORKSPACE_DIR.exists():
        for item in WORKSPACE_DIR.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception:
                pass
    else:
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

    # Resolve source CSV and copy it preserving its basename
    src = Path(csv_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source CSV file does not exist: {csv_path}")
    dst = WORKSPACE_DIR / src.name
    shutil.copy2(src, dst)


def run_script(script_path: str) -> dict:
    """
    Executes a generated Python script inside the workspace sandbox using the venv's Python.

    Returns a dict with stdout, stderr, returncode, and timed_out flag.
    """
    script_path = Path(script_path).resolve()

    if not str(script_path).startswith(str(WORKSPACE_DIR)):
        raise ValueError(
            f"Refusing to execute script outside workspace: {script_path}"
        )

    # Resolve Python interpreter in active virtual environment (.venv)
    # Search root and parent folders in case of execution context variance
    project_root = Path(__file__).parent.resolve()
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = project_root / ".venv" / "bin" / "python"
    
    python_exe = str(venv_python) if venv_python.exists() else "python"

    # Force subprocess Python to output UTF-8
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        result = subprocess.run(
            [python_exe, str(script_path), str(WORKSPACE_DIR)],
            cwd=str(WORKSPACE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",      # avoid cp1252 decode errors on Windows
            errors="replace",       # never crash the sandbox on a bad byte
            timeout=TIMEOUT_SECONDS,
            env=env,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "stdout": e.stdout or "",
            "stderr": (e.stderr or "") + f"\n[TIMED OUT after {TIMEOUT_SECONDS}s]",
            "returncode": None,
            "timed_out": True,
        }


def verify_artifacts(expected_files: list[str]) -> dict:
    """
    Confirms expected output files (e.g. chart.png, cleaned.csv) exist in
    the workspace and are non-empty.
    """
    results = {}
    for fname in expected_files:
        fpath = WORKSPACE_DIR / fname
        results[fname] = fpath.exists() and fpath.stat().st_size > 0
    return results


if __name__ == "__main__":
    # Quick manual smoke test
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    test_script = WORKSPACE_DIR / "_smoke_test.py"
    test_script.write_text(
        "print('sandbox OK - hello')\n", encoding="utf-8"
    )
    out = run_script(str(test_script))
    # Safe printing using ASCII encoding/decoding just in case console cannot handle it
    safe_out = {k: (v.encode('ascii', 'replace').decode('ascii') if isinstance(v, str) else v) for k, v in out.items()}
    print("Smoke test result:", safe_out)
    test_script.unlink()

