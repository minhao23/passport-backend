"""Compatibility imports; new code should import from errors."""

from errors import PhotoIssueError, PersonNotDetectedError

__all__ = ["PhotoIssueError", "PersonNotDetectedError"]
