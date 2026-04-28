"""Rollback engine: restore the file system to a point in a captured session."""

from rewind.rollback.engine import (
    PlannedFileChange,
    RollbackAction,
    RollbackOutcome,
    RollbackPlan,
    plan_rollback,
    restore,
    safety_errors_from,
    undo_last,
)
from rewind.rollback.safety import (
    SafetyError,
    check_paths_within_cwd,
    check_uncommitted_changes,
)

__all__ = [
    "PlannedFileChange",
    "RollbackAction",
    "RollbackOutcome",
    "RollbackPlan",
    "SafetyError",
    "check_paths_within_cwd",
    "check_uncommitted_changes",
    "plan_rollback",
    "restore",
    "safety_errors_from",
    "undo_last",
]
