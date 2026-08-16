import os
from typing import Optional
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from config import REVIEWER_MODEL, PRO_MODEL, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL


class ReviewResult(BaseModel):
    """Structured review result from the Reviewer Agent."""

    approved: bool = Field(
        description="True if the script executed successfully and generated all expected artifacts correctly, False otherwise"
    )
    reason: str = Field(
        default="",
        description="Detailed reason for failure if approved is False. Empty string if approved is True."
    )
    retry_suggestion: Optional[str] = Field(
        default=None,
        description="Constructive suggestion/hint for the Coder agent on how to fix the issue. None if approved is True."
    )


def get_reviewer_llm(use_pro: bool = False) -> ChatOpenAI:
    """
    Configure ChatOpenAI client pointed at the DeepSeek cloud API.
    Review is a simple structured pass/fail evaluation.
    """
    return ChatOpenAI(
        base_url=DEEPSEEK_BASE_URL,
        api_key=DEEPSEEK_API_KEY,
        model=PRO_MODEL if use_pro else REVIEWER_MODEL,
        temperature=0.1,  # low temperature for consistent evaluation
        max_tokens=4096,
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
Return your evaluation as JSON."""


def review(task_description: str, exec_result: dict, artifact_check: dict, use_pro: bool = False) -> ReviewResult:
    """
    Calls the Reviewer agent to assess execution and decide if retry is needed.
    """
    llm = get_reviewer_llm(use_pro)
    # DeepSeek doesn't support JSON Schema response_format — use json_mode instead
    structured_llm = llm.with_structured_output(ReviewResult, method="json_mode")

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

