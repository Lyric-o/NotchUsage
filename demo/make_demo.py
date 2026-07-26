#!/usr/bin/env python3
"""Render an editorial, ARIS-inspired product film for NotchUsage."""

from __future__ import annotations

import math
import random
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H = 1440, 900
FPS = 24
DURATION = 31
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo" / "NotchUsage-demo.mp4"

FONT_SERIF = "/System/Library/Fonts/Supplemental/Georgia.ttf"
FONT_SERIF_BOLD = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
FONT_SONG = "/System/Library/Fonts/Supplemental/Songti.ttc"
FONT_SANS = "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/3419f2a427639ad8c8e139149a287865a90fa17e.asset/AssetData/PingFang.ttc"

PAPER = (244, 241, 234)
PAPER_2 = (237, 232, 222)
INK = (28, 26, 23)
INK_2 = (49, 46, 41)
MUTED = (113, 106, 95)
HAIRLINE = (205, 198, 186)
RUST = (154, 59, 40)
SLATE = (101, 115, 143)
CLAUDE = (203, 99, 61)
CODEX = (44, 139, 111)
WHITE = (250, 248, 243)


@lru_cache(maxsize=None)
def fnt(size: int, family: str = "sans", bold: bool = False):
    if family == "serif":
        return ImageFont.truetype(FONT_SERIF_BOLD if bold else FONT_SERIF, size)
    if family == "song":
        return ImageFont.truetype(FONT_SONG, size)
    return ImageFont.truetype(FONT_SANS, size)


def clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def smooth(v: float) -> float:
    v = clamp(v)
    return v * v * (3 - 2 * v)


def phase(t: float, a: float, b: float) -> float:
    return smooth((t - a) / (b - a))


def scene_alpha(t: float, start: float, end: float, fade: float = 0.7) -> float:
    return phase(t, start, start + fade) * (1 - phase(t, end - fade, end))


def composite(base: Image.Image, layer: Image.Image, opacity: float = 1.0):
    if opacity <= 0:
        return
    if opacity < 1:
        alpha = layer.getchannel("A").point(lambda x: int(x * opacity))
        layer.putalpha(alpha)
    base.alpha_composite(layer)


def line(draw, xy, fill=HAIRLINE, width=1):
    draw.line(xy, fill=fill, width=width)


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def tracking(draw, xy, text, font, fill, spacing=3):
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        x += draw.textlength(char, font=font) + spacing


def paper_background() -> Image.Image:
    image = Image.new("RGBA", (W, H), PAPER + (255,))
    draw = ImageDraw.Draw(image, "RGBA")
    rng = random.Random(7)
    for _ in range(1800):
        x, y = rng.randrange(W), rng.randrange(H)
        shade = rng.choice([(90, 75, 56, 8), (255, 255, 255, 12)])
        draw.point((x, y), fill=shade)
    for x in range(0, W, 120):
        line(draw, (x, 0, x, H), (80, 70, 55, 5))
    return image


PAPER_BG = paper_background()
INK_BG = Image.new("RGBA", (W, H), INK + (255,))


def editorial_chrome(draw: ImageDraw.ImageDraw, dark=False, active="01"):
    fg = WHITE if dark else INK
    muted = (180, 174, 164) if dark else MUTED
    hair = (255, 255, 255, 25) if dark else HAIRLINE
    line(draw, (350, 56, 350, 842), hair)
    tracking(draw, (52, 59), "CONTENTS", fnt(13, "serif", True), muted, 2)
    items = [
        ("01", "The Quiet Default"),
        ("02", "Hover for Context"),
        ("03", "Refresh, Deliberately"),
        ("04", "Native by Design"),
    ]
    y = 108
    for num, label in items:
        color = RUST if num == active else muted
        draw.text((52, y), num, font=fnt(13, "serif", True), fill=color)
        draw.text((91, y), label, font=fnt(13, "serif"), fill=fg if num == active else muted)
        y += 39
    line(draw, (52, 788, 310, 788), hair)
    draw.text((52, 806), "LYRIC98  /  MIT  /  2026", font=fnt(10, "sans"), fill=muted)


def eyebrow(draw, text, x=407, y=61, dark=False):
    tracking(draw, (x, y), text.upper(), fnt(13, "serif", True), (201, 106, 78) if dark else RUST, 2)


def page_rule(draw, y=190, dark=False, progress=1.0):
    color = (135, 145, 165) if dark else SLATE
    line(draw, (407, y, 407 + int(954 * progress), y), color, 4)


def progress_bar(draw, box, percent, color, dark=True):
    x1, y1, x2, y2 = box
    bg = (255, 255, 255, 34) if dark else (20, 20, 20, 25)
    rounded(draw, box, (y2 - y1) // 2, bg)
    rounded(draw, (x1, y1, x1 + (x2 - x1) * percent / 100, y2), (y2 - y1) // 2, color)


def widget(draw, y: int, hover=False, refreshing=False, scale=1.0):
    center = 890
    width = int(780 * scale)
    h = int(64 * scale)
    x1, x2 = center - width // 2, center + width // 2
    notch = int(210 * scale)
    rounded(draw, (x1, y, x2, y + h), int(18 * scale), (6, 7, 8), (255, 255, 255, 24), 1)
    draw.rectangle((center - notch // 2, y, center + notch // 2, y + int(38 * scale)), fill=(0, 0, 0))
    rounded(draw, (center - notch // 2, y, center + notch // 2, y + int(47 * scale)), int(15 * scale), (0, 0, 0))
    draw.rectangle((center - notch // 2, y, center + notch // 2, y + int(20 * scale)), fill=(0, 0, 0))

    if refreshing:
        r = int(9 * scale)
        cx, cy = center, y + int(43 * scale)
        draw.arc((cx-r, cy-r, cx+r, cy+r), 30, 285, fill=(230, 230, 225), width=max(1, int(2*scale)))
    else:
        rounded(draw, (center - int(22*scale), y + int(45*scale), center + int(22*scale), y + int(49*scale)), int(2*scale), (255, 255, 255, 26))

    small = fnt(int(12 * scale), "sans")
    small_b = fnt(int(13 * scale), "sans", True)
    if not hover:
        draw.text((x1 + int(23*scale), y + int(12*scale)), "Claude", font=small_b, fill=(221, 218, 212))
        draw.text((x1 + int(23*scale), y + int(35*scale)), "5h 82%   W 64%", font=small, fill=CLAUDE)
        right = center + notch // 2 + int(26*scale)
        draw.text((right, y + int(23*scale)), "Codex", font=small_b, fill=(221, 218, 212))
        draw.text((x2 - int(24*scale), y + int(23*scale)), "62%", font=small_b, fill=CODEX, anchor="ra")
    else:
        lx = x1 + int(19*scale)
        draw.text((lx, y + int(10*scale)), "5h", font=small, fill=CLAUDE)
        progress_bar(draw, (lx + int(29*scale), y + int(17*scale), lx + int(150*scale), y + int(23*scale)), 82, CLAUDE)
        draw.text((lx + int(192*scale), y + int(8*scale)), "82%", font=small_b, fill=WHITE, anchor="ra")
        draw.text((lx, y + int(37*scale)), "W", font=small, fill=CLAUDE)
        progress_bar(draw, (lx + int(29*scale), y + int(44*scale), lx + int(150*scale), y + int(50*scale)), 64, CLAUDE)
        draw.text((lx + int(192*scale), y + int(35*scale)), "64%", font=small_b, fill=WHITE, anchor="ra")
        rx = center + notch // 2 + int(24*scale)
        draw.text((rx, y + int(22*scale)), "Codex", font=small_b, fill=(221, 218, 212))
        progress_bar(draw, (rx + int(61*scale), y + int(29*scale), rx + int(170*scale), y + int(35*scale)), 62, CODEX)
        draw.text((x2 - int(22*scale), y + int(20*scale)), "62%", font=small_b, fill=WHITE, anchor="ra")
    return (x1, y, x2, y+h)


def details(draw, y: int, amount: float, dark_page=False):
    if amount <= 0:
        return
    center, width, full_h = 890, 850, 206
    x1 = center - width // 2
    h = int(full_h * amount)
    fill = (247, 244, 237) if dark_page else (36, 34, 31)
    fg = INK if dark_page else WHITE
    muted = MUTED if dark_page else (175, 170, 162)
    rounded(draw, (x1, y, x1+width, y+h), 22, fill, (255, 255, 255, 22) if not dark_page else HAIRLINE, 1)
    if amount < 0.62:
        return
    a = int(255 * phase(amount, 0.62, 1))
    line(draw, (center, y+27, center, y+full_h-27), (140, 130, 116, 45) if dark_page else (255, 255, 255, 28))
    draw.text((x1+34, y+28), "CLAUDE", font=fnt(12, "serif", True), fill=(*RUST, a))
    draw.text((center+34, y+28), "CODEX", font=fnt(12, "serif", True), fill=(*CODEX, a))
    draw.text((x1+34, y+64), "5-hour window", font=fnt(18, "serif", True), fill=(*fg, a))
    draw.text((center-35, y+65), "82%", font=fnt(18, "serif", True), fill=(*CLAUDE, a), anchor="ra")
    draw.text((x1+34, y+95), "Resets today at 18:40", font=fnt(13, "sans"), fill=(*muted, a))
    line(draw, (x1+34, y+125, center-35, y+125), (120, 110, 95, 38) if dark_page else (255, 255, 255, 22))
    draw.text((x1+34, y+143), "Weekly", font=fnt(14, "serif", True), fill=(*fg, a))
    draw.text((center-35, y+143), "64%  ·  Aug 1, 16:13", font=fnt(13, "sans"), fill=(*muted, a), anchor="ra")
    draw.text((center+34, y+64), "Weekly allowance", font=fnt(18, "serif", True), fill=(*fg, a))
    draw.text((x1+width-34, y+65), "62%", font=fnt(18, "serif", True), fill=(*CODEX, a), anchor="ra")
    draw.text((center+34, y+95), "Resets Aug 1 at 16:13", font=fnt(13, "sans"), fill=(*muted, a))
    line(draw, (center+34, y+125, x1+width-34, y+125), (120, 110, 95, 38) if dark_page else (255, 255, 255, 22))
    draw.text((center+34, y+143), "Authoritative server value", font=fnt(13, "sans"), fill=(*CODEX, a))


def cursor(draw, x, y, click=0, dark=False):
    if click > 0:
        r = 18 + 35 * click
        draw.ellipse((x-r, y-r, x+r, y+r), outline=(*RUST, int(180*(1-click))), width=2)
    fill = INK if not dark else WHITE
    pts = [(x, y), (x+2, y+28), (x+10, y+20), (x+18, y+35), (x+24, y+31), (x+16, y+17), (x+28, y+15)]
    draw.polygon(pts, fill=fill, outline=PAPER if not dark else INK)


def cover(t: float) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    editorial_chrome(d, active="01")
    eyebrow(d, "NOTCHUSAGE · 2026 INTRODUCTION")
    reveal = phase(t, 0.35, 1.2)
    y = 124 + int((1-reveal)*18)
    d.multiline_text((407, y), "Your AI usage,\nwhere you already look.", font=fnt(62, "serif", True), fill=INK, spacing=5)
    d.text((409, 282), "Claude 与 Codex 的实时额度，安静地留在刘海两侧。", font=fnt(20, "song"), fill=INK_2)
    d.text((409, 328), "By Lyric98  ·  Native macOS utility", font=fnt(14, "serif", True), fill=INK)
    line(d, (407, 376, 1360, 376), HAIRLINE)
    d.text((407, 401), "Source:", font=fnt(12, "serif", True), fill=INK)
    rounded(d, (467, 395, 632, 423), 4, PAPER_2)
    d.text((478, 401), "github.com/Lyric98", font=fnt(11, "sans"), fill=RUST)
    d.text((661, 401), "Build:", font=fnt(12, "serif", True), fill=INK)
    rounded(d, (708, 395, 786, 423), 4, PAPER_2)
    d.text((721, 401), "SwiftUI", font=fnt(11, "sans"), fill=RUST)
    page_rule(d, 454, progress=phase(t, 0.8, 1.6))
    d.text((407, 510), "TL;DR", font=fnt(34, "serif", True), fill=INK)
    line(d, (407, 559, 1360, 559), HAIRLINE)
    d.text((407, 586), "A quiet status surface for two tools you use every day.", font=fnt(23, "serif"), fill=INK)
    d.text((407, 630), "No dashboard. No context switching. No telemetry.", font=fnt(17, "sans"), fill=MUTED)
    widget(d, 705, hover=False, scale=0.82)
    return layer


def quiet_default(t: float) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    editorial_chrome(d, active="01")
    eyebrow(d, "01 · THE QUIET DEFAULT")
    d.text((407, 110), "Always visible. Never loud.", font=fnt(52, "serif", True), fill=INK)
    d.text((409, 176), "平时只保留最重要的数字。", font=fnt(19, "song"), fill=INK_2)
    page_rule(d, 232, progress=phase(t, 4.1, 5.0))
    widget(d, 335, hover=False, scale=1.05)
    d.text((407, 493), "ONE GLANCE", font=fnt(12, "serif", True), fill=RUST)
    d.text((407, 531), "5h", font=fnt(26, "serif", True), fill=INK)
    d.text((407, 570), "Short window", font=fnt(13, "sans"), fill=MUTED)
    line(d, (570, 518, 570, 600), HAIRLINE)
    d.text((617, 531), "W", font=fnt(26, "serif", True), fill=INK)
    d.text((617, 570), "Claude weekly", font=fnt(13, "sans"), fill=MUTED)
    line(d, (812, 518, 812, 600), HAIRLINE)
    d.text((860, 531), "Codex", font=fnt(26, "serif", True), fill=INK)
    d.text((860, 570), "Server allowance", font=fnt(13, "sans"), fill=MUTED)
    line(d, (407, 646, 1360, 646), HAIRLINE)
    d.text((407, 678), "The interface occupies 34 pt when closed — nothing more.", font=fnt(16, "serif"), fill=INK_2)
    return layer


def hover_context(t: float) -> Image.Image:
    layer = INK_BG.copy()
    d = ImageDraw.Draw(layer, "RGBA")
    editorial_chrome(d, dark=True, active="02")
    eyebrow(d, "02 · HOVER FOR CONTEXT", dark=True)
    d.text((407, 110), "Details, only when invited.", font=fnt(52, "serif", True), fill=WHITE)
    d.text((409, 176), "鼠标靠近，完整周期与重置时间自然展开。", font=fnt(19, "song"), fill=(214, 207, 196))
    page_rule(d, 232, dark=True, progress=phase(t, 9.0, 9.8))
    widget(d, 315, hover=True, scale=1.05)
    expand = phase(t, 10.0, 11.0)
    details(d, 382, expand, dark_page=True)
    # Minimal editorial annotations.
    if expand > 0.8:
        line(d, (407, 650, 610, 650), (255, 255, 255, 35))
        d.text((407, 670), "RESET TIMES", font=fnt(11, "serif", True), fill=(201, 106, 78))
        d.text((407, 700), "Shown in your local time zone.", font=fnt(15, "serif"), fill=(205, 198, 187))
        line(d, (916, 650, 1118, 650), (255, 255, 255, 35))
        d.text((916, 670), "REAL VALUES", font=fnt(11, "serif", True), fill=CODEX)
        d.text((916, 700), "Last success remains during rate limits.", font=fnt(15, "serif"), fill=(205, 198, 187))
    move = phase(t, 9.0, 10.0)
    cursor(d, 1260*(1-move)+1020*move, 710*(1-move)+344*move, dark=True)
    return layer


def refresh_scene(t: float) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    editorial_chrome(d, active="03")
    eyebrow(d, "03 · REFRESH, DELIBERATELY")
    d.text((407, 110), "One click. Two sources.", font=fnt(52, "serif", True), fill=INK)
    d.text((409, 176), "需要确认时，主动向两边服务端请求最新额度。", font=fnt(19, "song"), fill=INK_2)
    page_rule(d, 232, progress=phase(t, 16.5, 17.3))
    local_t = t - 16.5
    click = math.sin(clamp((local_t-2.1)/0.8) * math.pi) if 2.1 <= local_t <= 2.9 else 0
    refreshing = 2.5 <= local_t <= 4.2
    widget(d, 326, hover=False, refreshing=refreshing, scale=1.05)
    cursor(d, 920, 355, click=click)
    # Source ledger.
    d.text((407, 507), "SOURCE LEDGER", font=fnt(12, "serif", True), fill=RUST)
    line(d, (407, 542, 1360, 542), HAIRLINE)
    rows = [
        ("ANTHROPIC", "OAuth usage endpoint", "5h + weekly", CLAUDE),
        ("OPENAI", "Authoritative usage endpoint", "Codex weekly", CODEX),
    ]
    yy = 575
    for provider, endpoint, scope, color in rows:
        d.ellipse((407, yy+6, 417, yy+16), fill=color)
        d.text((438, yy), provider, font=fnt(13, "serif", True), fill=INK)
        d.text((635, yy), endpoint, font=fnt(14, "serif"), fill=INK_2)
        d.text((1130, yy), scope, font=fnt(13, "sans"), fill=MUTED)
        d.text((1325, yy), "SYNCED" if local_t > 4.2 else "QUERY", font=fnt(11, "sans"), fill=color, anchor="ra")
        line(d, (407, yy+39, 1360, yy+39), HAIRLINE)
        yy += 66
    d.text((407, 741), "If an endpoint rate-limits, NotchUsage keeps the last successful real value.", font=fnt(15, "serif"), fill=MUTED)
    return layer


def native_scene(t: float) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    editorial_chrome(d, active="04")
    eyebrow(d, "04 · NATIVE BY DESIGN")
    d.text((407, 110), "Small software, honestly made.", font=fnt(52, "serif", True), fill=INK)
    d.text((409, 176), "没有 Electron，没有遥测，也没有第三方后台。", font=fnt(19, "song"), fill=INK_2)
    page_rule(d, 232, progress=phase(t, 22.0, 22.8))
    cols = [
        ("01", "SwiftUI + AppKit", "Native panel, native menu, native login item."),
        ("02", "Direct endpoints", "Credentials stay local and in memory."),
        ("03", "Open source", "MIT licensed. Read every line."),
    ]
    x = 407
    for num, title, body in cols:
        d.text((x, 298), num, font=fnt(12, "serif", True), fill=RUST)
        line(d, (x, 329, x+260, 329), HAIRLINE)
        d.text((x, 362), title, font=fnt(21, "serif", True), fill=INK)
        d.multiline_text((x, 405), body, font=fnt(14, "serif"), fill=MUTED, spacing=8)
        x += 318
    rounded(d, (407, 548, 1360, 666), 4, INK)
    d.text((438, 571), "$", font=fnt(16, "sans", True), fill=CODEX)
    d.text((465, 571), "git clone https://github.com/Lyric98/NotchUsage.git", font=fnt(16, "sans"), fill=WHITE)
    d.text((438, 612), "$", font=fnt(16, "sans", True), fill=CODEX)
    d.text((465, 612), "cd NotchUsage && ./install.sh", font=fnt(16, "sans"), fill=WHITE)
    d.text((407, 718), "Build once. Launch at login. Forget the dashboard.", font=fnt(22, "serif", True), fill=INK)
    return layer


def outro(t: float) -> Image.Image:
    layer = INK_BG.copy()
    d = ImageDraw.Draw(layer, "RGBA")
    tracking(d, (74, 74), "NOTCHUSAGE · OPEN SOURCE", fnt(13, "serif", True), (201, 106, 78), 2)
    line(d, (74, 118, 1366, 118), (255, 255, 255, 28))
    d.multiline_text((74, 210), "Your limits.\nIn sight, not in the way.", font=fnt(68, "serif", True), fill=WHITE, spacing=7)
    d.text((78, 408), "用量在视线里，工具在工作流外。", font=fnt(23, "song"), fill=(205, 198, 187))
    widget(d, 510, hover=False, scale=1.0)
    line(d, (74, 720, 1366, 720), (255, 255, 255, 28))
    d.text((74, 754), "github.com/Lyric98/NotchUsage", font=fnt(17, "serif", True), fill=WHITE)
    d.text((74, 793), "Native macOS · MIT License · No telemetry", font=fnt(13, "sans"), fill=(170, 164, 154))
    rounded(d, (1112, 758, 1366, 812), 4, (247, 244, 237))
    d.text((1239, 784), "VIEW ON GITHUB  ↗", font=fnt(12, "serif", True), fill=INK, anchor="mm")
    return layer


def render(index: int) -> Image.Image:
    t = index / FPS
    frame = PAPER_BG.copy()
    scenes = [
        (0.0, 4.8, cover),
        (3.8, 10.0, quiet_default),
        (9.0, 17.5, hover_context),
        (16.5, 23.0, refresh_scene),
        (22.0, 27.8, native_scene),
        (26.8, 31.0, outro),
    ]
    for start, end, renderer in scenes:
        opacity = scene_alpha(t, start, end)
        if opacity > 0:
            composite(frame, renderer(t), opacity)
    return frame.convert("RGB")


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium",
        "-crf", "17", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(OUT),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for i in range(FPS * DURATION):
            proc.stdin.write(render(i).tobytes())
            if i % FPS == 0:
                print(f"Rendering {i // FPS:02d}/{DURATION}s", flush=True)
    finally:
        proc.stdin.close()
    return proc.wait()


if __name__ == "__main__":
    sys.exit(main())
