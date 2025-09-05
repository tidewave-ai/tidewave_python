import contextlib
import io
import json as json_module
import multiprocessing
from typing import Any, Optional


def project_eval(
    code: str,
    arguments: Optional[list[Any]] = None,
    timeout: int = 30,
    as_json: bool = False,
) -> str:
    """
    Execute Python code with optional arguments and timeout.

    Args:
            code (str): The Python code to execute.
            arguments (Optional[list[Any]]): The arguments to pass to the code.
            timeout (int): The maximum time to wait for execution, in seconds.
            json (bool): Whether to return the result as JSON.

    Returns:
            Result of execution (str or JSON)
    """

    queue = multiprocessing.Queue()
    process = multiprocessing.Process(
        target=execute_code, args=(code, arguments, queue)
    )
    process.start()
    process.join(timeout)

    if process.is_alive():
        process.terminate()
        process.join()
        result = f"Code execution timed out after {timeout} seconds"
        success = False
        stdout = ""
        stderr = ""
        error_message = result
    else:
        output = queue.get() if not queue.empty() else {}
        result = output.get("result", "")
        success = output.get("success", False)
        stdout = output.get("stdout", "")
        stderr = output.get("stderr", "")
        error_message = output.get("error", None)

    if as_json:
        response = json_module.dumps(
            {
                "result": str(result) if result is not None else "",
                "success": success,
                "stdout": stdout,
                "stderr": stderr,
                "error": error_message,
            }
        )
        return response
    elif not stdout and not stderr:
        return str(result)
    else:
        output = [
            f"STDOUT:\n{stdout}",
            f"STDERR:\n{stderr}",
            f"Result:\n{str(result)}",
        ]
        return "".join(output)


# Note: Defined at the module level so it can be used in the multiprocessing context.
def execute_code(code, arguments, queue):
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    result = None
    success = False
    error_message = None

    execution_globals = {
        "__builtins__": __builtins__,  # ⚠️ Potential security risk.
        "arguments": arguments or [],
    }

    try:
        with (
            contextlib.redirect_stdout(stdout_capture),
            contextlib.redirect_stderr(stderr_capture),
        ):
            try:
                result = eval(code, execution_globals)
                success = True
            except SyntaxError:
                exec(code, execution_globals)
                result = execution_globals.get("result", "Code executed successfully")
                success = True
    except Exception as e:
        error_message = str(e)
        result = error_message
        success = False
    queue.put(
        {
            "result": result,
            "success": success,
            "stdout": stdout_capture.getvalue(),
            "stderr": stderr_capture.getvalue(),
            "error": error_message,
        }
    )
