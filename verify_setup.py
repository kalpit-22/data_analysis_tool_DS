"""
Phase 1 verification script.

Confirms both engines are reachable and responding before we build
the profiler / agent layers on top of them:
  1. Local vLLM server (Qwen3-8B) — planner + reviewer
  2. Cloud DeepSeek V4 Pro API   — coder

Run:
    python scripts/verify_setup.py
"""

import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv()


def check_local_vllm() -> bool:
    base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:8000/v1")
    model = os.getenv("LOCAL_LLM_MODEL", "Qwen/Qwen3-8B")
    print(f"\n[1/2] Checking local vLLM at {base_url} ...")

    try:
        resp = httpx.get(f"{base_url}/models", timeout=5.0)
        resp.raise_for_status()
        models = [m["id"] for m in resp.json().get("data", [])]
        print(f"  Server reachable. Models available: {models}")

        chat_resp = httpx.post(
            f"{base_url}/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                "max_tokens": 50,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            timeout=30.0,
        )
        chat_resp.raise_for_status()
        text = chat_resp.json()["choices"][0]["message"]["content"]
        print(f"  Chat completion succeeded. Response: {text!r}")
        return True

    except httpx.ConnectError:
        print("  FAILED: Could not connect. Is launch_vllm.sh running?")
        return False
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def check_deepseek_cloud() -> bool:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    print(f"\n[2/2] Checking cloud DeepSeek at {base_url} ...")

    if not api_key or api_key == "your_deepseek_api_key_here":
        print("  FAILED: DEEPSEEK_API_KEY not set in .env")
        return False

    try:
        resp = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                "max_tokens": 50,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        print(f"  Chat completion succeeded. Response: {text!r}")
        if not text.strip():
            print(f"  NOTE: content is empty — full response for debugging:")
            print(f"  {data}")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


if __name__ == "__main__":
    print("== DataPilot Phase 1: Environment Verification ==")

    local_ok = check_local_vllm()
    cloud_ok = check_deepseek_cloud()

    print("\n== Summary ==")
    print(f"  Local vLLM (Planner/Reviewer): {'PASS' if local_ok else 'FAIL'}")
    print(f"  Cloud DeepSeek (Coder):        {'PASS' if cloud_ok else 'FAIL'}")

    if local_ok and cloud_ok:
        print("\nBoth engines are up. Ready to build Phase 2 (profiler.py).")
        sys.exit(0)
    else:
        print("\nFix the failing engine(s) above before proceeding to Phase 2.")
        sys.exit(1)
