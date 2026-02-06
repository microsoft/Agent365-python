# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for OperationError class."""

import pytest
from microsoft_agents_a365.runtime import OperationError


class TestOperationError:
    """Tests for OperationError class."""

    def test_operation_error_can_be_instantiated(self):
        """Test that OperationError can be instantiated with an exception."""
        # Arrange
        exception = Exception("Test error")

        # Act
        error = OperationError(exception)

        # Assert
        assert error is not None
        assert error.exception == exception
        assert error.message == "Test error"

    def test_operation_error_requires_exception(self):
        """Test that OperationError requires an exception."""
        # Act & Assert
        with pytest.raises(ValueError, match="exception cannot be None"):
            OperationError(None)

    def test_operation_error_string_representation(self):
        """Test that OperationError has correct string representation."""
        # Arrange
        exception = Exception("Test error message")
        error = OperationError(exception)

        # Act
        result = str(error)

        # Assert
        assert "Test error message" in result

    def test_operation_error_with_different_exception_types(self):
        """Test that OperationError works with different exception types."""
        # Arrange & Act
        value_error = OperationError(ValueError("Invalid value"))
        type_error = OperationError(TypeError("Invalid type"))
        runtime_error = OperationError(RuntimeError("Runtime issue"))

        # Assert
        assert value_error.message == "Invalid value"
        assert type_error.message == "Invalid type"
        assert runtime_error.message == "Runtime issue"
