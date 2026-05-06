# Contributing to 202020Reminder

Thanks for your interest in contributing to **202020Reminder**.

This project aims to stay small, useful, privacy-friendly, and easy to maintain. Contributions are welcome, especially if they improve reliability, Windows user experience, documentation, packaging, or accessibility.

## Languages

- Main README: [English](README.md)
- Chinese README: [简体中文](README.zh-CN.md)

When you change user-facing behavior, please update both README files if needed.

## Good first issues

Good areas for new contributors:

- Fix UI text, typos, or translations
- Improve screenshots or README structure
- Add tests for configuration and daily statistics
- Improve Windows packaging and release workflow
- Add auto start on boot
- Add idle detection
- Add dark mode
- Add do-not-disturb mode
- Improve accessibility and keyboard navigation

## Development setup

This project uses `uv`.

```bash
git clone https://github.com/yourname/202020Reminder.git
cd 202020Reminder
uv sync --extra dev
uv run 202020reminder
```

Run tests:

```bash
uv run pytest
```

Run lint checks:

```bash
uv run ruff check .
```

Build a Windows executable:

```bash
uv run pyinstaller --noconsole --onefile --name 202020Reminder --collect-data twenty_twenty_twenty_reminder scripts/run_202020reminder.py
```

## Pull request checklist

Before opening a PR, please check:

- [ ] The change has a clear purpose.
- [ ] The app still starts successfully.
- [ ] `uv run pytest` passes.
- [ ] `uv run ruff check .` passes.
- [ ] UI changes include screenshots or screen recordings when possible.
- [ ] README files are updated if user-facing behavior changed.
- [ ] Privacy expectations are preserved: no analytics, no ads, no data upload.

## Design principles

Please keep the app:

- lightweight
- calm and non-intrusive
- privacy-first
- understandable for non-technical users
- useful as a small tray utility rather than a bloated health platform

## Commit style

There is no strict commit convention yet, but readable prefixes are appreciated:

```text
feat: add auto start option
fix: prevent duplicated break prompts
docs: improve README screenshots
test: add settings validation tests
```

## Reporting bugs

When reporting a bug, please include:

- Windows version
- app version
- how you installed or ran the app
- steps to reproduce
- expected behavior
- actual behavior
- screenshots or logs if available

## Feature requests

For feature requests, please explain:

- the problem you want to solve
- your proposed user interaction
- whether it should be enabled by default
- whether it may interrupt users

Thank you for helping make 202020Reminder better.
