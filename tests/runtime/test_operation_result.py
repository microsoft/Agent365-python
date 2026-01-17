# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for OperationResult class."""

from microsoft_agents_a365.runtime import OperationError, OperationResult


class TestOperationResult:
    """Tests for OperationResult class."""

    def test_operation_result_success(self):
        """Test that OperationResult.success() returns a successful result."""
        # Act
        result = OperationResult.success()

        # Assert
        assert result is not None
        assert result.succeeded is True
        assert len(result.errors) == 0

    def test_operation_result_success_returns_singleton(self):
        """Test that OperationResult.success() returns the same instance."""
        # Act
        result1 = OperationResult.success()
        result2 = OperationResult.success()

        # Assert
        assert result1 is result2

    def test_operation_result_failed_with_no_errors(self):
        """Test that OperationResult.failed() without errors returns a failed result."""
        # Act
        result = OperationResult.failed()

        # Assert
        assert result is not None
        assert result.succeeded is False
        assert len(result.errors) == 0

    def test_operation_result_failed_with_single_error(self):
        """Test that OperationResult.failed() with a single error works correctly."""
        # Arrange
        exception = Exception("Test error")
        error = OperationError(exception)

        # Act
        result = OperationResult.failed(error)

        # Assert
        assert result is not None
        assert result.succeeded is False
        assert len(result.errors) == 1
        assert result.errors[0] == error

    def test_operation_result_failed_with_multiple_errors(self):
        """Test that OperationResult.failed() with multiple errors works correctly."""
        # Arrange
        error1 = OperationError(Exception("Error 1"))
        error2 = OperationError(Exception("Error 2"))
        error3 = OperationError(Exception("Error 3"))

        # Act
        result = OperationResult.failed(error1, error2, error3)

        # Assert
        assert result is not None
        assert result.succeeded is False
        assert len(result.errors) == 3
        assert result.errors[0] == error1
        assert result.errors[1] == error2
        assert result.errors[2] == error3

    def test_operation_result_success_string_representation(self):
        """Test that successful OperationResult has correct string representation."""
        # Act
        result = OperationResult.success()

        # Assert
        assert str(result) == "Succeeded"

    def test_operation_result_failed_string_representation_no_errors(self):
        """Test that failed OperationResult without errors has correct string representation."""
        # Act
        result = OperationResult.failed()

        # Assert
        assert str(result) == "Failed"

    def test_operation_result_failed_string_representation_with_errors(self):
        """Test that failed OperationResult with errors has correct string representation."""
        # Arrange
        error1 = OperationError(Exception("Error 1"))
        error2 = OperationError(Exception("Error 2"))

        # Act
        result = OperationResult.failed(error1, error2)

        # Assert
        result_str = str(result)
        assert "Failed" in result_str
        assert "Error 1" in result_str
        assert "Error 2" in result_str
