"""Empaquetar, comprobar y descargar vídeos sin dependencias adicionales."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parent.parent
EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv"}


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def safe_path(root, name):
    parts = PurePosixPath(name)
    if (not name or parts.is_absolute() or "\\" in name or ":" in name
            or any(part in {".", "..", ""} for part in name.split("/"))
            or any(part.endswith((".", " ")) for part in parts.parts)):
        raise ValueError(f"Ruta de media inválida: {name}")
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"La ruta sale de media/: {name}")
    return target


def read_manifest(root):
    data = json.loads((root / "media-manifest.json").read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("files"), list) or not data["files"]:
        raise ValueError("Manifiesto de media vacío o inválido")
    seen = set()
    for entry in data["files"]:
        name = entry["path"]
        safe_path(root / "media", name)
        if name.casefold() in seen:
            raise ValueError(f"Ruta duplicada: {name}")
        seen.add(name.casefold())
        if (type(entry["size"]) is not int or entry["size"] < 0
                or len(entry["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in entry["sha256"])):
            raise ValueError(f"Tamaño/hash inválido: {name}")
    return data["files"]


def matches(path, entry):
    return path.is_file() and path.stat().st_size == entry["size"] and digest(path) == entry["sha256"]


def pack(root):
    media = root / "media"
    paths = sorted(p for p in media.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS)
    if not paths:
        raise ValueError("No hay vídeos en media/")
    destination = root / "media-dist"
    destination.mkdir(exist_ok=True)
    entries = []
    archive = destination / "bigbang-media.zip"
    temporary = destination / "bigbang-media.zip.part"
    try:
        # MP4 ya está comprimido; ZIP_STORED evita gastar tiempo recomprimiéndolo.
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as bundle:
            for path in paths:
                name = path.relative_to(media).as_posix()
                safe_path(media, name)
                before = path.stat()
                checksum = digest(path)
                bundle.write(path, name)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError(f"El vídeo cambió mientras se empaquetaba: {name}")
                entries.append({"path": name, "size": before.st_size, "sha256": checksum})
        os.replace(temporary, archive)
    finally:
        temporary.unlink(missing_ok=True)
    manifest = root / "media-manifest.json"
    manifest.write_text(json.dumps({"version": 1, "files": entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ZIP preparado: {archive} ({archive.stat().st_size / 1024**2:.1f} MiB)")
    print(f"Manifiesto actualizado: {len(entries)} vídeos. Guarda este JSON en Git.")
    return archive


def check(root):
    entries = read_manifest(root)
    missing = [e for e in entries if not matches(safe_path(root / "media", e["path"]), e)]
    for entry in missing:
        print(f"Falta o difiere: {entry['path']}")
    print(f"Vídeos verificados: {len(entries) - len(missing)}/{len(entries)}")
    return missing


def install_archive(root, archive, entries):
    media = root / "media"
    media.mkdir(exist_ok=True)
    cache = root / ".cache"
    cache.mkdir(exist_ok=True)
    # Se verifican TODOS los archivos antes de sustituir ninguno.
    with tempfile.TemporaryDirectory(prefix="media-stage-", dir=cache) as directory:
        stage = Path(directory)
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            if len(names) != len(set(names)):
                raise ValueError("El ZIP contiene entradas duplicadas")
            for info in bundle.infolist():
                safe_path(stage, info.filename.rstrip("/"))
            for entry in entries:
                name = entry["path"]
                info = bundle.getinfo(name)
                if info.file_size != entry["size"]:
                    raise ValueError(f"Tamaño incorrecto: {name}")
                target = safe_path(stage, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                if not matches(target, entry):
                    raise ValueError(f"Checksum incorrecto: {name}")
        for entry in entries:
            target = safe_path(media, entry["path"])
            if matches(target, entry):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(safe_path(stage, entry["path"]), target)


def sync(root, url=None, archive=None):
    entries = read_manifest(root)
    if not check(root):
        print("Media completa. No se necesita descargar nada.")
        return
    if archive:
        install_archive(root, Path(archive), entries)
    else:
        source = root / "media-source.json"
        configured = json.loads(source.read_text(encoding="utf-8")).get("url") if source.exists() else None
        url = url or os.environ.get("BIGBANG_MEDIA_URL") or configured
        if not url:
            folder = json.loads(source.read_text(encoding="utf-8")).get("folder_url") if source.exists() else None
            if folder:
                raise ValueError(f"Descarga bigbang-media.zip desde {folder} y ejecuta descargar_media.bat --archive RUTA_AL_ZIP")
            raise ValueError("Configura url en media-source.json o BIGBANG_MEDIA_URL, o usa --archive ruta.zip")
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Se necesita un enlace directo HTTP(S) al ZIP")
        cache = root / ".cache"
        cache.mkdir(exist_ok=True)
        # Límite suficiente para el ZIP sin compresión generado por pack.
        maximum = sum(e["size"] for e in entries) + max(1024**2, len(entries) * 4096)
        with tempfile.TemporaryDirectory(prefix="media-download-", dir=cache) as directory:
            downloaded = Path(directory) / "media.zip"
            print("Descargando el paquete de media…", flush=True)
            size, reported = 0, 0
            with urlopen(url, timeout=60) as response, downloaded.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > maximum:
                        raise ValueError("El ZIP supera el tamaño esperado; comprueba el enlace y el manifiesto")
                    output.write(chunk)
                    if size - reported >= 50 * 1024**2:
                        print(f"  {size / 1024**2:.0f} MiB descargados", flush=True)
                        reported = size
            install_archive(root, downloaded, entries)
    print("Media instalada y verificada. Puedes iniciar la aplicación.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["pack", "check", "sync"])
    parser.add_argument("--url", help="Enlace directo al ZIP")
    parser.add_argument("--archive", type=Path, help="Instalar desde ZIP local o de una unidad compartida")
    args = parser.parse_args()
    try:
        if args.command == "pack":
            pack(ROOT)
        elif args.command == "check":
            return 1 if check(ROOT) else 0
        else:
            sync(ROOT, args.url, args.archive)
    except Exception as exc:
        # Las excepciones HTTP pueden incluir enlaces con tokens; no mostrarlos.
        detail = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print(f"No se pudo completar la operación: {detail}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
