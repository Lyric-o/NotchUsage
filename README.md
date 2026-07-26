<h1 align="center">NotchUsage ✦</h1>

<p align="center">
  <strong>Your Claude and Codex limits, right where you already look.</strong>
</p>

<p align="center">
  A tiny native macOS widget that lives around the MacBook notch.<br>
  Quiet by default. Detailed on hover. Fresh on click.
</p>

<p align="center">
  <img alt="macOS 14+" src="https://img.shields.io/badge/macOS-14%2B-111111?style=flat&logo=apple&logoColor=white">
  <img alt="Swift 6" src="https://img.shields.io/badge/Swift-6.0-F05138?style=flat&logo=swift&logoColor=white">
  <img alt="Native SwiftUI" src="https://img.shields.io/badge/UI-SwiftUI-0D96F6?style=flat&logo=swift&logoColor=white">
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-2F855A?style=flat"></a>
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#privacy">Privacy</a>
</p>

---

## 1. 🎬 See it in action

<!-- The GitHub user-attachments URL inserted here renders as a native inline video player. -->
https://github.com/user-attachments/assets/1ae90079-1e49-40f3-a6c1-3d088bb2b3b1

<p align="center">
  <em>Claude on the left. Codex on the right. The desktop stays yours.</em>
</p>

## 2. ✨ What it feels like

NotchUsage turns an awkward piece of screen hardware into a calm status surface.
You see only the numbers while working; move the pointer to the notch when you
want progress bars, reset times, or a little more context.

| Moment | What appears |
| --- | --- |
| 💤 **Idle** | Compact Claude 5-hour, Claude weekly, and Codex percentages |
| 👀 **Hover** | Progress bars plus exact reset times |
| ↻ **Click** | A fresh request for both providers |
| ⚠️ **Rate limited** | A live retry countdown without request spam |
| 🔑 **Token expired** | A clear sign-in instruction while the last good value stays visible |

> [!NOTE]
> Manual refresh respects an active server cooldown. Clicking repeatedly will
> never bypass `Retry-After` or make a rate limit worse.

## 3. 🪶 Why it stays out of the way

- **85 pt per provider** — designed around the physical notch, not over it
- **Numbers first** — bars appear only when you ask for detail
- **Native macOS** — SwiftUI + AppKit, with no Electron or background server
- **Every Space** — visible across desktops and full-screen apps
- **Launch at login** — enabled once, controllable from the menu bar
- **Last-good-value cache** — temporary network trouble does not erase useful data

<a id="install"></a>

## 4. 🚀 Install

### Requirements

- A MacBook with a notch
- macOS 14 or later
- Xcode Command Line Tools
- Claude Code signed in locally
- Codex CLI signed in locally

### One-minute setup

```bash
git clone https://github.com/Lyric-o/NotchUsage.git
cd NotchUsage
./install.sh
```

The installer builds a release version, copies it to
`~/Applications/NotchUsage.app`, signs it locally, and opens it.

Pulling an update is just as small:

```bash
git pull
./install.sh
```

## 5. 🧭 Use

- **Hover** over the notch strip to reveal progress bars and reset times.
- **Click** the visible strip to request fresh Claude and Codex usage.
- Use the **menu bar icon** to refresh, open the configuration, toggle
  **Launch at Login**, or quit.

The compact strip does not open a large click-blocking area. The detail panel
exists only while the pointer is at the notch.

<a id="how-it-works"></a>

## 6. ⚙️ How it works

| Provider | Live source | Local fallback |
| --- | --- | --- |
| **Claude** | `api.anthropic.com/api/oauth/usage` | Last successful response |
| **Codex** | `chatgpt.com/backend-api/wham/usage` | Latest local `rate_limits` event |

NotchUsage checks local state every 5 seconds and requests authoritative service
usage about once per minute. A manual click requests fresh data immediately
unless that provider is inside a server-directed cooldown.

Each provider owns its own retry state:

- `429` → honor `Retry-After`, otherwise use bounded exponential backoff
- `401` / `403` → show the provider-specific sign-in instruction
- success → clear the warning and resume normal polling

Credentials are read fresh for each request. When Claude Code or Codex refreshes
its own login, NotchUsage reconnects on the next eligible poll.

<a id="privacy"></a>

## 7. 🔒 Privacy

Your credentials stay on your Mac.

- Claude credentials are read from the macOS Keychain entry created by Claude Code.
- Codex credentials are read from `~/.codex/auth.json`.
- Tokens are kept in memory only and are never written by NotchUsage.
- Requests go directly to the official Anthropic and OpenAI endpoints.
- No analytics, telemetry, advertising, third-party backend, or account proxy.

## 8. 🛠 Build from source

```bash
./build-app.sh
open dist/NotchUsage.app
```

Or compile the Swift package directly:

```bash
swift build -c release
```

## 9. 🧹 Uninstall

Quit NotchUsage, disable **Launch at Login** from the menu if enabled, then run:

```bash
rm -r ~/Applications/NotchUsage.app
```

Your Claude Code and Codex credentials are untouched.

## 10. 📄 License

Released under the [MIT License](LICENSE).

<p align="center">
  <strong>Your limits. In sight, not in the way.</strong>
</p>
