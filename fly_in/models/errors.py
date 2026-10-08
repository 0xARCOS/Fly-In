"""Exceptions raised while reading and validating maps."""


class MapError(Exception):
    """Root of every map-related error (I/O or content)."""


class MapParseError(MapError):
    """Parse error on a specific line of the map file.

    It always carries the original line (number + content) and the cause,
    as Chap. VII.4 requires: "a clear error message indicating the line and
    cause".
    """

    def __init__(self, line_num: int, line_content: str, reason: str) -> None:
        """Create the error.

        Args:
            line_num: Line number in the original file (1-based).
            line_content: Text of the line, with the comment stripped.
            reason: Cause of the failure.
        """
        self.line_num = line_num
        self.line_content = line_content
        self.reason = reason
        super().__init__(f"Line {line_num}: '{line_content}' -> {reason}")


class MapValidationError(MapError):
    """The file fails as a whole (empty, no start_hub, no path…).

    Unlike `MapParseError`, there is no single line to point at: the check
    can only be done after reading the whole file.
    """
