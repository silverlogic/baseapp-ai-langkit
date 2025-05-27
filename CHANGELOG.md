# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.2.4] - 2024-05-27

### Added

- Keyword arguments added to the slack_process_incoming_user_slack_message task and some other methods. This allows to pass additional context, like a placeholder message that is to be overwritten with the final bot answer.
- process_message returns the exception if there was any.

### Fixed

- Private channel identifier in tests changed to "DXXXXXXXXXM"


## [0.2.3] - 2024-05-09

### Added

- Now workflow nodes (workers and agents) can define a specific LLM model for themselves.
- Compatibility with version 0.3 of `langchain-openai`, which introduced native support for formatted_output with `Pydantic`. This eliminates the need for auxiliary properties like `min_length` and `default`.

### Fixed

- Synthesizer prompt conditional rule adjustment to also check empty lists of selected nodes.


## [0.2.2] - 2024-05-07

### Fixed

- Slack App now it optional


## [0.2.1] - 2024-04-25

### Added
- Slack bot integration feature
  - New Django app `baseapp_ai_langkit.slack` for Slack integration
  - Support for Slack webhook events handling
  - Integration with existing AI chat functionality
  - Support for both direct messages and channel conversations
  - Thread-based conversation support
  - Message reactions handling
  - Bot user detection and handling
  - Error handling and user feedback
  - Comprehensive test coverage

### Features
- **Slack Event Handling**
  - Support for `message` events
  - Support for `app_mention` events
  - Support for `reaction_added` and `reaction_removed` events
  - URL verification for Slack webhooks
  - Event status tracking and management

- **User Management**
  - Automatic user creation/update from Slack profiles
  - Bot user detection and filtering
  - User context preservation across conversations

- **Message Processing**
  - Asynchronous message processing using Celery
  - Message formatting and chunking for long responses
  - Thread-based conversation tracking
  - Message reaction tracking and handling

- **Security**
  - Slack request signature verification
  - Secure webhook handling
  - Bot token management

### Technical Details
- New models:
  - `SlackEvent`: Tracks incoming Slack events
  - `SlackEventStatus`: Manages event processing status
  - `SlackAIChat`: Links Slack conversations with AI chat sessions
  - `SlackAIChatMessage`: Stores message history
  - `SlackAIChatMessageReaction`: Tracks message reactions

- New controllers and handlers:
  - `SlackInstanceController`: Manages Slack API interactions
  - `SlackAIChatController`: Connects Slack events with LLM models
  - Various event callback handlers for different event types

- New interfaces:
  - `BaseSlackChatInterface`: Base interface for Slack chat runners

- New views:
  - `SlackWebhookViewSet`: Handles incoming Slack webhook requests

### Dependencies
- Added `slack-sdk` for Slack API integration
- Requires Celery for asynchronous task processing
- Requires Django REST framework for API endpoints
