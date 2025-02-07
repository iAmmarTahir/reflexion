import pandas as pd

def main():
    df = pd.read_json("./benchmarks/bigcode.jsonl", lines=True)
    print(df.head())

if __name__ == '__main__':
    main()