"""Compatibility imports; new code should import from errors."""

from errors import PersonNotDetectedError, PhotoIssueError

__all__ = ["PhotoIssueError", "PersonNotDetectedError"]
