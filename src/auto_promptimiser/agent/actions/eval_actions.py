from pydantic import BaseModel, Field
from auto_promptimiser.core.action import Action


class RunEvalSuiteAction(Action):
    evals_to_run: list[str] = Field(
        default_factory=lambda: ["all"],
        min_length=1,
        description="List of eval IDs to run. default: all evals",
    )
    num_attempts: int = Field(
        default=1,
        ge=1,
        description="Number of times to run each evaluation. Useful for checking stability or giving multiple chances.",
    )


class ProjectBreakdownUpdates(BaseModel):
    """Structured updates to the project breakdown."""
    files: dict[str, str] | None = Field(
        default=None,
        description="Dictionary of file paths to updated descriptions. Only include files that need description updates or are newly created.",
    )
    actions: dict[str, str] | None = Field(
        default=None,
        description="Dictionary of action names to updated descriptions. Include new actions or updated descriptions.",
    )
    known_limitations: dict[str, str] | None = Field(
        default=None,
        description="Dictionary of eval names to reasons why they cannot be fixed. Use this to mark evals that should not be pursued further due to model capability limitations or other fundamental issues.",
    )


class EndIterationAction(Action):
    """Marks the end of an iteration, runs evals, and updates state."""
    changelog_entry: str = Field(
        description="Medium-detail description of changes made during this iteration. Should be specific enough to understand what changed and why.",
    )
    project_breakdown_updates: ProjectBreakdownUpdates = Field(
        description="Structured updates to project breakdown. Update when: new files created, file purposes changed significantly, new actions added, actions deleted, or action descriptions invalidated.",
    )


class UpdateProjectBreakdownAction(Action):
    """Updates the project breakdown immediately, without ending the iteration.

    Use this before dispatching trajectory analysis agents to ensure they have
    current information about the target system's structure and capabilities.
    """
    updates: ProjectBreakdownUpdates = Field(
        description="Structured updates to project breakdown (files and/or actions).",
    )


class ResetToIterationAction(Action):
    """Resets file states and project breakdown back to a previous iteration's snapshot.

    Use this when changes caused regression (multiple evals broke).
    Maximum resets per eval: 1. If second attempt also regresses, mark eval as known limitation.
    The reset will be recorded in iteration history so future context windows know what happened.
    """
    iteration_number: int = Field(
        ge=0,
        description="The iteration number to reset to. Use 0 for initial baseline state.",
    )
    reason: str = Field(
        min_length=50,
        description="Detailed explanation including: (1) what was attempted, (2) what went wrong and which evals broke, (3) what alternative approach you'll try next. This creates a record to avoid repeating failed approaches.",
    )