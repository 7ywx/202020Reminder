# 202020Reminder

<p align="center">
  <img src="docs/images/hero.png" alt="202020Reminder hero" width="920" />
</p>

<p align="center">
  <strong>A tiny Windows tray app that helps you protect your eyes with the 20-20-20 rule.</strong>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows-2563eb">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-3776ab">
  <img alt="PySide6" src="https://img.shields.io/badge/UI-PySide6-41cd52">
  <img alt="uv" src="https://img.shields.io/badge/package%20manager-uv-7c3aed">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-16a34a">
  <img alt="Privacy" src="https://img.shields.io/badge/privacy-local--only-0f766e">
  <img alt="Status" src="https://img.shields.io/badge/status-MVP-orange">
</p>

<p align="center">
  <a href="#download">Download</a> ·
  <a href="#screenshots">Screenshots</a> ·
  <a href="#features">Features</a> ·
  <a href="#quick-start-for-developers">Quick Start</a> ·
  <a href="#roadmap">Roadmap</a> ·
  <a href="#contributing">Contributing</a>
</p>

---

## Why 202020Reminder?

Long screen sessions make it easy to forget to blink, look away, or take a short break. **202020Reminder** keeps the 20-20-20 rule visible and lightweight:

- **Simple and lightweight**: no account, no cloud service, no complicated health dashboard
- **Windows tray app**: runs quietly in the background
- **Clear countdowns**: 20-minute eye-use countdown and 20-second break countdown
- **Flexible reminders**: tray notification, popup reminder, and fullscreen overlay
- **Local-only statistics**: completed breaks, skipped breaks, snoozes, total rest time, and completion rate
- **Privacy-first**: no ads, no account, no tracking

> This project is not medical software and is not a substitute for professional diagnosis or treatment.

---

## Table of contents

- [202020Reminder](#202020reminder)
  - [Why 202020Reminder?](#why-202020reminder)
  - [Table of contents](#table-of-contents)
  - [Download](#download)
    - [For normal users](#for-normal-users)
    - [For developers](#for-developers)
  - [Screenshots](#screenshots)
    - [Interface overview](#interface-overview)
    - [Main screens](#main-screens)
  - [How it works](#how-it-works)
  - [Features](#features)
  - [Quick start for developers](#quick-start-for-developers)
  - [Build a Windows executable](#build-a-windows-executable)
  - [Project structure](#project-structure)
  - [Roadmap](#roadmap)
  - [Privacy-first](#privacy-first)
  - [Contributing](#contributing)
  - [Star history](#star-history)
  - [License](#license)

---

## Download

### For normal users

Download the latest **`202020Reminder.exe`** from **GitHub Releases** and run it directly.

> Python is not required if you use the packaged executable.

### For developers

Clone the repository and run it with `uv`:

```bash
git clone https://github.com/yourname/202020Reminder.git
cd 202020Reminder
uv sync
uv run 202020reminder
```

---

## Screenshots

### Interface overview

<p align="center">
  <img src="docs/images/screenshots/all-interfaces-overview.png" alt="202020Reminder interface overview" width="1000" />
</p>

### Main screens


| Control panel                                                                           | Settings                                                                                    |
| ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| <img src="docs/images/screenshots/control-panel.png" alt="Control panel" width="480" /> | <img src="docs/images/screenshots/settings-dialog.png" alt="Settings dialog" width="480" /> |


| Break prompt                                                                          | Fullscreen break overlay                                                                              |
| --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| <img src="docs/images/screenshots/break-prompt.png" alt="Break prompt" width="480" /> | <img src="docs/images/screenshots/fullscreen-break.png" alt="Fullscreen break overlay" width="480" /> |

---

## How it works

```text
Launch app
→ Click Start
→ 20-minute countdown begins
→ Reminder appears at 00:00
→ Click “Start 20-second break”
→ 20-second countdown begins
→ Break complete prompt appears
→ Start the next round or pause
```

202020Reminder uses a **confirmation-based break flow**. When the 20-minute countdown ends, the app reminds you first. The 20-second break timer starts only after you confirm that you are ready to rest. This avoids counting a break while you are still finishing a task.

---

## Features

- Windows tray app that keeps running in the background
- Visible 20-minute countdown and progress bar
- 20-second break countdown
- Tray notification, popup reminder, and fullscreen overlay
- Today’s local statistics:
  - completed breaks
  - skipped breaks
  - snoozed reminders
  - total rest time
  - completion rate
  - longest continuous focus time
- Settings for:
  - focus duration
  - break duration
  - snooze duration
  - reminder modes
  - sound
  - always-on-top behavior
- Minimize-to-taskbar and hide-to-tray behavior
- Built with PySide6
- `uv`-first developer workflow
- MIT licensed

---

## Quick start for developers

Install `uv` first:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Run the project:

```bash
git clone https://github.com/yourname/202020Reminder.git
cd 202020Reminder
uv sync
uv run 202020reminder
```

Run as a module:

```bash
uv run python -m twenty_twenty_twenty_reminder
```

Run tests and lint checks:

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

---

## Build a Windows executable

```bash
uv sync --extra dev
uv run pyinstaller --noconsole --onefile --name 202020Reminder --collect-data twenty_twenty_twenty_reminder scripts/run_202020reminder.py
```

The executable will be generated here:

```text
dist/202020Reminder.exe
```

You can also use the included GitHub Actions workflow to build release artifacts automatically.

---

## Project structure

```text
202020Reminder/
├─ src/twenty_twenty_twenty_reminder/
│  ├─ app.py
│  ├─ config.py
│  ├─ assets/
│  │  └─ icon.svg
│  ├─ __init__.py
│  └─ __main__.py
├─ scripts/
│  └─ run_202020reminder.py
├─ tests/
│  └─ test_config.py
├─ docs/images/
│  ├─ hero.svg
│  ├─ icon.svg
│  └─ screenshots/
├─ .github/
│  ├─ workflows/release.yml
│  └─ ISSUE_TEMPLATE/
├─ pyproject.toml
├─ CONTRIBUTING.md
├─ LICENSE
├─ README.md
└─ README.zh-CN.md
```

---

## Roadmap

- [X] Windows tray app
- [X] 20-minute countdown
- [X] 20-second break timer
- [X] Daily local statistics
- [X] Popup / notification / fullscreen reminder modes
- [X] Control panel and settings dialog
- [X] GitHub-friendly screenshots and bilingual README
- [ ] Auto start on boot
- [ ] Idle detection
- [ ] Multi-language UI inside the app
- [ ] Portable `.exe` release
- [ ] Dark mode
- [ ] Fullscreen app detection / do-not-disturb mode
- [ ] Pause for 30 minutes / 1 hour / 2 hours
- [ ] Better break-completion encouragement

---

## Privacy-first

**202020Reminder does not collect, upload, sell, or share any data.**

All settings and statistics are stored locally on your computer. There is no account system, no analytics SDK, no ads, and no tracking.

---

## Contributing

Contributions are welcome. Good first contributions include:

- fixing UI text or translations
- improving README screenshots
- adding tests for configuration and statistics
- improving Windows packaging
- implementing roadmap items such as auto start, idle detection, or dark mode

Before opening a pull request:

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

Please keep pull requests focused and include screenshots or screen recordings for UI changes.

See [CONTRIBUTING.md](CONTRIBUTING.md) for more details.

---

## Star history

If this project helps you, consider giving it a star. It helps more people discover a small, privacy-friendly eye-care tool.

---

## License

MIT License. See [LICENSE](LICENSE).
