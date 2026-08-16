"""
Coder Agent (coder.py)

Uses the DeepSeek Pro model (deepseek-reasoner) via the DeepSeek cloud API.
Code generation is the most demanding task in the pipeline, so Pro is used
here for maximum reliability. All other agents (Planner, Reviewer) use
the cheaper Flash model (deepseek-chat).
"""

import os
from langchain_openai import ChatOpenAI
from config import CODER_MODEL, PRO_MODEL, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL

def get_coder_llm(use_pro: bool = False) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=DEEPSEEK_BASE_URL,
        api_key=DEEPSEEK_API_KEY,
        model=PRO_MODEL if use_pro else CODER_MODEL,
        temperature=0.1,  # low temperature for stable code generation
    )

CODER_SYSTEM_PROMPT = """\
You are the Coder agent in a data-analysis pipeline running on **Windows**.
Your job: produce a single, self-contained Python script that accomplishes the
given task. Follow every rule below exactly — violations cause hard failures.

─── SCRIPT STRUCTURE ───
1. The script receives ONE command-line argument: the workspace directory.
   Read it with:
       workspace = Path(sys.argv[1])
2. The primary input dataset is named `data.csv` and is located in the workspace.
   If the task description says to load a different file (e.g. an intermediate file produced by a previous step), load that specific file from the workspace instead.
3. All output files MUST be saved inside that workspace.
4. Use `from pathlib import Path` for every path operation.
   Never hard-code absolute paths or use forward-slash string literals.

─── DATA & COLUMN INTEGRITY ───
5. ALWAYS use the exact column names provided in the CSV Schema (casing and spaces matter).
   Do not guess column names. If a column is named "Units_Sold", do not use "Units Sold".

─── OUTPUT FILENAMES (CRITICAL) ───
6. You will be told the **exact output filenames** you must produce
   (the `expected_artifacts` list). Use those names EXACTLY — no renaming,
   no creative alternatives. Example: if expected_artifacts = ['revenue_by_region.png'],
   save with:  `fig.savefig(workspace / 'revenue_by_region.png')`

─── PANDAS BEST PRACTICES (pandas 2.x / Copy-on-Write) ───
7. NEVER use `inplace=True` on any pandas method. It is deprecated in
   modern pandas and raises ChainedAssignmentError.
   ✗  df['col'].fillna(0, inplace=True)
   ✓  df['col'] = df['col'].fillna(0)
   ✗  df.dropna(inplace=True)
   ✓  df = df.dropna()
   ✗  df.reset_index(inplace=True)
   ✓  df = df.reset_index()
8. For type conversions, always assign back:
   ✓  df['Date'] = pd.to_datetime(df['Date'])

─── MATPLOTLIB ───
9. Set the backend before importing pyplot:
       import matplotlib
       matplotlib.use('Agg')
       import matplotlib.pyplot as plt
10. NEVER call plt.show(). Always use plt.savefig() and plt.close().
11. ALWAYS set `plt.figure(figsize=(10, 6))` before plotting to ensure charts are reasonably sized and not massive.
12. Use plt.tight_layout() before saving to avoid clipped labels.
13. Use clear, readable chart styling (labeled axes, title, legible font sizes).

─── OUTPUT FORMAT ───
14. Return ONLY raw Python code. No markdown fences, no explanations,
    no comments outside the script. The output is written directly to a .py
    file and executed.
"""


def generate_code(
    task_description: str,
    csv_schema: str,
    workspace_dir: str,
    expected_artifacts: list[str] | None = None,
    previous_code: str = None,
    error: str = None,
    use_pro: bool = False
) -> str:
    """
    Calls the Coder agent to produce a script for one atomic task.
    Supports retrying by taking the previous failed code and the error output.
    """
    artifacts_str = ", ".join(expected_artifacts) if expected_artifacts else "none specified"

    user_prompt = f"""CSV Schema:
{csv_schema}

Workspace directory (read from sys.argv[1], do NOT hard-code): {workspace_dir}

Expected output artifact filenames (use these EXACT names): [{artifacts_str}]

Task:
{task_description}
"""
    messages = [
        {"role": "system", "content": CODER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    if previous_code and error:
        retry_prompt = f"""Your previous attempt failed execution.

Previous Code:
```python
{previous_code}
```

Execution Error/Traceback:
{error}

IMPORTANT reminders for your fix:
- Do NOT use inplace=True anywhere (pandas 2.x raises ChainedAssignmentError).
- Save output files with the EXACT expected artifact filenames: [{artifacts_str}]
- Use sys.argv[1] for workspace directory, pathlib.Path for all paths.

Return ONLY the complete corrected Python code. No markdown fences or explanations."""
        messages.append({"role": "user", "content": retry_prompt})

    llm = get_coder_llm(use_pro)
    response = llm.invoke(messages)

    # Strip any markdown code fences if the model generated them despite instructions
    content = response.content.strip()
    if content.startswith("```python"):
        content = content[9:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()
