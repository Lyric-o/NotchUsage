#!/usr/bin/env python3
"""Create and apply the NotchUsage demo cover."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


WIDTH = 1440
HEIGHT = 900
FPS = 24

SERIF_FONT = Path("/System/Library/Fonts/NewYork.ttf")
SANS_FONT = Path("/System/Library/Fonts/SFNS.ttf")
MONO_FONT = Path("/System/Library/Fonts/SFNSMono.ttf")

IVORY = "#F3F0E8"
MUTED = "#A8ADB3"
ACCENT = "#D65E43"
GREEN = "#47C79B"
BLUE = "#6E92FF"
INK = "#070A0D"


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def fit_background(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    scale = max(WIDTH / image.width, HEIGHT / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - WIDTH) // 2
    top = (resized.height - HEIGHT) // 2
    return resized.crop((left, top, left + WIDTH, top + HEIGHT))


def add_shadowed_panel(
    canvas: Image.Image,
    bounds: tuple[int, int, int, int],
    radius: int,
    fill: str,
    outline: str,
    shadow_blur: int = 28,
    shadow_offset: tuple[int, int] = (0, 16),
) -> None:
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    x0, y0, x1, y1 = bounds
    dx, dy = shadow_offset
    shadow_draw.rounded_rectangle(
        (x0 + dx, y0 + dy, x1 + dx, y1 + dy),
        radius=radius,
        fill=(0, 0, 0, 165),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))
    canvas.alpha_composite(shadow)
    ImageDraw.Draw(canvas).rounded_rectangle(
        bounds,
        radius=radius,
        fill=fill,
        outline=outline,
        width=2,
    )


def draw_progress(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    progress: float,
    color: str,
) -> None:
    draw.rounded_rectangle(
        (x, y, x + width, y + 7),
        radius=4,
        fill="#292F35",
    )
    draw.rounded_rectangle(
        (x, y, x + round(width * progress), y + 7),
        radius=4,
        fill=color,
    )


def create_cover(background: Path, output: Path) -> None:
    canvas = fit_background(background).convert("RGBA")

    # A subtle left-side veil keeps the headline readable at thumbnail size.
    veil = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    veil_draw = ImageDraw.Draw(veil)
    for x in range(0, 760, 4):
        alpha = round(105 * (1 - x / 760) ** 1.6)
        veil_draw.rectangle((x, 0, x + 4, HEIGHT), fill=(0, 0, 0, alpha))
    canvas.alpha_composite(veil)
    draw = ImageDraw.Draw(canvas)

    # Brand.
    draw.rounded_rectangle((76, 58, 104, 84), radius=9, fill=ACCENT)
    draw.rounded_rectangle((84, 65, 99, 77), radius=5, fill=INK)
    draw.text((118, 58), "NotchUsage", font=font(SANS_FONT, 27), fill=IVORY)
    star_x, star_y = 282, 71
    draw.polygon(
        [
            (star_x, star_y - 10),
            (star_x + 3, star_y - 3),
            (star_x + 10, star_y),
            (star_x + 3, star_y + 3),
            (star_x, star_y + 10),
            (star_x - 3, star_y + 3),
            (star_x - 10, star_y),
            (star_x - 3, star_y - 3),
        ],
        fill=ACCENT,
    )

    # Editorial headline and compact supporting copy.
    draw.rounded_rectangle(
        (76, 146, 270, 179),
        radius=16,
        fill=(214, 94, 67, 25),
        outline=(214, 94, 67, 105),
        width=1,
    )
    draw.ellipse((92, 159, 98, 165), fill=ACCENT)
    draw.text(
        (108, 153),
        "LIVE USAGE · macOS",
        font=font(MONO_FONT, 13),
        fill="#DCA18F",
    )

    headline_font = font(SERIF_FONT, 68)
    plus_font = font(SANS_FONT, 48)
    draw.text((72, 211), "Claude", font=headline_font, fill=IVORY)
    claude_width = draw.textlength("Claude", font=headline_font)
    plus_x = 72 + claude_width + 18
    draw.text((plus_x, 228), "+", font=plus_font, fill=ACCENT)
    plus_width = draw.textlength("+", font=plus_font)
    draw.text(
        (plus_x + plus_width + 18, 211),
        "Codex",
        font=headline_font,
        fill=IVORY,
    )
    draw.text((72, 286), "at a glance.", font=font(SERIF_FONT, 82), fill=IVORY)
    draw.text(
        (78, 402),
        "Your remaining usage, reset times,",
        font=font(SANS_FONT, 25),
        fill="#C7C9C8",
    )
    draw.text(
        (78, 437),
        "and refresh control—right in the notch.",
        font=font(SANS_FONT, 25),
        fill="#C7C9C8",
    )

    badges = [
        ("CLAUDE + CODEX", ACCENT, 170),
        ("NATIVE SWIFTUI", BLUE, 170),
        ("OPEN SOURCE", GREEN, 148),
    ]
    badge_x = 78
    for label, color, badge_width in badges:
        draw.rounded_rectangle(
            (badge_x, 501, badge_x + badge_width, 538),
            radius=18,
            fill="#11161B",
            outline=color,
            width=1,
        )
        draw.ellipse((badge_x + 14, 516, badge_x + 20, 522), fill=color)
        draw.text(
            (badge_x + 28, 510),
            label,
            font=font(MONO_FONT, 12),
            fill="#CDD0D2",
        )
        badge_x += badge_width + 12

    # Product mockup.
    device = (704, 142, 1378, 705)
    add_shadowed_panel(
        canvas,
        device,
        radius=28,
        fill="#141A21",
        outline="#454D56",
        shadow_blur=32,
        shadow_offset=(0, 20),
    )
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((718, 156, 1364, 691), radius=20, fill="#1B222B")
    draw.ellipse((738, 174, 747, 183), fill="#65707A")
    draw.ellipse((754, 174, 763, 183), fill="#4D5760")
    draw.ellipse((770, 174, 779, 183), fill="#3C454D")

    # Abstract macOS wallpaper inside the mock display.
    wallpaper = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    wallpaper_draw = ImageDraw.Draw(wallpaper)
    wallpaper_draw.ellipse((1120, 104, 1510, 500), fill=(165, 65, 49, 90))
    wallpaper_draw.ellipse((656, 445, 1090, 850), fill=(25, 111, 91, 55))
    wallpaper = wallpaper.filter(ImageFilter.GaussianBlur(20))
    canvas.alpha_composite(wallpaper)
    draw = ImageDraw.Draw(canvas)

    # The actual compact notch surface.
    notch = (782, 156, 1305, 226)
    add_shadowed_panel(
        canvas,
        notch,
        radius=22,
        fill="#020304",
        outline="#080A0B",
        shadow_blur=12,
        shadow_offset=(0, 7),
    )
    draw = ImageDraw.Draw(canvas)
    draw.line((1044, 171, 1044, 211), fill="#202429", width=1)
    draw.text((810, 169), "Claude", font=font(SANS_FONT, 17), fill="#E7E8E6")
    draw.text((1070, 169), "Codex", font=font(SANS_FONT, 17), fill="#E7E8E6")
    draw.text((810, 198), "5h 82%   W 64%", font=font(MONO_FONT, 15), fill="#E77859")
    draw.text((1239, 198), "73%", font=font(MONO_FONT, 15), fill=GREEN)

    # Hover detail card.
    detail = (795, 290, 1289, 558)
    add_shadowed_panel(
        canvas,
        detail,
        radius=22,
        fill="#0D1217",
        outline="#323A42",
        shadow_blur=18,
        shadow_offset=(0, 12),
    )
    draw = ImageDraw.Draw(canvas)
    draw.text((826, 318), "Usage details", font=font(SANS_FONT, 21), fill=IVORY)
    draw.rounded_rectangle((1195, 316, 1258, 346), radius=15, fill="#17201E")
    draw.ellipse((1208, 328, 1214, 334), fill=GREEN)
    draw.text((1222, 322), "LIVE", font=font(MONO_FONT, 11), fill="#89DABB")

    rows = [
        ("Claude · 5h", "82%", "resets in 2h 18m", 0.82, ACCENT),
        ("Claude · W", "64%", "resets Monday", 0.64, "#D78D62"),
        ("Codex", "73%", "resets in 3h 42m", 0.73, GREEN),
    ]
    row_y = 374
    for label, value, reset, progress, color in rows:
        draw.text((826, row_y), label, font=font(SANS_FONT, 16), fill="#E3E5E4")
        value_width = draw.textlength(value, font=font(MONO_FONT, 15))
        draw.text(
            (1257 - value_width, row_y + 1),
            value,
            font=font(MONO_FONT, 15),
            fill=color,
        )
        draw_progress(draw, 826, row_y + 30, 272, progress, color)
        draw.text((1114, row_y + 24), reset, font=font(SANS_FONT, 13), fill="#8F979E")
        row_y += 60

    draw.text(
        (824, 610),
        "Hover for reset times",
        font=font(SANS_FONT, 15),
        fill="#A9AFB4",
    )
    draw.ellipse((1012, 620, 1017, 625), fill="#4A535B")
    draw.text(
        (1033, 610),
        "Click to refresh",
        font=font(SANS_FONT, 15),
        fill="#A9AFB4",
    )

    # Footer line gives the composition a clean editorial baseline.
    draw.line((76, 782, 1364, 782), fill=(255, 255, 255, 28), width=1)
    draw.text(
        (76, 812),
        "A tiny native macOS utility by Lyric-o",
        font=font(SANS_FONT, 16),
        fill="#8D949A",
    )
    footer = "github.com/Lyric-o/NotchUsage"
    footer_width = draw.textlength(footer, font=font(MONO_FONT, 14))
    draw.text(
        (1364 - footer_width, 812),
        footer,
        font=font(MONO_FONT, 14),
        fill="#B7BCBF",
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, quality=96)


def apply_cover(video: Path, cover: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="notchusage-cover-") as temporary:
        rendered = Path(temporary) / output.name
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-loop",
                "1",
                "-framerate",
                str(FPS),
                "-i",
                str(cover),
                "-i",
                str(video),
                "-filter_complex",
                "[0:v]trim=duration=1.20,setpts=PTS-STARTPTS,format=rgba,"
                "fade=t=out:st=0.82:d=0.38:alpha=1[cover];"
                "[1:v][cover]overlay=eof_action=pass:shortest=0[v]",
                "-map",
                "[v]",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(FPS),
                "-c:a",
                "copy",
                "-t",
                "30",
                "-movflags",
                "+faststart",
                str(rendered),
            ],
            check=True,
        )
        rendered.replace(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    folder = Path(__file__).resolve().parent
    parser.add_argument(
        "--background",
        type=Path,
        default=folder / "assets" / "cover-background.png",
    )
    parser.add_argument(
        "--cover",
        type=Path,
        default=folder / "NotchUsage-cover.png",
    )
    parser.add_argument("--video", type=Path)
    parser.add_argument("--output-video", type=Path)
    args = parser.parse_args()

    create_cover(args.background, args.cover)
    if args.video or args.output_video:
        if not args.video or not args.output_video:
            parser.error("--video and --output-video must be provided together")
        apply_cover(args.video, args.cover, args.output_video)

    print(args.cover)
    if args.output_video:
        print(args.output_video)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
