"""Monta intro -> set de 66 s como una base H.264 con audio sincronizado.

Uso: python scripts/build_nfc_base.py --ffmpeg RUTA_A_FFMPEG
Los originales se conservan. FFmpeg solo hace falta para generar el archivo.
"""

import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def duration(ffmpeg, path):
    result = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)],
                            capture_output=True, text=True)
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
    if not match:
        raise ValueError(f"No se pudo leer la duración de {path}")
    hours, minutes, seconds = map(float, match.groups())
    return hours * 3600 + minutes * 60 + seconds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    folder = ROOT / "media" / "pantalla"
    intro, scene = folder / "bigBangIntro.mp4", folder / "setBigBang.mp4"
    intro_seconds = duration(args.ffmpeg, intro)
    scene_seconds = duration(args.ffmpeg, scene)
    # 64 s de movimiento (también durante el fundido de entrada) + 2 s al final.
    # La canción se ajusta de 22,53 a 22 s sin cambiar su tono: tres vueltas = 66 s.
    normalize = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p"
    filters = (
        f"[0:v]setpts=PTS-STARTPTS,{normalize},fade=t=in:st=0:d=2,"
        f"fade=t=out:st={intro_seconds - 2:.6f}:d=2[v0];"
        f"[1:v]setpts=(PTS-STARTPTS)*{64 / scene_seconds:.10f},{normalize},"
        "trim=duration=64,tpad=stop_mode=clone:stop_duration=2,"
        "trim=duration=66,fade=t=in:st=0:d=2,fade=t=out:st=64:d=2[v1];"
        f"[0:a]asplit=2[original][song];"
        f"[original]asetpts=PTS-STARTPTS,apad,atrim=duration={intro_seconds},"
        f"afade=t=in:st=0:d=2,afade=t=out:st={intro_seconds - 2:.6f}:d=2[a0];"
        f"[song]asetpts=PTS-STARTPTS,atempo={intro_seconds / 22:.10f},apad,atrim=duration=22,"
        "afade=t=in:st=0:d=0.015,afade=t=out:st=21.985:d=0.015,asplit=3[a][b][c];"
        "[a][b][c]concat=n=3:v=0:a=1,afade=t=in:st=0:d=2,afade=t=out:st=64:d=2[a1];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][audio]"
    )
    output = folder / "bigBangBase.mp4"
    temporary = folder / "bigBangBase.build.mp4"
    subprocess.run([
        args.ffmpeg, "-hide_banner", "-y", "-i", str(intro), "-i", str(scene),
        "-filter_complex", filters, "-map", "[v]", "-map", "[audio]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart", str(temporary),
    ], check=True)
    temporary.replace(output)
    print(f"Base preparada: {output} ({duration(args.ffmpeg, output):.2f} s)")


if __name__ == "__main__":
    main()
