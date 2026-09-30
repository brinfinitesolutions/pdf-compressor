from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import img2pdf

from bot.compress_image import CompressResult

# Highest quality first. First output under the cap wins.
_PRESETS: list[tuple[int, int]] = [
    (300, 95),
    (250, 90),
    (200, 85),
    (150, 80),
    (144, 75),
    (120, 70),
    (100, 60),
    (96, 50),
    (72, 40),
    (72, 30),
]
_RASTER_PRESETS: list[tuple[int, int]] = [
    (120, 50),
    (96, 40),
    (72, 35),
    (50, 30),
    (36, 25),
]


def _run_gs(src: Path, dest: Path, dpi: int, jpegq: int) -> bool:
    cmd = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        "-dSAFER",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dDownsampleColorImages=true",
        "-dDownsampleGrayImages=true",
        "-dDownsampleMonoImages=true",
        "-dColorImageDownsampleType=/Bicubic",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dMonoImageDownsampleType=/Subsample",
        f"-dColorImageResolution={dpi}",
        f"-dGrayImageResolution={dpi}",
        f"-dMonoImageResolution={min(dpi * 2, 300)}",
        "-dColorImageDownsampleThreshold=1.0",
        "-dGrayImageDownsampleThreshold=1.0",
        "-dMonoImageDownsampleThreshold=1.0",
        "-dEncodeColorImages=true",
        "-dEncodeGrayImages=true",
        "-dColorImageFilter=/DCTEncode",
        "-dGrayImageFilter=/DCTEncode",
        f"-dJPEGQ={jpegq}",
        f"-sOutputFile={dest}",
        str(src),
    ]
    try:
        completed = subprocess.run(cmd, check=False, capture_output=True, timeout=180)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and dest.is_file() and dest.stat().st_size > 0


def _rasterize_pdf(src: Path, dest: Path, dpi: int, jpegq: int) -> bool:
    with tempfile.TemporaryDirectory(prefix="gs-raster-") as tmp:
        pattern = str(Path(tmp) / "page-%d.jpg")
        cmd = [
            "gs",
            "-sDEVICE=jpeg",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            "-dSAFER",
            f"-r{dpi}",
            f"-dJPEGQ={jpegq}",
            f"-sOutputFile={pattern}",
            str(src),
        ]
        try:
            completed = subprocess.run(cmd, check=False, capture_output=True, timeout=180)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        if completed.returncode != 0:
            return False
        pages = sorted(Path(tmp).glob("page-*.jpg"), key=lambda p: p.name)
        if not pages:
            return False
        dest.write_bytes(img2pdf.convert([str(p) for p in pages]))
        return dest.is_file() and dest.stat().st_size > 0


def compress_pdf(src: str | Path, dest: str | Path, target_bytes: int) -> CompressResult:
    src_path = Path(src)
    dest_path = Path(dest)
    original_size = src_path.stat().st_size

    if original_size < target_bytes:
        shutil.copyfile(src_path, dest_path)
        return CompressResult(
            path=str(dest_path),
            size=original_size,
            under_target=True,
            quality=95,
            used_original=True,
        )

    if shutil.which("gs") is None:
        shutil.copyfile(src_path, dest_path)
        return CompressResult(
            path=str(dest_path),
            size=original_size,
            under_target=False,
            quality=0,
            used_original=True,
        )

    best_path: Path | None = None
    best_size = original_size
    best_quality = 0

    with tempfile.TemporaryDirectory(prefix="gs-pdf-") as tmp:
        tmp_dir = Path(tmp)
        for dpi, jpegq in _PRESETS:
            candidate = tmp_dir / f"out-{dpi}-{jpegq}.pdf"
            if not _run_gs(src_path, candidate, dpi, jpegq):
                continue
            size = candidate.stat().st_size
            if size < target_bytes:
                shutil.copyfile(candidate, dest_path)
                return CompressResult(
                    path=str(dest_path),
                    size=size,
                    under_target=True,
                    quality=jpegq,
                    used_original=False,
                )
            if size < best_size:
                best_size = size
                best_path = candidate
                best_quality = jpegq

        for dpi, jpegq in _RASTER_PRESETS:
            candidate = tmp_dir / f"raster-{dpi}-{jpegq}.pdf"
            if not _rasterize_pdf(src_path, candidate, dpi, jpegq):
                continue
            size = candidate.stat().st_size
            if size < target_bytes:
                shutil.copyfile(candidate, dest_path)
                return CompressResult(
                    path=str(dest_path),
                    size=size,
                    under_target=True,
                    quality=jpegq,
                    used_original=False,
                )
            if size < best_size:
                best_size = size
                best_path = candidate
                best_quality = jpegq

        if best_path is not None:
            shutil.copyfile(best_path, dest_path)
            return CompressResult(
                path=str(dest_path),
                size=best_size,
                under_target=best_size < target_bytes,
                quality=best_quality,
                used_original=False,
            )

    shutil.copyfile(src_path, dest_path)
    return CompressResult(
        path=str(dest_path),
        size=original_size,
        under_target=False,
        quality=0,
        used_original=True,
    )
