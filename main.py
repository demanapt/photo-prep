"""
photo-prep — конвертація фото для n8n.

POST /convert   тіло = бінарні дані картинки
                ?fmt=jpeg|png  &max_side=1600  &q=85
                → повертає готову картинку
                → заголовок X-Dominant-Color = #rrggbb

POST /palette   тіло = бінарні дані картинки
                → {"hex": "#3b2a20", "palette": [{"hex": ..., "share": 0.41}, ...]}

GET  /health    → {"ok": true}

Підтримує HEIC/HEIF, JPEG, PNG, WEBP, TIFF, BMP.
"""
import os
from collections import Counter
from io import BytesIO

import pillow_heif
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageOps

pillow_heif.register_heif_opener()

MAX_BYTES = 32 * 1024 * 1024
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")   # порожній = без перевірки

app = FastAPI(title="photo-prep", version="1.1")


@app.middleware("http")
async def guard(request: Request, call_next):
    """Якщо задано AUTH_TOKEN — усі шляхи, крім /health, вимагають заголовок X-Auth-Token."""
    if AUTH_TOKEN and request.url.path != "/health":
        if request.headers.get("x-auth-token") != AUTH_TOKEN:
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)


def _load(data: bytes) -> Image.Image:
    if not data:
        raise HTTPException(400, "empty body")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"file too large: {len(data)} bytes")
    try:
        im = Image.open(BytesIO(data))
        im.load()
    except Exception as exc:
        raise HTTPException(415, f"unsupported image: {exc}")
    return ImageOps.exif_transpose(im)


def _flatten(im: Image.Image) -> Image.Image:
    """Прозорість → білий фон, інакше JPEG падає."""
    if im.mode in ("RGBA", "LA", "PA"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.convert("RGBA").split()[-1])
        return bg
    return im.convert("RGB")


def _palette(im: Image.Image, top: int = 5) -> list[dict]:
    """Домінуючі кольори по центру кадру — там зазвичай сам одяг."""
    w, h = im.size
    box = (int(w * 0.25), int(h * 0.2), int(w * 0.75), int(h * 0.8))
    crop = _flatten(im).crop(box).resize((64, 64), Image.Resampling.BILINEAR)
    quant = crop.quantize(colors=8, method=Image.Quantize.FASTOCTREE).convert("RGB")

    counts = Counter(quant.getdata())
    total = sum(counts.values()) or 1
    return [
        {"hex": "#%02x%02x%02x" % rgb, "rgb": list(rgb), "share": round(n / total, 3)}
        for rgb, n in counts.most_common(top)
    ]


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/convert")
async def convert(
    request: Request,
    fmt: str = Query("jpeg", pattern="^(jpeg|jpg|png)$"),
    max_side: int = Query(1600, ge=200, le=6000),
    q: int = Query(85, ge=40, le=100),
) -> Response:
    im = _load(await request.body())
    colors = _palette(im)

    if max(im.size) > max_side:
        im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    buf = BytesIO()
    if fmt == "png":
        im.convert("RGBA" if im.mode in ("RGBA", "LA", "PA") else "RGB").save(
            buf, "PNG", optimize=True
        )
        media_type = "image/png"
    else:
        _flatten(im).save(buf, "JPEG", quality=q, optimize=True, progressive=True)
        media_type = "image/jpeg"

    return Response(
        content=buf.getvalue(),
        media_type=media_type,
        headers={
            "X-Dominant-Color": colors[0]["hex"] if colors else "",
            "X-Image-Width": str(im.size[0]),
            "X-Image-Height": str(im.size[1]),
        },
    )


@app.post("/palette")
async def palette(request: Request) -> JSONResponse:
    colors = _palette(_load(await request.body()))
    return JSONResponse({"hex": colors[0]["hex"] if colors else "", "palette": colors})
