"""Domain errors shared by the commissioning backend modules."""

from __future__ import annotations


class CommissioningError(Exception):
    """Base class for expected commissioning request failures."""


class CommissioningNotFound(CommissioningError):
    """Raised when a catalogued subsystem, motor, or job does not exist."""


class CommissioningUnavailable(CommissioningError):
    """Raised when a known subsystem does not yet support commissioning."""


class CommissioningValidationError(CommissioningError):
    """Raised when editable configuration or a request is unsafe."""


class CommissioningStorageError(CommissioningError):
    """Raised when a catalogued file cannot be read or replaced."""


class CommissioningRevisionConflict(CommissioningError):
    """Raised when a file changed after the browser loaded its revision."""


class CommissioningBusy(CommissioningError):
    """Raised when another commissioning operation already owns the system."""


class CommissioningStateError(CommissioningError):
    """Raised when an operation is invalid for a job's current state."""
