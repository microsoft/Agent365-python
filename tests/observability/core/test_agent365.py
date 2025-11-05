# Copyright (c) Microsoft. All rights reserved.


from microsoft_agents_a365.observability.core import configure
from microsoft_agents_a365.observability.core.trace_processor import SpanProcessor


def test_basic_functionality():
    """Test basic Agent365 SDK functionality"""
    print("Testing Agent365 SDK...")

    # Test configure function
    try:
        configure(
            service_name="test-service",
            service_namespace="test-namespace",
        )
        print("✅ configure() executed successfully")
    except Exception as e:
        print(f"❌ configure() failed: {e}")
        return False

    # Test SpanProcessor class
    try:
        SpanProcessor()
        print("✅ SpanProcessor created successfully")
    except Exception as e:
        print(f"❌ SpanProcessor creation failed: {e}")
        return False

    print("✅ All tests passed!")
    return True


if __name__ == "__main__":
    test_basic_functionality()
