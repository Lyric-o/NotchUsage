# NotchUsage

<p align="center">
  A tiny native macOS notch widget for Claude and Codex usage.
</p>

<p align="center">
  <strong>Claude 5h · Claude weekly · Codex weekly</strong><br>
  Live usage, reset times, hover details, and launch at login.
</p>

## Demo

[Watch the 31-second product demo](demo/NotchUsage-demo.mp4)

The demo shows the compact notch view, hover details, reset times, manual
refresh, and launch-at-login control.

## What it does

NotchUsage sits around the MacBook notch without taking space from your desktop.

- Claude on the left, Codex on the right
- Compact numbers while idle
- Progress bars and reset times on hover
- Click the notch strip to request a manual refresh
- Starts automatically when you log in
- Native SwiftUI and AppKit — no Electron, no background server

## Requirements

- A MacBook with a notch
- macOS 14 or later
- Xcode Command Line Tools
- Claude Code signed in locally
- Codex CLI signed in locally

The app reads your existing local Claude and Codex authentication. Tokens stay in
memory and are never written by NotchUsage or sent anywhere except the official
Anthropic and OpenAI usage endpoints.

## Install

```bash
git clone https://github.com/Lyric98/NotchUsage.git
cd NotchUsage
./install.sh
```

The installer builds a release version, copies it to
`~/Applications/NotchUsage.app`, and opens it.

To rebuild after pulling an update:

```bash
git pull
./install.sh
```

## Usage

- **Hover** over the notch strip to reveal progress bars and reset times.
- **Click** the visible notch strip to request fresh usage from both services.
- Use the **menu bar icon** to refresh, toggle launch at login, or quit.

Codex is checked locally every 5 seconds and against the service every minute or
when manually refreshed. Claude is checked against its official usage endpoint
every minute or when manually refreshed. If a service rate-limits the request,
the last successful real value is preserved.

## Data sources

| Service | Primary source | Fallback |
| --- | --- | --- |
| Claude | `api.anthropic.com/api/oauth/usage` | Last successful value |
| Codex | `chatgpt.com/backend-api/wham/usage` | Latest local `rate_limits` event |

Claude credentials are read from the macOS Keychain entry created by Claude
Code. Codex credentials are read from `~/.codex/auth.json`. No credentials are
included in the repository or application bundle.

## Build manually

```bash
./build-app.sh
open dist/NotchUsage.app
```

The project is a Swift Package and can also be compiled with:

```bash
swift build -c release
```

## Uninstall

Quit NotchUsage, disable **Launch at Login** from its menu if enabled, then remove:

```bash
rm -r ~/Applications/NotchUsage.app
```

## Privacy

NotchUsage does not include analytics, telemetry, advertising, or a third-party
backend. Usage requests go directly from your Mac to the official service
endpoints.

## License

[MIT](LICENSE)
