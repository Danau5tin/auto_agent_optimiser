from typing import List, Optional
from pydantic import BaseModel, Field

from auto_promptimiser.core.action import Action

class ReadAction(Action):
    """Read a file."""

    file_path: str = Field(..., min_length=1)
    offset: Optional[int] = Field(None, ge=0)
    limit: Optional[int] = Field(None, gt=0)


class WriteAction(Action):
    """Write to a file."""

    file_path: str = Field(..., min_length=1)
    content: str = Field(...)


class EditAction(Action):
    """Edit a file."""

    file_path: str = Field(..., min_length=1)
    old_string: str = Field(...)
    new_string: str = Field(...)
    replace_all: bool = Field(False)


class EditOperation(BaseModel):
    """Single edit operation for multi-edit."""

    old_string: str
    new_string: str
    replace_all: bool = False


class MultiEditAction(Action):
    """Multiple edits to a single file."""

    file_path: str = Field(..., min_length=1)
    edits: List[EditOperation] = Field(..., min_length=1)
