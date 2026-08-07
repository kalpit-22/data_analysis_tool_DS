import os
from typing import Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv()


class ReviewResult(BaseModel):
    """Structured review result from the Reviewer Agent."""

    approved: bool = Field(
        description="True if the script executed successfully and generated all expected artifacts correctly, False otherwise"
    )
    reason: str = Field(
        description="Detailed reason for failure if approved is False. Empty string if approved is True."
    )
    retry_suggestion: Optional[str] = Field(
        default=None,
        description="Constructive suggestion/hint for the Coder agent on how to fix the issue. None if approved is True."
    )


def get_reviewer_llm() -> ChatOpenAI:
    """
    Configure ChatOpenAI client pointed at local vLLM server,
    matching the planner config (thinking mode disabled, structured output).
    """
    return ChatOpenAI(
        base_url=os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:8000/v1"),
        api_key=os.getenv("LOCAL_LLM_API_KEY", "not-needed"),
        model=os.getenv("LOCAL_LLM_MODEL", "Qwen/Qwen3-8B-AWQ"),
        temperature=0.1,  # low temperature for consistent evaluation
        max_tokens=4098,
        extra_body={
            "chat_template_kwargs": {"enable_thinking": False}
        },
    )


REVIEWER_SYSTEM_PROMPT = """You are the Reviewer agent in a data-analysis pipeline. \
Evaluate the execution results of a Python script against the requested task.

You must reject the execution (approved=False) if:
1. The script failed with a non-zero returncode.
2. The script timed out.
3. Any of the expected output files (artifacts) are missing or failed verification.
4. The stdout/stderr contains Python tracebacks or critical error messages.
5. The execution was clean but failed to achieve the user's intent.

If you do not approve the execution, provide a clear, concise reason and a retry suggestion to guide the Coder agent.
"""


def review(task_description: str, exec_result: dict, artifact_check: dict) -> ReviewResult:
    """
    Calls the Reviewer agent to assess execution and decide if retry is needed.
    """
    llm = get_reviewer_llm()
    structured_llm = llm.with_structured_output(ReviewResult)

    user_prompt = f"""Task Description:
{task_description}

Execution Output:
stdout:
{exec_result.get('stdout', '')}

stderr:
{exec_result.get('stderr', '')}

returncode: {exec_result.get('returncode')}
timed_out: {exec_result.get('timed_out')}

Expected artifacts present and non-empty:
{artifact_check}
"""
    return structured_llm.invoke(
        [
            {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
    )

