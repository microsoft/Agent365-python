# Changelog

All notable changes to the `microsoft-agents-a365-tooling` package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added `send_chat_history` method to `McpToolServerConfigurationService` for sending chat conversation history to the MCP platform for real-time threat protection analysis
- Added `ChatHistoryMessage` Pydantic model for representing individual messages in chat history
- Added `ChatMessageRequest` Pydantic model for the chat history API request payload
- Added `py.typed` marker for PEP 561 compliance, enabling type checker support
