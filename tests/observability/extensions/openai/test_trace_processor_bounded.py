# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Standalone test for bounded tool calls functionality.
This test can be run without installing the full package.
"""

from collections import OrderedDict


def capture_tool_call_ids_test(output_list, pending_tool_calls, max_size=1000):
    """Test version of capture_tool_call_ids function."""
    if not output_list:
        return
    try:
        for msg in output_list:
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    for tc in tool_calls:
                        if isinstance(tc, dict):
                            call_id = tc.get("id")
                            func = tc.get("function", {})
                            func_name = func.get("name") if isinstance(func, dict) else None
                            func_args = func.get("arguments", "") if isinstance(func, dict) else ""
                            if call_id and func_name:
                                key = f"{func_name}:{func_args}"
                                pending_tool_calls[key] = call_id
                                # Cap the size of the dict to prevent unbounded growth
                                while len(pending_tool_calls) > max_size:
                                    pending_tool_calls.popitem(last=False)
    except Exception:
        pass


def test_bounded_size():
    """Test that the bounded size logic works correctly."""
    pending_tool_calls = OrderedDict()
    max_size = 10

    print("Testing bounded size functionality...")
    print(f"Max size: {max_size}")

    # Create tool calls that exceed max_size
    for i in range(15):
        output_list = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": f"call_{i}",
                        "function": {
                            "name": f"function_{i}",
                            "arguments": f'{{"arg": {i}}}',
                        },
                    }
                ],
            }
        ]
        capture_tool_call_ids_test(output_list, pending_tool_calls, max_size)
        print(f"After adding call {i}: size = {len(pending_tool_calls)}")

    # Verify the size does not exceed max_size
    assert len(pending_tool_calls) <= max_size, (
        f"Size {len(pending_tool_calls)} exceeds max {max_size}"
    )
    assert len(pending_tool_calls) == max_size, (
        f"Size {len(pending_tool_calls)} should equal max {max_size}"
    )

    print(f"\n✅ Final size: {len(pending_tool_calls)} (max: {max_size})")

    # Verify that the oldest entries were removed (FIFO behavior)
    print("\nVerifying FIFO behavior...")
    for i in range(5):
        key = f'function_{i}:{{"arg": {i}}}'
        assert key not in pending_tool_calls, f"Old entry {key} should have been removed"
        print(f"✅ Entry {i} was correctly removed (oldest)")

    # The last 10 entries should still be present
    for i in range(5, 15):
        key = f'function_{i}:{{"arg": {i}}}'
        assert key in pending_tool_calls, f"Recent entry {key} should be present"
        assert pending_tool_calls[key] == f"call_{i}", f"Call ID mismatch for {key}"
        print(f"✅ Entry {i} is present with correct call_id")

    print("\n✅ All tests passed! Bounded size logic works correctly.")
    return True


def test_single_tool_call():
    """Test storing a single tool call."""
    pending_tool_calls = OrderedDict()
    max_size = 10

    print("\nTesting single tool call...")
    output_list = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_123",
                    "function": {
                        "name": "add_numbers",
                        "arguments": '{"a": 5, "b": 10}',
                    },
                }
            ],
        }
    ]
    capture_tool_call_ids_test(output_list, pending_tool_calls, max_size)

    assert len(pending_tool_calls) == 1
    key = 'add_numbers:{"a": 5, "b": 10}'
    assert key in pending_tool_calls
    assert pending_tool_calls[key] == "call_123"

    print("✅ Single tool call test passed!")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("Running Bounded Tool Calls Tests")
    print("=" * 70)

    try:
        test_bounded_size()
        test_single_tool_call()
        print("\n" + "=" * 70)
        print("🎉 All tests passed successfully!")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        exit(1)
