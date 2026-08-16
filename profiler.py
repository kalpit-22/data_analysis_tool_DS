import os
import pandas as pd

def profile_csv(csv_path: str) -> str:
    """
    Reads a CSV and generates a lightweight Markdown schema 
    designed specifically for LLM context windows.
    Raises FileNotFoundError if the file does not exist,
    ValueError if the file is empty or cannot be parsed.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Could not locate file at: {csv_path}")
    
    try:
        # Load the dataset
        df = pd.read_csv(csv_path)
    except pd.errors.EmptyDataError:
        raise ValueError(f"The CSV file at {csv_path} is empty.")
    except Exception as e:
        raise ValueError(f"Failed to parse CSV file at {csv_path}: {e}")

    try:
        # 1. Basic Dimensions
        schema = f"### Dataset Profile: `data.csv`\n"
        schema += f"- **Total Rows:** {df.shape[0]}\n"
        schema += f"- **Total Columns:** {df.shape[1]}\n\n"
        
        # 2. Column Metadata (Types, Missing Values, and Notes)
        schema += "#### Schema & Data Types:\n\n"
        
        # Build notes for each column regarding data types and issues
        notes = []
        for col in df.columns:
            inferred = pd.api.types.infer_dtype(df[col])
            col_type = str(df[col].dtype)
            if col_type == 'object':
                if inferred == 'mixed':
                    notes.append("WARNING: Mixed data types detected. Ensure proper casting.")
                elif inferred in ('date', 'datetime'):
                    notes.append("NOTE: Contains date/time strings. Parse with pd.to_datetime().")
                else:
                    notes.append("Text/string data.")
            elif col_type.startswith('float') or col_type.startswith('int'):
                if inferred == 'mixed-integer':
                    notes.append("WARNING: Mixed integer/float data detected.")
                else:
                    notes.append("Numeric data.")
            else:
                notes.append(f"Inferred: {inferred}")

        info_df = pd.DataFrame({
            'Data Type': df.dtypes.astype(str),
            'Missing Values': df.isnull().sum(),
            'Notes / Warnings': notes
        })
        schema += f"{info_df.to_markdown()}\n\n"
        
        # 3. Data Sample (First 3 Rows)
        schema += "#### Sample Data (First 3 Rows):\n\n"
        schema += df.head(3).to_markdown() + "\n"
        
        return schema
    except Exception as e:
        raise ValueError(f"Error profiling data from {csv_path}: {e}")

# Keep generate_data_profile as an alias for backwards compatibility if needed
generate_data_profile = profile_csv

# ==========================================
# Test Execution (Runs only if executed directly)
# ==========================================
if __name__ == "__main__":
    target_csv = "enterprise_sales_data.csv"
    print(f"Extracting LLM-friendly schema for '{target_csv}'...\n")
    try:
        profile = profile_csv(target_csv)
        print(profile)
    except Exception as e:
        print(f"Profiler error: {e}")