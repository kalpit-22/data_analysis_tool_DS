"""
Planner Agent (planner.py)

Receives a user's natural-language request plus a CSV schema summary,
and returns a structured, ordered list of atomic analysis steps for the
Coder Agent to implement.

Uses the DeepSeek Flash model (deepseek-chat) via the DeepSeek cloud API.
Planning is a lightweight structured-output task — Flash is fast and cheap
for this workload with no loss in quality.
"""

import os
from typing import List
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from config import PLANNER_MODEL, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL


class TaskStep(BaseModel):
    """A single atomic step in the analysis plan."""

    step_name: str = Field(
        description="Short filename-style identifier for this step, e.g. 'clean_data.py'"
    )
    description: str = Field(
        description="One or two sentences describing what this step does"
    )
    expected_artifacts: List[str] = Field(
        default=[],
        description="List of filenames this step is expected to produce in the workspace (e.g. ['cleaned_data.csv'] or ['chart.png']). Leave empty if no files are output."
    )


class DataPlan(BaseModel):
    """Structured output: an ordered list of steps to fulfill the user's request."""

    steps: List[TaskStep] = Field(
        description="Ordered list of atomic steps needed to complete the user's request"
    )


def get_planner_llm() -> ChatOpenAI:
    """
    Configure a ChatOpenAI client pointed at the DeepSeek cloud API.
    Uses the Flash model (deepseek-chat) — fast, cheap, and fully capable
    of producing consistent structured output for planning tasks.
    """
    return ChatOpenAI(
        base_url=DEEPSEEK_BASE_URL,
        api_key=DEEPSEEK_API_KEY,
        model=PLANNER_MODEL,
        temperature=0.1,  # low temperature: we want consistent, structured planning
        max_tokens=4096,
    )


PLANNER_SYSTEM_PROMPT = """You are a data analysis planning agent. Given a user's request and a CSV schema, break the request down into a short, ordered list of atomic steps. Each step should be small enough to be a single Python script.

Return your answer as JSON matching this exact structure:
{
  "steps": [
    {
      "step_name": "snake_case_script_name.py",
      "description": "One or two sentences describing what this step does.",
      "expected_artifacts": ["output_filename.csv"]
    }
  ]
}

Rules:
- `step_name` is REQUIRED — use a short snake_case filename ending in .py (e.g. "clean_data.py", "plot_revenue.py").
- `expected_artifacts` contains the exact output filenames the script must produce (e.g. ["revenue_by_month.png"]).
- Use snake_case filenames without spaces.
- Keep the plan concise while fully addressing the request."""


def plan_tasks(user_request: str, csv_schema: str) -> DataPlan:
    """
    Generate a structured task plan for the given user request and CSV schema.

    Args:
        user_request: The user's natural-language analysis request.
        csv_schema: Markdown-formatted schema summary from profiler.py
                    (column names, dtypes, non-null counts, sample rows).

    Returns:
        DataPlan with an ordered list of TaskStep objects.
    """
    llm = get_planner_llm()
    # DeepSeek doesn't support JSON Schema response_format — use json_mode instead
    structured_llm = llm.with_structured_output(DataPlan, method="json_mode")

    prompt = f"""{PLANNER_SYSTEM_PROMPT}

CSV Schema:
{csv_schema}

User Request:
{user_request}
"""

    return structured_llm.invoke(prompt)


if __name__ == "__main__":
    # Quick manual test — run with: python planner.py
    # Requires DEEPSEEK_API_KEY to be set in .env

    example_schema = """
| Column      | Type    | Non-Null Count | Sample          |
|-------------|---------|-----------------|-----------------|
| order_id    | int64   | 1000            | 1001            |
| region      | object  | 1000            | "West"          |
| revenue     | float64 | 998             | 245.50          |
| order_date  | object  | 1000            | "2024-01-15"    |
"""
    example_request = "Show me total revenue by region and plot it as a bar chart."

    print("Requesting plan from DeepSeek Planner Agent (Flash)...\n")
    result = plan_tasks(example_request, example_schema)

    print(f"Generated {len(result.steps)} step(s):\n")
    for i, step in enumerate(result.steps, 1):
        print(f"{i}. {step.step_name}")
        print(f"   {step.description}\n")
