import unittest
import os
import sys
import traceback
from io import StringIO
from .executor_utils import function_with_timeout
from typing import List
from .executor_types import ExecuteResult, Executor
import uuid



class UnitTestExecutor(Executor):
    def execute(self, func: str, tests: List[str], timeout: int = 5) -> ExecuteResult:
        _id = str(uuid.uuid4())
        print("|| Begin Executing...")

        imports = (
            'import os\n'
            'os.environ["MPLBACKEND"] = "Agg"\n'  # Force backend
            'from typing import *\n'
        )
        full_code = f'{imports}\n{func}\n' + "\n".join(tests)
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        is_passing = True
        failed_tests = []
        success_tests = []

        try:
            # Create a temp test file
            test_filename = f"temp_test_{_id}.py"
            with open(test_filename, "w") as f:
                f.write(full_code)

            # Dynamically execute the test code
            test_globals = {}
            exec(full_code, test_globals)

            # Create test suite
            suite = unittest.TestSuite()
            test_cases = []
            for name, obj in test_globals.items():
                if isinstance(obj, type) and issubclass(obj, unittest.TestCase):
                    tests = unittest.defaultTestLoader.loadTestsFromTestCase(obj)
                    suite.addTests(tests)
                    test_cases.extend(tests)

            # Run tests
            runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
            result = runner.run(suite)

            # Get failed test names
            failed_tests = [str(test[0]) for test in result.failures + result.errors]

            # Determine successful tests
            all_test_names = {str(test) for test in test_cases}
            failed_test_names = set(failed_tests)
            success_tests = list(all_test_names - failed_test_names)

            # If there are failures, mark as not passing
            if failed_tests:
                is_passing = False

        except Exception as e:
            is_passing = False
            failed_tests.append(str(e))
            traceback.print_exc()
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
            if os.path.exists(test_filename):
                os.remove(test_filename)
        feedback = "TEST OUTPUT: \n" + output + "\nFAILED TESTS: \n" +  ''.join(failed_tests)
        state = {"output": output}
        print("|| End Executing...")
        return ExecuteResult(is_passing, feedback , state)

    def evaluate(self, name: str, func: str, test: str, timeout: int = 1) -> bool:
        """
        Evaluates the implementation on Human-Eval Python.
        """
        code = f"""{func}

{test}
    """
        try:
            global_env = {}
            function_with_timeout(exec, (code, global_env), timeout)
            return True
        except Exception:
            return False



if __name__ == "__main__":
    func = """
from typing import *
import os
import requests
from zipfile import ZipFile, BadZipFile

def task_func(url, download_path="mnt/data/downloads/"):
    return None
    """

    tests = [
    """
import unittest
from unittest.mock import patch
import os

class TestNonZipFileDownload(unittest.TestCase):
    def setUp(self):
        self.url = 'https://example.com/not_a_zip.txt'
        self.download_path = 'mnt/data/downloads/'

    @patch('requests.get')
    def test_non_zip_file_download(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.headers = {'Content-Type': 'text/plain'}
        
        result = task_func(self.url, self.download_path)
        self.assertEqual(result, "Error: The URL does not point to a ZIP file.")
    """
    ]

    executor = UnitTestExecutor()
    
    # Test execute function
    result = executor.execute(func, tests, timeout=2)
    print("Execution Result:", result)

    # Test evaluate function with a single test
    single_test = """
import unittest

class SingleTestCase(unittest.TestCase):
    def test_valid_data(self):
        self.assertEqual(1 + 1, 2)
    """

    eval_result = executor.evaluate("test_valid_data", func, tests, timeout=2)
    print("Evaluation Result:", eval_result)

