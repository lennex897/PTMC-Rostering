from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class GenerationRequest:
    roster_month: date
    scheduling_roster_path: Path
    leave_workbook_path: Path
    leave_sheet: str
    rulebook_text: str
    assumptions_text: str
    output_path: Path


@dataclass
class GenerationResult:
    success: bool
    output_path: Path | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    statistics: dict[str, object] = field(default_factory=dict)


def generate_roster(
    request: GenerationRequest,
) -> GenerationResult:
    """
    Temporary generator function.

    The actual scheduling algorithm will be connected later.
    """

    return GenerationResult(
        success=False,
        errors=[
            "The scheduling engine has not yet been connected."
        ],
    )