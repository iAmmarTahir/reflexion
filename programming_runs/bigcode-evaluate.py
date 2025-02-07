import argparse
import json
import multiprocessing
import os
import pickle
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed, wait, FIRST_COMPLETED
from concurrent.futures._base import CancelledError
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional
from warnings import warn
from gradio_client import Client, handle_file
from e2b import Sandbox

import httpx
import numpy as np
from termcolor import cprint
from tqdm import tqdm

from bigcodebench.generate import run_codegen
from bigcodebench.data import (
    get_bigcodebench,
    get_bigcodebench_hash,
    load_solutions,
)
from bigcodebench.data.utils import CACHE_DIR
from bigcodebench.eval import (
    PASS,
    compatible_eval_result,
    estimate_pass_at_k,
    untrusted_check,
)
from bigcodebench.gen.util import trusted_check

# 1st item: the status
# 2nd item (optional): the detailed pass/fail boolean for each input
Result = Tuple[str, List[bool]]


def get_groundtruth(n_workers, problems, hashcode, check_gt_only, max_as_limit, max_data_limit, max_stack_limit, min_time_limit):
    cache_file = os.path.join(CACHE_DIR, f"{hashcode}.pkl")
    if os.path.exists(cache_file):
        if check_gt_only:
            os.remove(cache_file)
        else:
            print(f"Load from ground-truth from {cache_file}")
            with open(cache_file, "rb") as f:
                return pickle.load(f)

    os.makedirs(CACHE_DIR, exist_ok=True)
    print("\nAsserting the groundtruth...")
    tbegin = time.time()
    
    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = []
        n_samples = 0
        expected_time = dict()
        
        for problem in problems.values():
            args = (
                problem["complete_prompt"] + "\n" + problem["canonical_solution"],
                problem["test"],
                problem["task_id"],
                max_as_limit,
                max_data_limit,
                max_stack_limit,
                min_time_limit,
            )
            
            futures.append(executor.submit(trusted_check, *args))
            n_samples += 1

        for future in tqdm(as_completed(futures), total=n_samples):
            result = future.result()
            expected_time[result["task_id"]] = result["time"]
    
    print(f"Expected outputs computed in {time.time() - tbegin:.2f}s")
    
    if any(expected_time.values()):
        with open(cache_file, "wb") as f:
            pickle.dump(expected_time, f)

    return expected_time

def check_correctness(
    completion_id: int,
    problem: Dict[str, Any],
    solution: str,
    max_as_limit: float,
    max_data_limit: float,
    max_stack_limit: float,
    identifier=None,
    min_time_limit: float = 0.1,
    gt_time_limit: float = 2.0,
) -> Dict[str, Result]:  # {...}, "base" | "plus" -> (status, details)
    ret = {
        "completion_id": completion_id,
        "task_id": problem["task_id"],
        "_identifier": identifier,
        "solution": solution,
    }
    ret["base"] = untrusted_check(
        solution,
        problem["test"],
        problem["entry_point"],
        max_as_limit,
        max_data_limit,
        max_stack_limit,
        min_time_limit,
        gt_time_limit,
    )
    return ret


def evaluate(
    split: str,
    subset: str,
    samples: Optional[str] = None,
    no_execute: bool = False,
    execution: str = "gradio", # "e2b", "gradio", "local"
    selective_evaluate: str = "",
    e2b_endpoint: str = "bigcodebench_evaluator",
    gradio_endpoint: str = "https://bigcode-bigcodebench-evaluator.hf.space/",
    pass_k: str = "1,5,10",
    save_pass_rate: bool = True,
    calibrated: bool = True,
    parallel: int = -1,
    min_time_limit: float = 1,
    max_as_limit: int = 30*1024,
    max_data_limit: int = 30*1024,
    max_stack_limit: int = 10,
    check_gt_only: bool = False,
    no_gt: bool = False,
    **model_kwargs,
):  
    if not samples and model_kwargs:
        samples = run_codegen(
            split=split,
            subset=subset,
            **model_kwargs,
        )
    
    if no_execute:
        return
    
    assert samples is not None, "No samples provided"
        
    if os.path.isdir(samples):
        result_path = os.path.join(samples, "eval_results.json")
    else:
        assert samples.endswith(".jsonl")
        result_path = samples.replace(".jsonl", "_eval_results.json")
    
    if execution == "gradio":
        while True:
            try:
                client = Client(gradio_endpoint)
                results, pass_at_k = client.predict(
                    split=split,
                    subset=subset,
                    samples=handle_file(samples),
                    pass_k=pass_k,
                    parallel=parallel,
                    min_time_limit=min_time_limit,
                    max_as_limit=max_as_limit,
                    max_data_limit=max_data_limit,
                    max_stack_limit=max_stack_limit,
                    calibrated=calibrated,
                    check_gt_only=check_gt_only,
                    no_gt=no_gt,
                    selective_evaluate=selective_evaluate,
                    api_name="/predict"
                )
                break
            except (httpx.ReadTimeout, CancelledError):
                print("Read timeout error. Retrying in 4s...")
                time.sleep(4)
        gt_pass_rate = pass_at_k["gt_pass_rate"]
        failed_tasks = pass_at_k["failed_tasks"]
    
    elif execution == "e2b":
        sandbox = Sandbox(e2b_endpoint, api_key=os.environ["E2B_API_KEY"], timeout=60*60)

        # upload file to sandbox
        with open(samples, "r") as file:
            sandbox.files.write(samples, file)
        
        # run the evaluation
        print(f"Command run in sandbox {e2b_endpoint}")
        sandbox.commands.run("bigcodebench.evaluate  --execution 'local' "
                        f"--split {split} --subset {subset} --samples {samples} "
                        f"--pass_k {pass_k} --save_pass_rate {save_pass_rate} --calibrated {calibrated} "
                        f"--parallel {parallel} --selective_evaluate {selective_evaluate} --min_time_limit {min_time_limit} "
                        f"--max_as_limit {max_as_limit} --max_data_limit {max_data_limit} --max_stack_limit {max_stack_limit} "
                        f"--check_gt_only {check_gt_only} --no_gt {no_gt}", on_stderr=lambda x: print(x), on_stdout=lambda x: print(x), timeout=60*50)
        
        if not check_gt_only:
            # download the results
            content = sandbox.files.read(result_path)
            with open(result_path, "w") as file:
                file.write(content)


def main():
    from fire import Fire

    Fire(evaluate)

if __name__ == "__main__":
    main()