# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for sanitize_text_for_header utility function."""

import pytest
from microsoft_agents_a365.tooling.utils.utility import sanitize_text_for_header


class TestSanitizeTextForHeader:
    """Tests for sanitize_text_for_header."""

    @pytest.mark.unit
    def test_none_returns_none(self):
        assert sanitize_text_for_header(None) is None

    @pytest.mark.unit
    def test_empty_string_returns_none(self):
        assert sanitize_text_for_header("") is None

    @pytest.mark.unit
    def test_whitespace_only_returns_none(self):
        assert sanitize_text_for_header("   ") is None

    @pytest.mark.unit
    def test_plain_ascii_unchanged(self):
        assert sanitize_text_for_header("Hello world") == "Hello world"

    @pytest.mark.unit
    def test_accent_stripped_via_nfd(self):
        assert sanitize_text_for_header("café") == "cafe"

    @pytest.mark.unit
    def test_curly_double_quotes_replaced(self):
        assert sanitize_text_for_header("\u201cHello\u201d") == '"Hello"'

    @pytest.mark.unit
    def test_curly_single_quotes_replaced(self):
        assert sanitize_text_for_header("\u2018it\u2019s\u2018") == "'it's'"

    @pytest.mark.unit
    def test_em_dash_replaced(self):
        assert sanitize_text_for_header("one\u2014two") == "one-two"

    @pytest.mark.unit
    def test_en_dash_replaced(self):
        assert sanitize_text_for_header("one\u2013two") == "one-two"

    @pytest.mark.unit
    def test_ellipsis_replaced(self):
        assert sanitize_text_for_header("wait\u2026") == "wait..."

    @pytest.mark.unit
    def test_nbsp_replaced(self):
        assert sanitize_text_for_header("hello\u00a0world") == "hello world"

    @pytest.mark.unit
    def test_narrow_nbsp_replaced(self):
        assert sanitize_text_for_header("hello\u202fworld") == "hello world"

    @pytest.mark.unit
    def test_whitespace_collapsed(self):
        assert sanitize_text_for_header("a  \t\n  b") == "a b"

    @pytest.mark.unit
    def test_emoji_replaced_with_space_and_collapsed(self):
        assert sanitize_text_for_header("emoji \U0001f600 here") == "emoji here"

    @pytest.mark.unit
    def test_mixed_unicode(self):
        result = sanitize_text_for_header("\u201cHello\u201d \u2014 caf\u00e9!")
        assert result == '"Hello" - cafe!'
