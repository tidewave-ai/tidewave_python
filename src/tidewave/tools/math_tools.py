"""
Mathematical operation tools for MCP
"""


def add(a: float, b: float) -> str:
    """
    Add two numbers together.

    Args:
        a: The first number to add
        b: The second number to add

    Returns:
        A string describing the sum of the two numbers
    """
    result = a + b
    return f"The sum of {a} and {b} is {result}"


def multiply(x: float, y: float, precision: int = 2) -> str:
    """
    Multiply two numbers together.

    Args:
        x: The first number to multiply
        y: The second number to multiply
        precision: Number of decimal places for the result (default: 2)

    Returns:
        A string describing the product of the two numbers
    """
    result = x * y
    if precision == 0:
        result = int(result)
        return f"The product of {x} and {y} is {result}"
    else:
        result = round(result, precision)
        return f"The product of {x} and {y} is {result}"
