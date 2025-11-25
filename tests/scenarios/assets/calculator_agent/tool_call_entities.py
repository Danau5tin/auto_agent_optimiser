from pydantic import BaseModel

class ToolCall(BaseModel):
    pass

class CalculatorToolCall(ToolCall):
    float_a: float
    float_b: float
    operation: str
