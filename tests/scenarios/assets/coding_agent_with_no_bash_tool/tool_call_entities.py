from pydantic import BaseModel


class ToolCall(BaseModel):
    pass


class FileReadToolCall(ToolCall):
    file_path: str


class FileEditToolCall(ToolCall):
    file_path: str
    old_content: str
    new_content: str


class FileWriteToolCall(ToolCall):
    file_path: str
    content: str


class FinishToolCall(ToolCall):
    message: str