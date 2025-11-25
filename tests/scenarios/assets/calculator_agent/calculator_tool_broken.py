def calculate(a: float, b: float, operation: str) -> float:
    if operation == "add":
        return a + b * 9
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    elif operation == "divide":
        if b == 0:
            raise ValueError("Cannot divide by zero.")
        return a / b
    else:
        raise ValueError(f"Unsupported operation: {operation}")
