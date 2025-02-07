from datasets import load_dataset
import re
import json
import random

def find_import_statements(python_code: str) -> list:
    import_pattern = r'^\s*import\s+[a-zA-Z_][a-zA-Z0-9_]*(?:\s+as\s+[a-zA-Z_][a-zA-Z0-9_]*)?'
    from_import_pattern = r'^\s*from\s+[a-zA-Z_][a-zA-Z0-9_]*\s+import\s+[a-zA-Z_][a-zA-Z0-9_]*'
    imports = re.findall(import_pattern, python_code, re.MULTILINE)
    from_imports = re.findall(from_import_pattern, python_code, re.MULTILINE)
    return imports + from_imports + ['import matplotlib as plt']

def extract_function_signature(code_string):
    signature_regex = r"def\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\)"
    match = re.search(signature_regex, code_string)
    return match.group(0) if match else None

class BigCodeLoader:
    def __init__(self, sample_size=148):
        ds_hard = load_dataset("bigcode/bigcodebench-hard", split="v0.1.2", download_mode="force_redownload")
        ds_normal = load_dataset("bigcode/bigcodebench", split="v0.1.2", download_mode="force_redownload")
        
        hard_task_ids = set(item["task_id"] for item in ds_hard)
        unique_ds = [item for item in ds_normal if item["task_id"] not in hard_task_ids]
        
        if len(unique_ds) < sample_size:
            raise ValueError("Not enough unique problems available to sample 148 items.")
        
        selected_problems = random.sample(unique_ds, sample_size)
        
        self.prompts = []
        self.dataset = selected_problems
        self.solutions = []
        self.libs = []
        self.all_imports = []
        
        with open("bigcodebench_subset.jsonl", 'w', encoding='utf-8') as jsonl_file:
            for item in selected_problems:
                self.prompts.append(item['complete_prompt'])
                imports = find_import_statements(item['complete_prompt'])
                self.libs.append(item['libs'])
                for imp in imports:
                    if imp not in self.all_imports:
                        self.all_imports.append(imp)
                try:
                    sol = item['instruct_prompt'].split('```')[1] + item['canonical_solution']
                except Exception:
                    sol = item['instruct_prompt'] + item['canonical_solution']
                self.solutions.append(sol)
                task = {
                    "name": item["task_id"],
                    "language": "py",
                    "prompt": item["complete_prompt"],
                    "libs": item["libs"],
                    "canonical_solution": item["canonical_solution"],
                    "test": item["test"],
                    "entry_point": item["entry_point"]
                }
                jsonl_file.write(json.dumps(task) + '\n')
        print("Dataset loaded as bigcodebench_subset.jsonl")
    
    def get_prompts(self):
        return self.prompts

    def get_dataset(self):
        return self.dataset

    def get_solutions(self):
        return self.solutions

if __name__ == "__main__":
    bigcode = BigCodeLoader()
