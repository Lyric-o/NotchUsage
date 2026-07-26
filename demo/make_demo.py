#!/usr/bin/env python3
"""Render the English launch film for NotchUsage."""

from __future__ import annotations

import math
import random
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


W, H = 1440, 900
FPS = 24
DURATION = 30
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo" / "NotchUsage-demo.mp4"

FONT_SANS = "/System/Library/Fonts/SFNS.ttf"
FONT_ROUNDED = "/System/Library/Fonts/SFNSRounded.ttf"
FONT_SERIF = "/System/Library/Fonts/NewYork.ttf"

NIGHT = (10, 12, 15)
NIGHT_2 = (17, 20, 25)
PANEL = (24, 27, 32)
PANEL_2 = (31, 35, 42)
IVORY = (242, 238, 230)
IVORY_2 = (215, 209, 199)
MUTED = (143, 149, 158)
HAIRLINE = (255, 255, 255, 24)
RUST = (188, 76, 52)
RUST_BRIGHT = (231, 112, 80)
CLAUDE = (218, 124, 85)
CODEX = (85, 203, 164)
BLUE = (103, 145, 255)
BLACK = (2, 3, 4)
REPO = "github.com/Lyric-o/NotchUsage"
CLONE = "git clone https://github.com/Lyric-o/NotchUsage.git"


@lru_cache(maxsize=None)
def fnt(size: int, family: str = "sans"):
    path = {
        "sans": FONT_SANS,
        "rounded": FONT_ROUNDED,
        "serif": FONT_SERIF,
    }[family]
    return ImageFont.truetype(path, size)


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def ease(value: float) -> float:
    value = clamp(value)
    return value * value * (3 - 2 * value)


def phase(t: float, start: float, end: float) -> float:
    return ease((t - start) / (end - start))


def fade(t: float, start: float, end: float, edge: float = 0.65) -> float:
    return phase(t, start, start + edge) * (1 - phase(t, end - edge, end))


def lerp(a: float, b: float, amount: float) -> float:
    return a + (b - a) * amount


def mix(a: tuple[int, int, int], b: tuple[int, int, int], amount: float):
    return tuple(int(lerp(a[i], b[i], amount)) for i in range(3))


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def line(draw, points, fill=HAIRLINE, width=1):
    draw.line(points, fill=fill, width=width)


def tracking(draw, xy, text, font, fill, spacing=2):
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        x += draw.textlength(char, font=font) + spacing


def alpha_composite(base: Image.Image, layer: Image.Image, opacity: float):
    if opacity <= 0:
        return
    if opacity < 1:
        layer = layer.copy()
        channel = layer.getchannel("A").point(lambda pixel: int(pixel * opacity))
        layer.putalpha(channel)
    base.alpha_composite(layer)


def make_background() -> Image.Image:
    image = Image.new("RGBA", (W, H), NIGHT + (255,))
    draw = ImageDraw.Draw(image, "RGBA")
    for y in range(H):
        amount = y / H
        color = mix((17, 20, 25), (8, 10, 13), amount)
        draw.line((0, y, W, y), fill=color + (255,))
    for x in range(0, W + 1, 72):
        line(draw, (x, 0, x, H), (255, 255, 255, 8))
    for y in range(0, H + 1, 72):
        line(draw, (0, y, W, y), (255, 255, 255, 8))
    rng = random.Random(18)
    for _ in range(820):
        x, y = rng.randrange(W), rng.randrange(H)
        draw.point((x, y), fill=(255, 255, 255, rng.randrange(3, 13)))

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow, "RGBA")
    gd.ellipse((845, -250, 1545, 450), fill=(178, 66, 45, 58))
    gd.ellipse((-220, 520, 500, 1240), fill=(65, 117, 111, 27))
    glow = glow.filter(ImageFilter.GaussianBlur(115))
    image.alpha_composite(glow)
    return image


BACKGROUND = make_background()


def brand(draw, y=54, light=True):
    fg = IVORY if light else NIGHT
    rounded(draw, (64, y, 88, y + 24), 7, RUST)
    rounded(draw, (70, y + 5, 82, y + 12), 4, BLACK)
    draw.text((102, y - 1), "NotchUsage", font=fnt(20, "rounded"), fill=fg)


def top_meta(draw, chapter: str, label: str):
    brand(draw)
    tracking(draw, (1132, 59), f"{chapter}  /  {label.upper()}", fnt(11), IVORY_2, 1.6)
    line(draw, (64, 98, 1376, 98), HAIRLINE)


def section_label(draw, number: str, label: str, x: int, y: int):
    rounded(draw, (x, y, x + 42, y + 24), 12, (188, 76, 52, 38), (231, 112, 80, 90))
    draw.text((x + 21, y + 12), number, font=fnt(11, "rounded"), fill=RUST_BRIGHT, anchor="mm")
    tracking(draw, (x + 57, y + 5), label.upper(), fnt(11), MUTED, 1.7)


def label_pill(draw, x, y, text, color, width=None):
    if width is None:
        width = int(draw.textlength(text, font=fnt(11, "rounded"))) + 28
    rounded(draw, (x, y, x + width, y + 28), 14, (*color, 25), (*color, 78))
    draw.ellipse((x + 11, y + 11, x + 17, y + 17), fill=color)
    draw.text((x + 23, y + 6), text, font=fnt(11, "rounded"), fill=IVORY_2)
    return width


def device(
    draw,
    box,
    *,
    hover=0.0,
    refresh=0.0,
    claude_5h=82,
    claude_week=64,
    codex=73,
    pointer=None,
):
    x1, y1, x2, y2 = box
    width, height = x2 - x1, y2 - y1

    # Layered display frame.
    rounded(draw, (x1 - 10, y1 - 10, x2 + 10, y2 + 10), 30, (3, 4, 6), (255, 255, 255, 33), 2)
    rounded(draw, (x1, y1, x2, y2), 22, (18, 21, 27))

    # A restrained desktop wallpaper.
    for row in range(int(height)):
        amount = row / max(1, height)
        color = mix((34, 39, 50), (17, 21, 28), amount)
        draw.line((x1 + 1, y1 + row, x2 - 1, y1 + row), fill=color)
    draw.ellipse((x2 - 420, y1 - 250, x2 + 140, y1 + 310), fill=(166, 72, 54, 36))
    draw.ellipse((x1 - 180, y2 - 300, x1 + 380, y2 + 260), fill=(48, 115, 107, 24))

    # Minimal menu bar details.
    draw.text((x1 + 18, y1 + 11), "●  ●  ●", font=fnt(8), fill=(255, 255, 255, 45))
    draw.text((x2 - 22, y1 + 10), "9:41", font=fnt(9, "rounded"), fill=(220, 224, 229), anchor="ra")

    center = (x1 + x2) // 2
    compact_w = min(704, int(width * 0.68))
    compact_x1, compact_x2 = center - compact_w // 2, center + compact_w // 2
    compact_y = y1
    notch_w = min(216, int(width * 0.21))
    notch_h = 43
    bar_h = 52

    # The app lives around the physical notch.
    rounded(draw, (compact_x1, compact_y, compact_x2, compact_y + bar_h), 17, (1, 2, 3), (255, 255, 255, 24))
    rounded(draw, (center - notch_w // 2, compact_y, center + notch_w // 2, compact_y + notch_h), 15, BLACK)
    draw.rectangle((center - notch_w // 2, compact_y, center + notch_w // 2, compact_y + 18), fill=BLACK)

    small = fnt(11, "rounded")
    value = fnt(12, "rounded")
    draw.text((compact_x1 + 19, compact_y + 10), "Claude", font=value, fill=IVORY)
    draw.text(
        (center - notch_w // 2 - 18, compact_y + 29),
        f"5h {claude_5h}%    W {claude_week}%",
        font=small,
        fill=CLAUDE,
        anchor="ra",
    )
    right_x = center + notch_w // 2 + 19
    draw.text((right_x, compact_y + 10), "Codex", font=value, fill=IVORY)
    draw.text((compact_x2 - 18, compact_y + 28), f"{codex}%", font=value, fill=CODEX, anchor="ra")

    if refresh > 0:
        spinner_alpha = int(255 * math.sin(refresh * math.pi))
        r = 8
        draw.arc(
            (center - r, compact_y + 34 - r, center + r, compact_y + 34 + r),
            -50,
            245,
            fill=(242, 238, 230, spinner_alpha),
            width=2,
        )

    if hover > 0:
        full_y = compact_y + bar_h - 2
        full_h = int(190 * hover)
        rounded(
            draw,
            (center - 392, full_y, center + 392, full_y + full_h),
            22,
            (14, 16, 20),
            (255, 255, 255, 28),
        )
        if hover > 0.52:
            content_alpha = int(255 * phase(hover, 0.52, 1))
            divider = (255, 255, 255, int(25 * phase(hover, 0.52, 1)))
            line(draw, (center, full_y + 24, center, full_y + 163), divider)
            _provider_details(
                draw,
                center - 358,
                full_y + 24,
                "CLAUDE",
                CLAUDE,
                [("5-hour window", f"{claude_5h}%", "Today, 6:40 PM"), ("Weekly", f"{claude_week}%", "Friday, 4:13 PM")],
                content_alpha,
            )
            _provider_details(
                draw,
                center + 34,
                full_y + 24,
                "CODEX",
                CODEX,
                [("Weekly allowance", f"{codex}%", "Friday, 4:13 PM")],
                content_alpha,
            )
            draw.text(
                (center + 34, full_y + 126),
                "Authoritative service value",
                font=fnt(11, "rounded"),
                fill=(*MUTED, content_alpha),
            )

    if pointer is not None:
        px, py, click = pointer
        if click > 0:
            radius = 14 + click * 26
            draw.ellipse(
                (px - radius, py - radius, px + radius, py + radius),
                outline=(*RUST_BRIGHT, int(165 * (1 - click))),
                width=2,
            )
        points = [
            (px, py),
            (px + 3, py + 26),
            (px + 10, py + 19),
            (px + 18, py + 34),
            (px + 24, py + 30),
            (px + 16, py + 16),
            (px + 28, py + 14),
        ]
        draw.polygon(points, fill=IVORY, outline=(15, 17, 20))


def _provider_details(draw, x, y, name, color, rows, alpha):
    tracking(draw, (x, y), name, fnt(10), (*color, alpha), 1.3)
    yy = y + 34
    for label, value, reset in rows:
        draw.text((x, yy), label, font=fnt(15, "rounded"), fill=(*IVORY, alpha))
        draw.text((x + 318, yy), value, font=fnt(15, "rounded"), fill=(*color, alpha), anchor="ra")
        draw.text((x, yy + 25), f"Resets {reset}", font=fnt(11, "rounded"), fill=(*MUTED, alpha))
        yy += 68


def floating_card(draw, box, title, body, accent=RUST, index=None):
    x1, y1, x2, y2 = box
    shadow = (x1 + 4, y1 + 10, x2 + 4, y2 + 10)
    rounded(draw, shadow, 22, (0, 0, 0, 50))
    rounded(draw, box, 22, PANEL, (255, 255, 255, 23))
    if index is not None:
        rounded(draw, (x1 + 24, y1 + 24, x1 + 58, y1 + 58), 10, (*accent, 26), (*accent, 68))
        draw.text((x1 + 41, y1 + 41), index, font=fnt(11, "rounded"), fill=accent, anchor="mm")
    draw.text((x1 + 24, y1 + 80), title, font=fnt(19, "rounded"), fill=IVORY)
    draw.multiline_text((x1 + 24, y1 + 117), body, font=fnt(13, "rounded"), fill=MUTED, spacing=8)


def intro(t: float) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    brand(draw)
    label_pill(draw, 1162, 52, "NATIVE macOS", BLUE, 214)

    reveal = phase(t, 0.25, 1.1)
    x = int(86 - (1 - reveal) * 28)
    section_label(draw, "00", "A quieter way to know", x, 176)
    draw.multiline_text(
        (x, 226),
        "AI limits,\nat a glance.",
        font=fnt(73, "serif"),
        fill=IVORY,
        spacing=2,
    )
    draw.multiline_text(
        (x + 4, 418),
        "Claude and Codex usage, shaped around\nthe place your eyes already visit.",
        font=fnt(20, "rounded"),
        fill=IVORY_2,
        spacing=11,
    )
    label_pill(draw, x + 4, 504, "Live service values", CODEX)
    label_pill(draw, x + 175, 504, "One-click refresh", CLAUDE)

    device(draw, (720, 188, 1370, 650), claude_5h=82, claude_week=64, codex=73)
    draw.text((724, 694), "Designed for the MacBook notch.", font=fnt(13, "rounded"), fill=MUTED)
    line(draw, (86, 800, 1374, 800), HAIRLINE)
    tracking(draw, (86, 824), "OPEN SOURCE  ·  MIT LICENSE  ·  NO TELEMETRY", fnt(11), MUTED, 1.4)
    draw.text((1374, 822), "2026", font=fnt(12, "rounded"), fill=IVORY_2, anchor="ra")
    return layer


def quiet(t: float) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    top_meta(draw, "01", "The quiet default")
    section_label(draw, "01", "The quiet default", 74, 148)
    draw.text((74, 199), "Only the numbers", font=fnt(46, "serif"), fill=IVORY)
    draw.text((74, 255), "until you want more.", font=fnt(42, "serif"), fill=IVORY_2)
    draw.multiline_text(
        (78, 334),
        "Claude stays on the left.\nCodex stays on the right.\nThe notch stays useful.",
        font=fnt(18, "rounded"),
        fill=MUTED,
        spacing=12,
    )
    line(draw, (78, 464, 390, 464), HAIRLINE)
    draw.text((78, 490), "5h", font=fnt(26, "rounded"), fill=CLAUDE)
    draw.text((145, 496), "short window", font=fnt(13, "rounded"), fill=MUTED)
    draw.text((78, 545), "W", font=fnt(26, "rounded"), fill=CLAUDE)
    draw.text((145, 551), "weekly window", font=fnt(13, "rounded"), fill=MUTED)
    draw.text((78, 600), "%", font=fnt(26, "rounded"), fill=CODEX)
    draw.text((145, 606), "remaining allowance", font=fnt(13, "rounded"), fill=MUTED)
    device(draw, (470, 162, 1364, 716), claude_5h=82, claude_week=64, codex=73)
    rounded(draw, (470, 752, 1364, 810), 18, (255, 255, 255, 10), (255, 255, 255, 18))
    draw.text((494, 772), "Compact by default", font=fnt(14, "rounded"), fill=IVORY)
    draw.text((1340, 772), "85 pt per side", font=fnt(13, "rounded"), fill=MUTED, anchor="ra")
    return layer


def context(t: float) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    top_meta(draw, "02", "Hover for context")
    section_label(draw, "02", "Hover for context", 74, 142)
    draw.text((74, 190), "Move closer.", font=fnt(55, "serif"), fill=IVORY)
    draw.text((74, 252), "See the whole cycle.", font=fnt(55, "serif"), fill=IVORY_2)

    hover = phase(t, 8.9, 10.4)
    px = int(lerp(1232, 735, phase(t, 8.1, 9.4)))
    py = int(lerp(724, 188, phase(t, 8.1, 9.4)))
    device(
        draw,
        (184, 351, 1256, 777),
        hover=hover,
        claude_5h=82,
        claude_week=64,
        codex=73,
        pointer=(px, py, 0),
    )
    if hover > 0.7:
        label_pill(draw, 1060, 195, "Local reset times", BLUE, 196)
        line(draw, (1160, 223, 1050, 361), (103, 145, 255, 100), 1)
    draw.text(
        (74, 820),
        "Reset moments appear in your local time zone — and disappear when you leave.",
        font=fnt(14, "rounded"),
        fill=MUTED,
    )
    return layer


def refresh_scene(t: float) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    top_meta(draw, "03", "Refresh on demand")
    section_label(draw, "03", "Refresh on demand", 74, 142)
    draw.text((74, 190), "Click once.", font=fnt(55, "serif"), fill=IVORY)
    draw.text((74, 252), "Ask both services.", font=fnt(46, "serif"), fill=IVORY_2)

    local = t - 14.0
    move = phase(local, 0.4, 1.4)
    px = int(lerp(1160, 714, move))
    py = int(lerp(610, 202, move))
    click = math.sin(phase(local, 1.55, 2.25) * math.pi) if 1.55 <= local <= 2.25 else 0
    refreshing = math.sin(phase(local, 1.85, 3.55) * math.pi) if 1.85 <= local <= 3.55 else 0
    value_change = phase(local, 3.25, 4.0)
    codex = round(lerp(74, 73, value_change))
    device(
        draw,
        (460, 148, 1370, 588),
        refresh=refreshing,
        claude_5h=82,
        claude_week=64,
        codex=codex,
        pointer=(px, py, click),
    )

    status_y = 648
    statuses = [
        ("ANTHROPIC", "5-hour + weekly limits", CLAUDE, "UPDATED"),
        ("OPENAI", "Codex allowance", CODEX, "UPDATED"),
    ]
    for index, (provider, detail, color, status) in enumerate(statuses):
        x = 460 + index * 462
        rounded(draw, (x, status_y, x + 438, status_y + 116), 20, PANEL, (255, 255, 255, 23))
        draw.ellipse((x + 24, status_y + 28, x + 34, status_y + 38), fill=color)
        tracking(draw, (x + 48, status_y + 24), provider, fnt(11), IVORY, 1.2)
        draw.text((x + 24, status_y + 61), detail, font=fnt(13, "rounded"), fill=MUTED)
        state = status if local > 3.7 else "REQUESTING"
        state_color = color if local > 3.7 else BLUE
        draw.text((x + 414, status_y + 27), state, font=fnt(10, "rounded"), fill=state_color, anchor="ra")
    draw.text((74, 697), "Automatic polling", font=fnt(16, "rounded"), fill=IVORY)
    draw.multiline_text(
        (74, 733),
        "Runs quietly in the background.\nManual refresh is always one click away.",
        font=fnt(13, "rounded"),
        fill=MUTED,
        spacing=8,
    )
    return layer


def native_scene(t: float) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    top_meta(draw, "04", "Native by design")
    section_label(draw, "04", "Native by design", 74, 142)
    draw.text((74, 190), "Small software.", font=fnt(55, "serif"), fill=IVORY)
    draw.text((74, 252), "A very short path to trust.", font=fnt(55, "serif"), fill=IVORY_2)

    cards = [
        ("01", "Native macOS", "SwiftUI + AppKit.\nNo Electron runtime.", BLUE),
        ("02", "Private by default", "Credentials stay local.\nNo analytics backend.", CODEX),
        ("03", "Resilient values", "429-aware backoff.\nLast success stays visible.", CLAUDE),
    ]
    card_w = 400
    for index, (number, title, body, accent) in enumerate(cards):
        x = 74 + index * 431
        floating_card(draw, (x, 352, x + card_w, 558), title, body, accent, number)

    rounded(draw, (74, 616, 1366, 779), 24, (7, 9, 12), (255, 255, 255, 30))
    draw.ellipse((101, 642, 111, 652), fill=(255, 95, 86))
    draw.ellipse((119, 642, 129, 652), fill=(255, 189, 46))
    draw.ellipse((137, 642, 147, 652), fill=(39, 201, 63))
    draw.text((101, 685), "$", font=fnt(15, "rounded"), fill=CODEX)
    draw.text((130, 684), CLONE, font=fnt(15, "rounded"), fill=IVORY)
    draw.text((101, 726), "$", font=fnt(15, "rounded"), fill=CODEX)
    draw.text((130, 725), "cd NotchUsage && ./install.sh", font=fnt(15, "rounded"), fill=IVORY)
    draw.text((1366, 815), "Clone. Install. Launch.", font=fnt(11, "rounded"), fill=MUTED, anchor="ra")
    return layer


def outro(t: float) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    brand(draw)
    tracking(draw, (1174, 58), "OPEN SOURCE  /  MIT", fnt(11), MUTED, 1.6)
    line(draw, (64, 98, 1376, 98), HAIRLINE)

    draw.multiline_text(
        (76, 176),
        "Keep the limits.\nLose the dashboard.",
        font=fnt(74, "serif"),
        fill=IVORY,
        spacing=4,
    )
    draw.multiline_text(
        (82, 378),
        "A focused macOS utility for Claude and Codex.",
        font=fnt(19, "rounded"),
        fill=IVORY_2,
    )
    device(draw, (760, 173, 1370, 599), claude_5h=82, claude_week=64, codex=73)

    rounded(draw, (76, 522, 693, 594), 20, IVORY)
    draw.text((104, 545), REPO, font=fnt(17, "rounded"), fill=NIGHT)
    draw.text((662, 545), "↗", font=fnt(19, "rounded"), fill=RUST, anchor="ra")

    line(draw, (76, 704, 1370, 704), HAIRLINE)
    label_pill(draw, 76, 750, "Claude + Codex", RUST, 174)
    label_pill(draw, 266, 750, "Launch at login", BLUE, 178)
    label_pill(draw, 460, 750, "No telemetry", CODEX, 150)
    draw.text((1370, 757), "Made for macOS", font=fnt(13, "rounded"), fill=MUTED, anchor="ra")
    return layer


def render(index: int) -> Image.Image:
    t = index / FPS
    frame = BACKGROUND.copy()
    scenes = [
        (0.0, 5.0, intro),
        (4.2, 9.1, quiet),
        (8.3, 14.7, context),
        (13.9, 20.4, refresh_scene),
        (19.6, 26.1, native_scene),
        (25.3, 30.0, outro),
    ]
    for start, end, renderer in scenes:
        opacity = fade(t, start, end)
        if opacity > 0:
            alpha_composite(frame, renderer(t), opacity)
    return frame.convert("RGB")


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "17",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(OUT),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    try:
        for index in range(FPS * DURATION):
            process.stdin.write(render(index).tobytes())
            if index % FPS == 0:
                print(f"Rendering {index // FPS:02d}/{DURATION}s", flush=True)
    finally:
        process.stdin.close()
    return process.wait()


if __name__ == "__main__":
    sys.exit(main())
