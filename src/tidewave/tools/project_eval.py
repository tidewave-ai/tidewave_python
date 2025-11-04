import contextlib
import io
import json as json_module
import multiprocessing
import queue as q
from typing import Any, Optional


def project_eval(
    code: str,
    arguments: Optional[list[Any]] = None,
    timeout: int = 30_000,
    *,
    json: bool = False,
) -> str:
    """
    Evaluates Python code in the context of the project.

    Use this tool every time you need to evaluate Python code,
    including to test the behaviour of a function or to debug
    something. The tool also returns anything written to standard
    output. DO NOT use shell tools to evaluate Python code.

    Arguments:

      * `code`: The Python code to evaluate
      * `arguments`: A list of arguments to pass to evaluation
        They are available inside the evaluated code as `arguments`
      * `timeout`: The maximum time to wait for execution, in milliseconds.
        Defaults to `30_000`
    """

    # Note that we run the code in a separate OS process. This allows
    # us to terminate it once a timeout is reached. If we were to run
    # the code in another thread instead, we would have no clean way
    # of stopping it (other than signals, but those only work on Unix).
    timeout = timeout / 1000  # Convert milliseconds to seconds

    queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=execute_code, args=(code, arguments, queue))
    process.start()

    try:
        output = queue.get(timeout=timeout)
    except q.Empty:
        process.terminate()
        process.join()
        result = f"Code execution timed out after {timeout} seconds"
        success = False
        stdout = ""
        stderr = ""
        error_message = result
    else:
        process.join()
        result = output.get("result", "")
        success = output.get("success", False)
        stdout = output.get("stdout", "")
        stderr = output.get("stderr", "")
        error_message = output.get("error", None)

    if json:
        response = json_module.dumps(
            {
                "result": result,
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
        return "\n".join(output)


# Note: Defined at the module level so it can be used in the multiprocessing context.
def execute_code(code, arguments, queue):
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    result = None
    success = False
    error_message = None

    execution_globals = {
        "__builtins__": __builtins__,
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
