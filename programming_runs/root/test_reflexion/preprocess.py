import json

def replace_name_with_task_id(input_file, output_file):
    """
    Replace 'name' with 'task_id' in a JSONL file.
    
    Args:
        input_file (str): Path to the input JSONL file.
        output_file (str): Path to the output JSONL file.
    """
    with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
        for line in infile:
            entry = json.loads(line)
            if "name" in entry:
                entry["task_id"] = entry.pop("name")
            json.dump(entry, outfile)
            outfile.write('\n')

# Example usage
input_file = './bigcodebench._reflexion_2_gpt-4_pass_at_k_1_py.jsonl'  # Replace with the path to your input JSONL file
output_file = 'bigcodebench.jsonl'  # Replace with the desired output JSONL file
replace_name_with_task_id(input_file, output_file)
