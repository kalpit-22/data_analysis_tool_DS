"""
DataPilot Main Orchestrator (main.py)

Ties the entire self-correcting agentic loop together:
1. Profiles the target CSV file.
2. Generates an ordered execution plan of atomic steps.
3. For each step:
   - Requests code from the Coder Agent.
   - Runs the code safely inside the sandbox executor.
   - Checks output files and tracebacks with the Reviewer Agent.
   - Retries with self-correction feedback if execution fails.
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

from profiler import profile_csv
from planner import plan_tasks
from coder import generate_code
from executor import prepare_workspace, run_script, verify_artifacts, WORKSPACE_DIR
from reviewer import review

load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        description="DataPilot: An autonomous self-correcting data analysis assistant."
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Path to the target CSV dataset file"
    )
    parser.add_argument(
        "--request",
        default=None,
        help="Natural language data analysis request"
    )
    args = parser.parse_args()

    # Interactive prompts when flags aren't provided
    csv_input = args.csv
    if not csv_input:
        csv_input = input("📂 Enter the path to your CSV file: ").strip()
        if not csv_input:
            print("Error: No CSV file path provided.")
            sys.exit(1)

    request_input = args.request
    if not request_input:
        request_input = input("🔍 What would you like to analyze? Describe in plain English:\n> ").strip()
        if not request_input:
            print("Error: No analysis request provided.")
            sys.exit(1)

    csv_path = Path(csv_input).resolve()
    if not csv_path.exists():
        print(f"Error: Target CSV file not found: {csv_path}")
        sys.exit(1)

    print("\n" + "="*50)
    print("      DataPilot: Autonomous Analysis Initialization")
    print("="*50)

    # 1. Prepare Workspace Environment
    print(f"\n[+] Preparing workspace sandbox at {WORKSPACE_DIR}...")
    try:
        prepare_workspace(str(csv_path))
        print("    Workspace prepared and input CSV copied as 'data.csv'.")
    except Exception as e:
        print(f"[-] Workspace preparation failed: {e}")
        sys.exit(1)

    # 2. Extract CSV Schema Profile
    print("\n[+] Profiling dataset schema...")
    try:
        schema = profile_csv(str(csv_path))
        print("\n===== Dataset Profile =====\n")
        print(schema)
        # Optionally keep concise success line
        print("    Dataset profiled successfully.")
    except Exception as e:
        print(f"[-] Profiling failed: {e}")
        sys.exit(1)

    # 3. Request execution plan from DeepSeek Planner (Flash)
    print("\n[+] Generating analysis plan from DeepSeek Planner Agent (Flash)...")
    try:
        plan = plan_tasks(request_input, schema)
        print("[DEBUG] Planner returned plan with", len(plan.steps), "steps")
        if not plan.steps:
            print("⚠️ No steps returned by planner – aborting.")
            sys.exit(1)
        # Derive unique artifact filenames from each step's name so that
        # parallel aggregation / plot steps never collide.
        for step in plan.steps:
            # Normalise step name to a safe snake_case base
            safe = step.step_name.lower().replace(" ", "_").replace("-", "_")
            name = step.step_name.lower()
            if "clean" in name:
                step.expected_artifacts = [f"{safe}.csv"]
            elif "aggregate" in name or "group" in name:
                step.expected_artifacts = [f"{safe}.csv"]
            elif "chart" in name or "plot" in name:
                step.expected_artifacts = [f"{safe}.png"]
            # Otherwise keep whatever the LLM already provided
        
        print(f"    Generated {len(plan.steps)} step(s):\n")
        for i, step in enumerate(plan.steps, 1):
            print(f"    {i}. {step.step_name}")
            print(f"       Description: {step.description}")
            if step.expected_artifacts:
                print(f"       Expected Outputs: {step.expected_artifacts}")
            print()
    except Exception as e:
        print(f"[-] Planning failed: {e}")
        sys.exit(1)

    # 4. Self-Correcting Execution Loop
    max_retries = int(os.getenv("MAX_RETRIES_PER_TASK", "3"))
    results_summary = []
    
    print("="*50)
    print("             Executing Plan Steps")
    print("="*50)

    for i, step in enumerate(plan.steps, 1):
        print(f"\n>>> [Step {i}/{len(plan.steps)}] {step.step_name}")
        print(f"    Task: {step.description}")
        
        script_path = WORKSPACE_DIR / step.step_name
        code = None
        error_context = None
        success = False
        
        for attempt in range(1, max_retries + 1):
            print(f"    [Attempt {attempt}/{max_retries}] Generating code...")
            try:
                # Generate code from Coder (cloud DeepSeek V4 Pro)
                code = generate_code(
                    task_description=step.description,
                    csv_schema=schema,
                    workspace_dir=str(WORKSPACE_DIR),
                    expected_artifacts=step.expected_artifacts,
                    previous_code=code,
                    error=error_context
                )
                
                # Write to disk inside sandbox
                script_path.write_text(code, encoding="utf-8")
                
                # Run the generated script
                print("    Running script in sandbox...")
                exec_result = run_script(str(script_path))
                
                # Verify any expected artifacts
                print("    Verifying outputs...")
                artifact_check = verify_artifacts(step.expected_artifacts)
                
                # Review results (DeepSeek Flash)
                print("    Reviewing results...")
                review_result = review(step.description, exec_result, artifact_check)
                
                if review_result.approved:
                    print("    [+] Step Approved!")
                    success = True
                    break
                else:
                    print(f"    [-] Reviewer Rejected: {review_result.reason}")
                    if review_result.retry_suggestion:
                        print(f"        Suggestion: {review_result.retry_suggestion}")
                    
                    # Accumulate error context for retry prompt
                    error_context = (
                        f"stdout:\n{exec_result.get('stdout', '')}\n"
                        f"stderr:\n{exec_result.get('stderr', '')}\n"
                        f"returncode: {exec_result.get('returncode')}\n"
                        f"Reviewer rejection feedback:\n{review_result.reason}"
                    )
            except Exception as e:
                print(f"    [-] Execution or generation error: {e}")
                error_context = str(e)
        
        if success:
            results_summary.append((step.step_name, "SUCCESS"))
        else:
            print(f"\n[!] Critical: Step {step.step_name} failed all {max_retries} attempts.")
            results_summary.append((step.step_name, "FAILED"))
            # Keep executing subsequent steps, but alert
            
    # 5. Final Report Summary
    print("\n" + "="*50)
    print("               Final Execution Summary")
    print("="*50)
    all_passed = True
    for name, status in results_summary:
        print(f"  - {name}: {status}")
        if status == "FAILED":
            all_passed = False
            
    print("\nSandbox outputs are saved at:")
    print(f"  {WORKSPACE_DIR}")
    
    if all_passed:
        print("\n[+] SUCCESS: DataPilot successfully completed all planned steps!")
        sys.exit(0)
    else:
        print("\n[-] WARNING: Some steps failed. Please review the sandbox directory and logs above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
