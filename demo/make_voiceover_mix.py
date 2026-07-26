#!/usr/bin/env python3
"""Polish a voice-over and mix it with the 30-second NotchUsage demo."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np


SAMPLE_RATE = 48_000
TARGET_SECONDS = 30.0

# Extra room is inserted only at pauses already present in the supplied take.
# The positions come from silence detection on the supplied voice-over take.
PAUSES = [
    (5.686146, 0.40),
    (11.511417, 0.65),
    (14.199271, 0.40),
    (16.249958, 0.20),
    (17.961146, 0.20),
    (20.011250, 0.65),
    (21.698438, 0.50),
]


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def clean_voice(source: Path, output: Path) -> None:
    filters = ",".join(
        [
            "highpass=f=70",
            "lowpass=f=12000",
            "afftdn=nr=8:nf=-46:tn=1:ad=0.65:gs=5",
            "equalizer=f=180:t=q:w=1.1:g=1.5",
            "equalizer=f=3400:t=q:w=1.2:g=-1.2",
            "deesser=i=0.12:m=0.35:f=0.45",
            # A fast first stage rounds off emphatic syllables; the slower second
            # stage keeps the result conversational instead of sounding squashed.
            "acompressor=threshold=0.025:ratio=3.2:attack=8:release=140:makeup=2:knee=5",
            "acompressor=threshold=0.075:ratio=1.5:attack=38:release=300:makeup=1.15:knee=4",
            "agate=threshold=0.0075:ratio=2:range=0.08:attack=8:release=300:knee=3:detection=rms",
            "alimiter=limit=0.85",
            "loudnorm=I=-18:TP=-2.5:LRA=6",
        ]
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-af",
            filters,
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-c:a",
            "pcm_s24le",
            str(output),
        ]
    )


def add_natural_pauses(source: Path, output: Path) -> None:
    duration = probe_duration(source)
    cuts = [(position, extra) for position, extra in PAUSES if position < duration]
    labels: list[str] = []
    graph: list[str] = []
    start = 0.0
    index = 0

    for position, extra in cuts:
        segment = f"segment{index}"
        silence = f"silence{index}"
        graph.append(
            f"[0:a]atrim=start={start:.6f}:end={position:.6f},"
            f"asetpts=N/SR/TB[{segment}]"
        )
        graph.append(
            f"anullsrc=r={SAMPLE_RATE}:cl=mono:d={extra:.6f}[{silence}]"
        )
        labels.extend([f"[{segment}]", f"[{silence}]"])
        start = position
        index += 1

    segment = f"segment{index}"
    graph.append(
        f"[0:a]atrim=start={start:.6f}:end={duration:.6f},"
        f"asetpts=N/SR/TB[{segment}]"
    )
    labels.append(f"[{segment}]")
    graph.append(
        "".join(labels)
        + f"concat=n={len(labels)}:v=0:a=1,"
        + f"apad=whole_dur={TARGET_SECONDS},atrim=duration={TARGET_SECONDS}[voice]"
    )

    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-filter_complex",
            ";".join(graph),
            "-map",
            "[voice]",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-c:a",
            "pcm_s24le",
            str(output),
        ]
    )


def midi_frequency(note: float) -> float:
    return 440.0 * 2 ** ((note - 69.0) / 12.0)


def make_soft_music(output: Path) -> None:
    frames = int(SAMPLE_RATE * TARGET_SECONDS)
    timeline = np.arange(frames, dtype=np.float64) / SAMPLE_RATE
    stereo = np.zeros((frames, 2), dtype=np.float64)
    chord_seconds = 3.75
    chords = [
        (48, [60, 64, 67, 71]),  # Cmaj7
        (45, [57, 60, 64, 67]),  # Am7
        (41, [53, 57, 60, 64]),  # Fmaj7
        (43, [55, 59, 62, 69]),  # G6/9
        (48, [60, 64, 67, 71]),
        (45, [57, 60, 64, 67]),
        (41, [53, 57, 60, 64]),
        (48, [60, 64, 67, 74]),  # resolve gently to C for the outro
    ]

    for chord_index, (bass_note, notes) in enumerate(chords):
        start = chord_index * chord_seconds
        end = min(TARGET_SECONDS, start + chord_seconds)
        mask = (timeline >= start) & (timeline < end)
        local = timeline[mask] - start
        envelope = np.minimum(local / 0.55, 1.0) * np.minimum((end - timeline[mask]) / 0.8, 1.0)
        envelope = np.clip(envelope, 0.0, 1.0) ** 0.7

        left = np.zeros_like(local)
        right = np.zeros_like(local)
        for note_index, note in enumerate(notes):
            frequency = midi_frequency(note)
            weight = 0.020 / (1 + note_index * 0.15)
            left += weight * (
                np.sin(2 * np.pi * frequency * local)
                + 0.16 * np.sin(2 * np.pi * frequency * 2 * local)
            )
            right += weight * (
                np.sin(2 * np.pi * frequency * 1.0025 * local + 0.28)
                + 0.14 * np.sin(2 * np.pi * frequency * 2.005 * local + 0.45)
            )

        bass_frequency = midi_frequency(bass_note)
        bass = 0.024 * np.sin(2 * np.pi * bass_frequency * local)
        stereo[mask, 0] += (left + bass) * envelope
        stereo[mask, 1] += (right + bass) * envelope

    # A bright 124 BPM pulse gives the demo some movement without competing
    # with speech. The syncopated rests keep it playful rather than mechanical.
    beat = 60.0 / 124.0
    half_beat = beat / 2
    pluck_steps = [0, 2, 3, 4, 6, 7]
    pluck_index = 0
    for step, onset in enumerate(np.arange(0.35, TARGET_SECONDS - 0.6, half_beat)):
        if step % 8 not in pluck_steps:
            continue
        chord_index = min(int(onset // chord_seconds), len(chords) - 1)
        notes = chords[chord_index][1]
        note = notes[pluck_index % len(notes)] + 12
        frequency = midi_frequency(note)
        start_frame = int(onset * SAMPLE_RATE)
        length = min(int(0.55 * SAMPLE_RATE), frames - start_frame)
        local = np.arange(length, dtype=np.float64) / SAMPLE_RATE
        envelope = (1 - np.exp(-55 * local)) * np.exp(-8.2 * local)
        pluck = 0.063 * envelope * (
            np.sin(2 * np.pi * frequency * local)
            + 0.28 * np.sin(2 * np.pi * frequency * 2 * local)
            + 0.10 * np.sin(2 * np.pi * frequency * 3 * local)
        )
        pan = 0.28 + 0.44 * ((pluck_index % 4) / 3)
        stereo[start_frame : start_frame + length, 0] += pluck * np.sqrt(1 - pan)
        stereo[start_frame : start_frame + length, 1] += pluck * np.sqrt(pan)
        pluck_index += 1

    # Short bass pulses and brushed percussion make the rhythm audible on
    # laptop speakers while remaining gentle enough for a voice-over.
    rng = np.random.default_rng(98)
    for beat_index, onset in enumerate(np.arange(0.35, TARGET_SECONDS - 0.3, beat)):
        chord_index = min(int(onset // chord_seconds), len(chords) - 1)
        bass_frequency = midi_frequency(chords[chord_index][0])
        start_frame = int(onset * SAMPLE_RATE)

        bass_length = min(int(0.38 * SAMPLE_RATE), frames - start_frame)
        bass_time = np.arange(bass_length, dtype=np.float64) / SAMPLE_RATE
        bass_envelope = (1 - np.exp(-35 * bass_time)) * np.exp(-7.0 * bass_time)
        bass_pulse = (0.050 if beat_index % 4 == 0 else 0.034) * bass_envelope * (
            np.sin(2 * np.pi * bass_frequency * bass_time)
            + 0.18 * np.sin(2 * np.pi * bass_frequency * 2 * bass_time)
        )
        stereo[start_frame : start_frame + bass_length, :] += bass_pulse[:, None]

        kick_length = min(int(0.16 * SAMPLE_RATE), frames - start_frame)
        kick_time = np.arange(kick_length, dtype=np.float64) / SAMPLE_RATE
        kick_phase = 2 * np.pi * (82 * kick_time - 105 * kick_time**2)
        kick = 0.030 * np.exp(-22 * kick_time) * np.sin(kick_phase)
        stereo[start_frame : start_frame + kick_length, :] += kick[:, None]

        shaker_onset = onset + half_beat
        shaker_start = int(shaker_onset * SAMPLE_RATE)
        if shaker_start >= frames:
            continue
        shaker_length = min(int(0.10 * SAMPLE_RATE), frames - shaker_start)
        shaker_time = np.arange(shaker_length, dtype=np.float64) / SAMPLE_RATE
        noise = rng.standard_normal(shaker_length + 1)
        bright_noise = np.diff(noise)
        shaker = 0.009 * np.exp(-32 * shaker_time) * bright_noise
        pan = 0.38 if beat_index % 2 == 0 else 0.62
        stereo[shaker_start : shaker_start + shaker_length, 0] += shaker * np.sqrt(1 - pan)
        stereo[shaker_start : shaker_start + shaker_length, 1] += shaker * np.sqrt(pan)

        if beat_index % 4 in (1, 3):
            clap_length = min(int(0.14 * SAMPLE_RATE), frames - start_frame)
            clap_time = np.arange(clap_length, dtype=np.float64) / SAMPLE_RATE
            clap_noise = np.diff(rng.standard_normal(clap_length + 1))
            clap_envelope = np.exp(-25 * clap_time) * (
                0.75 + 0.25 * np.cos(2 * np.pi * 24 * clap_time)
            )
            clap = 0.008 * clap_envelope * clap_noise
            stereo[start_frame : start_frame + clap_length, 0] += clap * 0.68
            stereo[start_frame : start_frame + clap_length, 1] += clap * 0.74

    fade_in = np.clip(timeline / 1.2, 0.0, 1.0)
    fade_out = np.clip((TARGET_SECONDS - timeline) / 1.8, 0.0, 1.0)
    stereo *= (fade_in * fade_out)[:, None]

    peak = float(np.max(np.abs(stereo)))
    if peak > 0:
        stereo *= 0.82 / peak

    pcm = np.clip(stereo * 32767, -32768, 32767).astype("<i2")
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())


def encode_previews(voice: Path, music_wav: Path, voice_preview: Path, music_preview: Path) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(voice),
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            str(SAMPLE_RATE),
            str(voice_preview),
        ]
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(music_wav),
            "-af",
            f"loudnorm=I=-26:TP=-7:LRA=5,aresample={SAMPLE_RATE}",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            str(SAMPLE_RATE),
            str(music_preview),
        ]
    )


def mix_video(video: Path, voice: Path, music: Path, output: Path) -> None:
    graph = (
        "[1:a]asplit=2[voice][voice_sc];"
        "[2:a]volume=0.66[music];"
        "[music][voice_sc]sidechaincompress="
        "threshold=0.02:ratio=4:attack=35:release=500:makeup=1[ducked];"
        "[voice][ducked]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,"
        "alimiter=limit=0.95,loudnorm=I=-16:TP=-1.5:LRA=7,"
        f"afade=t=out:st=29.6:d=0.4,aresample={SAMPLE_RATE}[mix]"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(video),
            "-i",
            str(voice),
            "-i",
            str(music),
            "-filter_complex",
            graph,
            "-map",
            "0:v:0",
            "-map",
            "[mix]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            str(SAMPLE_RATE),
            "-t",
            str(TARGET_SECONDS),
            "-movflags",
            "+faststart",
            str(output),
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("voice", type=Path)
    parser.add_argument("--video", type=Path, default=Path(__file__).with_name("NotchUsage-demo.mp4"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("NotchUsage-demo-zh.mp4"))
    parser.add_argument("--audio-dir", type=Path, default=Path(__file__).with_name("audio"))
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.audio_dir.mkdir(parents=True, exist_ok=True)
    voice_preview = args.audio_dir / "NotchUsage-voice-zh-processed.m4a"
    music_preview = args.audio_dir / "NotchUsage-background-soft.m4a"

    with tempfile.TemporaryDirectory(prefix="notchusage-voiceover-") as temporary:
        temp = Path(temporary)
        cleaned = temp / "voice-clean.wav"
        spaced = temp / "voice-spaced.wav"
        music_wav = temp / "music.wav"
        clean_voice(args.voice, cleaned)
        add_natural_pauses(cleaned, spaced)
        make_soft_music(music_wav)
        encode_previews(spaced, music_wav, voice_preview, music_preview)
        mix_video(args.video, spaced, music_preview, args.output)

    print(args.output)
    print(voice_preview)
    print(music_preview)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
