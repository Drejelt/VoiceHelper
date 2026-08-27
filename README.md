# VoiceHelper

> A local Russian-language desktop voice assistant with a FastAPI control panel. Speech is recognized on-device with Vosk; the panel binds localhost only.

![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-blue)
![Language](https://img.shields.io/badge/language-python3.10+-green)
![STT](https://img.shields.io/badge/stt-vosk-orange)
![Panel](https://img.shields.io/badge/panel-localhost%20only-lightgrey)

VoiceHelper listens on a wake word, maps Russian speech to a fixed set of desktop and info commands, and speaks the result. A small web panel on `127.0.0.1:8000` edits config, JSON state, and logs. Keywords run first. An LLM is optional and only picks a tool from that closed set — it does not chat and it does not execute anything. Cloud APIs are otherwise used where a local equivalent is not wired in — weather, Gemini fairy tales, and gTTS.

This is a personal project, not a product. Treat the panel as a local admin surface, not something to publish.

---

## Contents

- [Why](#why)
- [Architecture](#architecture)
- [Security model](#security-model)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Voice commands](#voice-commands)
- [Configuration](#configuration)
- [Admin panel](#admin-panel)
- [File layout](#file-layout)
- [Known gaps](#known-gaps)
- [Troubleshooting](#troubleshooting)

---

## Why

Cloud voice assistants are easy, but they take the microphone off the machine and they are not built to drive *this* desktop — tabs, volume, alarms, shutdown. VoiceHelper keeps STT local (Vosk + WebRTC VAD), keeps the control plane on loopback, and lets you change the wake word and defaults from a browser on the same host.

The panel exists because a JSON file you have to edit by hand is how these projects rot. Config, alarms, reminders, custom command text, and logs are reachable from one place — behind HTTP Basic, and only from localhost.

---

## Architecture

```
microphone
    │
    ▼
┌──────────┐    ┌───────────┐    ┌──────────────────┐
│ PyAudio  │ ─► │ webrtcvad │ ─► │ Vosk (local STT) │
└──────────┘    └───────────┘    └────────┬─────────┘
                                          │ wake word
                                          ▼
                                   CommandProcessor
                                          │
                          keywords hit? ──┬── no, LLM on? ── tool pick
                                          │                    │
                                          ▼                    ▼
                                   closed tools (execute locally)
                                          │
         ┌────────────┬─────────────┬─────┴──────┬──────────────┐
         ▼            ▼             ▼            ▼              ▼
   InfoServices  Scheduler   MediaController  SystemCtrl   Entertainment
   weather/wiki  alarms      browser/hotkeys  screenshot   jokes/Gemini
         │
         ▼
   gTTS / pyttsx3  ──► speaker

127.0.0.1:8000   FastAPI + HTTP Basic  ──►  admin panel
```

The assistant process and the panel share one Python runtime: `uvicorn` loads `control:app`, which starts `VoiceAssistant` on a background thread. There is no separate daemon.

---

## Security model

The panel can rewrite config and read logs, so the default is deny-from-the-network:

- **Loopback only.** Requests whose peer is not `127.0.0.1` / `::1` get `403`. Binding `0.0.0.0` does not make the panel reachable.
- **HTTP Basic on every API route**, including files, logs, commands, and restart — not only `/admin`.
- **Passwords are bcrypt.** A leftover `admin`/`admin` hash from older checkouts is rotated on startup. Set `ADMIN_PASSWORD` or read the generated password from the log.
- **No secrets in git.** API keys live in `api_keys.env`. The SQLite user DB and the old `credentials.json` are gitignored.
- **Path allowlists.** JSON edits are restricted to four filenames under `json/`. Log view/delete only accepts `*.log` basenames under `logs/`.
- **Power commands are off.** Shutdown, reboot, and logout via voice require `ALLOW_POWER_COMMANDS=1`.

> Known gap: media control still injects keystrokes with pyautogui into whatever window is focused, including Alt+F4. HTTP Basic over HTTP is acceptable only because the socket is loopback. There is no session, CSRF token, or rate limit.

---

## Requirements

| | |
|---|---|
| OS | Linux (tested) or macOS |
| Python | 3.10+ |
| Hardware | a working microphone |
| STT model | [Vosk `vosk-model-small-ru-0.22`](https://alphacephei.com/vosk/models) unpacked under `model/` |
| Optional keys | OpenWeather (`WEATHER_API`), Gemini (`GOOGLE_API_KEY`) or any OpenAI-compatible endpoint (`LLM_API_BASE` + `LLM_API_KEY`) |
| Linux packages | `python3-dev`, `portaudio19-dev`, `python3-pyaudio`, `xdotool` |

---

## Quick start

Linux packages:

```bash
sudo apt-get update
sudo apt-get install python3-dev portaudio19-dev python3-pyaudio xdotool
```

macOS:

```bash
brew install portaudio
pip install pyaudio
```

Then:

```bash
pip install -r requirements.txt
python3 -m spacy download ru_core_news_sm

mkdir -p model sounds
# unpack vosk-model-small-ru-0.22 into model/vosk-model-small-ru-0.22
# put an alarm.mp3 into sounds/

cp .env.example api_keys.env
# fill WEATHER_API, GOOGLE_API_KEY, ADMIN_PASSWORD

uvicorn control:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Login is `admin`. The password is `ADMIN_PASSWORD`, or the one-time value printed at first start if that variable is empty.

Do not pass `--host 0.0.0.0`. The loopback check will reject non-local peers anyway.

---

## Voice commands

The wake word is `AI_NAME` in `json/model_config.json` (default `шут`). Utterances that do not contain it are ignored.

| Area | Examples |
|---|---|
| Time / alarms / reminders | текущее время; поставь будильник на 7:30; напомни …; покажи напоминания |
| Info | погода в …; курс доллара; что такое … / википедия |
| Browser / media | открой ютуб; включи музыку; найди видео …; пауза; громче; полный экран |
| Desktop | скриншот; выключи компьютер; перезагрузи; выйти из системы |
| Talk | привет; шутка; сказку; брось монетку |

Desktop power commands do nothing unless `ALLOW_POWER_COMMANDS=1`. Media actions are YouTube-oriented hotkeys sent to the focused window.

Custom phrases stored in the panel (`json/custom_commands.json`) are **not** executed by the voice loop yet — they are only edited there.

If the utterance is not a known keyword and `GOOGLE_API_KEY` (or `LLM_API_BASE`) is set, the model is asked to pick **one** tool. Timeout 3s, 12 calls/min, circuit opens after 3 failures. Usage lands in `logs/llm.jsonl` (`latency_ms`, token counts, tool, error). No key, a dead API, or an invented tool name → keywords-only, the assistant does not freeze.

---

## Configuration

Runtime knobs live in `json/model_config.json`. The panel's config form writes the same file.

```json
{
  "MODEL_PATH": "model/vosk-model-small-ru-0.22",
  "AI_NAME": "шут",
  "SAMPLE_RATE": 16000,
  "BUFFER_SIZE": 4000,
  "FRAME_DURATION_MS": 20,
  "VAD_MODE": 3,
  "DEFAULT_CITY": "киев",
  "DEFAULT_CURRENCY": "UAH",
  "RESTART_TIMEOUT": 30,
  "logging_enabled": true,
  "LLM_ENABLED": true,
  "LLM_MODEL": "gemini-2.0-flash"
}
```

Secrets are not in that file:

```
# api_keys.env  (gitignored; start from .env.example)
WEATHER_API=
GOOGLE_API_KEY=
ADMIN_PASSWORD=
ALLOW_POWER_COMMANDS=0
# LLM_ENABLED=0
# LLM_API_BASE=
# LLM_API_KEY=
# LLM_MODEL=
```

`RESTART_TIMEOUT` is idle minutes after which the audio stack is torn down and reopened. Alarms and reminders are separate JSON files, not the SQLite DB — SQLite is only the admin user.

---

## Admin panel

`GET /` and `GET /admin` both require Basic auth and then serve the dashboard.

| Route | Purpose |
|---|---|
| `/config`, `/api/config` | Read / write `model_config.json` |
| `/api/files/{filename}` | Read / write allowlisted JSON under `json/` |
| `/api/commands` | Edit `custom_commands.json` |
| `/api/logs/list`, `/view`, `/delete` | Daily log files under `logs/` |
| `/api/restart` | Reload assistant config |
| `/api/update_credentials` | Change admin username and password (min 8 chars) |

Changing credentials does not rewrite `api_keys.env`; `ADMIN_PASSWORD` is only the bootstrap value.

---

## File layout

| Path | Purpose |
|------|---------|
| `control.py` | FastAPI app, auth, file/log API |
| `main.py` | Capture, VAD, STT, command dispatch, TTS |
| `models.py` | SQLite user table (`html/database/voice_assistant.db`) |
| `functional_modules/intent.py` | Closed tools + keyword match + execute |
| `functional_modules/llm.py` | Tool-call extract, limits, `logs/llm.jsonl` |
| `functional_modules/` | Weather, media, scheduler, entertainment, system |
| `tests/` | Intent + LLM unit tests |
| `json/model_config.json` | Wake word, Vosk path, defaults |
| `json/alarms.json`, `json/reminders.json` | Scheduler state |
| `json/custom_commands.json` | Panel-edited phrases (not wired to STT) |
| `html/templates/`, `html/static/` | Admin UI |
| `api_keys.env` | Secrets (gitignored) |
| `model/` | Vosk model (gitignored) |
| `sounds/alarm.mp3` | Alarm clip (gitignored) |
| `logs/` | Rotating / daily logs (gitignored) |

---

## Known gaps

Boundaries, not a feature list:

- **Custom commands are storage-only.** The panel writes `custom_commands.json`; `CommandProcessor` never reads it.
- **Matching is keywords first.** spaCy still fills some entities. Unmatched wake-word phrases can go to the LLM as tool selection only. Overlapping keywords still win by dict order.
- **gTTS needs the network.** pyttsx3 is the fallback and often sounds worse.
- **Gemini model names drift.** `LLM_MODEL` is configurable; the default is `gemini-2.0-flash`.

---

## Troubleshooting

**401 on every panel request.**
The browser has no Basic credentials, or you are still using `admin`/`admin` after a rotation. Check the startup log for the generated password, or set `ADMIN_PASSWORD` and remove the user row so it can be recreated.

**403 from another machine.**
Expected. The panel refuses non-loopback peers. Use SSH local forwarding if you must reach it remotely: `ssh -L 8000:127.0.0.1:8000 host`.

**"API ключ от погоды потерялся" / fairy tales fail.**
`api_keys.env` is missing, unreadable, or the names are not `WEATHER_API` / `GOOGLE_API_KEY`. The file is loaded from the repo root, not from `functional_modules/`.

**Vosk fails at startup.**
`MODEL_PATH` must point at an unpacked model directory, typically `model/vosk-model-small-ru-0.22`, not the zip.

**Alarm is silent.**
`sounds/alarm.mp3` is required by `Scheduler`. The path is not configurable yet.

**"Выключи компьютер" does nothing.**
`ALLOW_POWER_COMMANDS` is `0`. Set it to `1` only if you actually want voice-triggered shutdown.

**Panel config form does not save.**
The UI talks to `/api/config`, which is an alias of `/config` and requires the same Basic auth the browser already stored for `/admin`.

**LLM never fires.**
Keywords already matched, `LLM_ENABLED=0`, or there is no `GOOGLE_API_KEY` / `LLM_API_KEY`. Check `logs/llm.jsonl`. After three timeouts the circuit stays open for 60s.

## Tests

```bash
python3 -m unittest discover -s tests
```
