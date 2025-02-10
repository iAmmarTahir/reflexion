import json
import argparse

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Merge two JSONL files line by line.")
parser.add_argument("file1_path", type=str, help="Path to the first JSONL file")
parser.add_argument("file2_path", type=str, help="Path to the second JSONL file")
parser.add_argument("output_file_path", type=str, help="Path to the output merged JSONL file")

args = parser.parse_args()

# Function to read JSONL files
def read_jsonl(file_path):
    with open(file_path, "r") as file:
        return [json.loads(line.strip()) for line in file]

# Read both files
data1 = read_jsonl(args.file1_path)
data2 = read_jsonl(args.file2_path)

# Ensure both files have the same number of entries
if len(data1) != len(data2):
    raise ValueError("Files have different numbers of entries.")

# Merge corresponding entries
merged_data = [{**d1, **d2} for d1, d2 in zip(data1, data2)]

# Write merged data to a new JSONL file
with open(args.output_file_path, "w") as file:
    for entry in merged_data:
        file.write(json.dumps(entry) + "\n")

print(f"Merged JSONL file saved to: {args.output_file_path}")
