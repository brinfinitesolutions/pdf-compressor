from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

MIN_QUALITY = 20
MAX_QUALITY = 95
MIN_LONG_SIDE = 640
SCALE_STEP = 0.9


@dataclass
class CompressResult:
    path: str
    size: int
    under_target: bool
    quality: int
    used_original: bool


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return image.convert("RGB")


def _jpeg_bytes(image: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _best_jpeg_under(image: Image.Image, target_bytes: int) -> tuple[bytes, int] | None:
    lo, hi = MIN_QUALITY, MAX_QUALITY
    best: tuple[bytes, int] | None = None
    while lo <= hi:
        mid = (lo + hi) // 2
        data = _jpeg_bytes(image, mid)
        if len(data) < target_bytes:
            best = (data, mid)
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def compress_image(src: str | Path, dest: str | Path, target_bytes: int) -> CompressResult:
    src_path = Path(src)
    dest_path = Path(dest)
    original = src_path.read_bytes()
    original_size = len(original)

    if original_size < target_bytes:
        keep = dest_path.with_suffix(src_path.suffix or dest_path.suffix)
        keep.write_bytes(original)
        return CompressResult(
            path=str(keep),
            size=original_size,
            under_target=True,
            quality=MAX_QUALITY,
            used_original=True,
        )

    with Image.open(src_path) as opened:
        work = _to_rgb(opened)
        work.load()

    smallest: tuple[bytes, int] | None = None
    chosen: tuple[bytes, int] | None = None

    while True:
        fit = _best_jpeg_under(work, target_bytes)
        if fit is not None:
            chosen = fit
            break

        data = _jpeg_bytes(work, MIN_QUALITY)
        if smallest is None or len(data) < len(smallest[0]):
            smallest = (data, MIN_QUALITY)

        width, height = work.size
        if max(width, height) <= MIN_LONG_SIDE:
            break
        new_size = (max(1, int(width * SCALE_STEP)), max(1, int(height * SCALE_STEP)))
        if new_size == work.size:
            break
        work = work.resize(new_size, Image.Resampling.LANCZOS)

    payload, quality = chosen if chosen is not None else (smallest or (_jpeg_bytes(work, MIN_QUALITY), MIN_QUALITY))
    dest_path.write_bytes(payload)
    return CompressResult(
        path=str(dest_path),
        size=len(payload),
        under_target=len(payload) < target_bytes,
        quality=quality,
        used_original=False,
    )
