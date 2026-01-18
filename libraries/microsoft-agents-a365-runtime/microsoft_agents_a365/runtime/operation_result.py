# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Represents the result of an operation.
"""

from typing import List, Optional

from .operation_error import OperationError


class OperationResult:
    """
    Represents the result of an operation.

    This class encapsulates the success or failure state of an operation along
    with any associated errors.
    """

    _success_instance: Optional["OperationResult"] = None

    def __init__(self, succeeded: bool, errors: Optional[List[OperationError]] = None):
        """
        Initialize a new instance of the OperationResult class.

        Args:
            succeeded: Flag indicating whether the operation succeeded.
            errors: Optional list of errors that occurred during the operation.
        """
        self._succeeded = succeeded
        self._errors = errors if errors is not None else []

    @property
    def succeeded(self) -> bool:
        """
        Get a flag indicating whether the operation succeeded.

        Returns:
            bool: True if the operation succeeded, otherwise False.
        """
        return self._succeeded

    @property
    def errors(self) -> List[OperationError]:
        """
        Get the list of errors that occurred during the operation.

        Note:
            This property returns a defensive copy of the internal error list
            to prevent external modifications, which is especially important for
            protecting the singleton instance returned by success().

        Returns:
            List[OperationError]: A copy of the list of operation errors.
        """
        return list(self._errors)

    @staticmethod
    def success() -> "OperationResult":
        """
        Return an OperationResult indicating a successful operation.

        Returns:
            OperationResult: An OperationResult indicating a successful operation.
        """
        return OperationResult._success_instance

    @staticmethod
    def failed(*errors: OperationError) -> "OperationResult":
        """
        Create an OperationResult indicating a failed operation.

        Args:
            *errors: Variable number of OperationError instances.

        Returns:
            OperationResult: An OperationResult indicating a failed operation.
        """
        error_list = list(errors) if errors else []
        return OperationResult(succeeded=False, errors=error_list)

    def __str__(self) -> str:
        """
        Convert the value of the current OperationResult object to its string representation.

        Returns:
            str: A string representation of the current OperationResult object.
        """
        if self._succeeded:
            return "Succeeded"
        else:
            error_messages = ", ".join(str(error.message) for error in self._errors)
            return f"Failed: {error_messages}" if error_messages else "Failed"


# Module-level eager initialization (thread-safe by Python's import lock)
OperationResult._success_instance = OperationResult(succeeded=True)
