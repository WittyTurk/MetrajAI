"""Legacy opening-schedule design notes.

This experimental module never contained a working ``OpeningSchedule`` implementation;
it was prose stored as Python and prevented repository-wide syntax validation.  The new
engine lives under :mod:`metrajai` and deliberately does not import this legacy module.
"""


class OpeningSchedule:
    """Fail explicitly instead of silently pretending the legacy feature exists."""

    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs
        raise NotImplementedError(
            "Legacy OpeningSchedule was never implemented. Use the reviewed "
            "architectural workflow in the new MetrajAI engine."
        )
