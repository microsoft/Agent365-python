# Changelog — microsoft-agents-a365-notifications

All notable changes to this package will be documented in this file.

## [2.0.0] - 2026-10-20

### Breaking Changes

- **`AgentLifecycleEvent.USERDELETED` value changed** — it is now
  `"agenticuserdeleted"` (previously `"agenticuseridentitydeleted"`), so
  `on_user_deleted()` handlers match the new event name. Update any code that
  compares against the raw string value.

### Added

- New lifecycle events and handler decorators on `AgentNotification`:
  - `USERUNDELETED` — `on_user_undeleted()`
  - `USERUPDATED` — `on_user_updated()`
  - `USERMANAGERUPDATED` — `on_user_manager_updated()`
  - `USERENABLED` — `on_user_enabled()`
  - `USERDISABLED` — `on_user_disabled()`

### Security

- Raised the minimum `PyJWT` version to `>= 2.14.0`.
