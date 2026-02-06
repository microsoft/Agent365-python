# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Encapsulates an error from an operation.
"""


class OperationError:
    """
    Represents an error that occurred during an operation.

    This class wraps an exception and provides a consistent interface for
    accessing error information.
    """

    def __init__(self, exception: Exception):
        """
        Initialize a new instance of the OperationError class.

        Args:
            exception: The exception associated with the error.

        Raises:
            ValueError: If exception is None.
        """
        if exception is None:
            raise ValueError("exception cannot be None")
        self._exception = exception

    @property
    def exception(self) -> Exception:
        """
        Get the exception associated with the error.

        Returns:
            Exception: The exception associated with the error.
        """
        return self._exception

    @property
    def message(self) -> str:
        """
        Get the message associated with the error.

        Returns:
            str: The error message from the exception.
        """
        return str(self._exception)

    def __str__(self) -> str:
        """
        Return a string representation of the error.

        Returns:
            str: A string representation of the error.
        """
        return str(self._exception)
