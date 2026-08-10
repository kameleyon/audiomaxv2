#!/usr/bin/env python3
"""
SPIKE D renderers — one geometry, three media.

    layout.Page ──> PDF   (born-digital: the two-column academic paper case)
                ──> PNG   (a clean scan, 200 dpi, flat and square)
                ──> JPG   (a CAMERA PHOTOGRAPH: perspective, lighting, blur,
                           sensor noise, lossy compression)

The three fixtures are not three transcriptions of a page; they are three
renderings of ONE placement, so the answer key is identical across them and any
difference in score is a property of the medium and the engine, never of the
truth. That is the point of generating rather than collecting.

THE PDF WRITER is deliberately about eighty lines and has no dependency. It
writes one `Tm`/`Tj` pair per word at the word's own origin, which is what a
typesetter emits and what every extractor is built to read. It does NOT embed a
font: base-14 `/Helvetica` with `/WinAnsiEncoding` covers en/es/fr including
diacritics, and embedding would mean committing a Microsoft font file.

THE CAMERA MODEL, and what it is not.
====================================
`camera()` applies, in this order and all seeded:

  1. a perspective homography from a fixed non-degenerate quad (about 11 deg of
     tilt and a small roll) -- the page is not fronto-parallel;
  2. a multiplicative illumination gradient plus a soft radial falloff --
     one-sided window light and a vignette;
  3. anisotropic Gaussian blur -- the focal plane is not the page plane;
  4. Gaussian sensor noise;
  5. JPEG at quality 68.

It is a SIMULATION, and the artifact says so in `_limits.camera_is_synthetic`.
A real phone photograph additionally carries rolling-shutter skew, a curved
page (this page stays planar -- no cylindrical page-curl term), specular
highlights from glossy stock, motion blur, and a demosaicing pipeline. A result
on this fixture is therefore an UPPER BOUND on real camera performance, and
must not be quoted as though a phone had taken it. What it does establish
soundly is the negative: an engine that cannot recover reading order HERE will
not recover it on a real photograph.
"""
from __future__ import annotations

import hashlib
import io
import pathlib

import cv2
import numpy as np
from PIL import Image, ImageDraw

import layout as L

OUT = pathlib.Path(__file__).parent / "out"
RASTER_DPI = 200
CAMERA_SEED = 20260814          # fixed before the run; not tuned to a result


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def _pdf_escape(s: str) -> bytes:
    b = s.encode("cp1252", errors="replace")
    out = bytearray()
    for ch in b:
        if ch in (0x28, 0x29, 0x5C):        # ( ) backslash
            out.append(0x5C)
        out.append(ch)
    return bytes(out)


def write_pdf(page: L.Page, path: pathlib.Path) -> pathlib.Path:
    """One page, one content stream, one Tm/Tj per word."""
    ops = []
    cur_size = None
    ops.append(b"BT")
    for w in page.all_words:
        if w.size != cur_size:
            ops.append(f"/F1 {w.size:.2f} Tf".encode("ascii"))
            cur_size = w.size
        # layout y is the TOP of the glyph box, origin top-left; PDF wants the
        # BASELINE, origin bottom-left. Arial's ascent is ~0.905 em.
        baseline = w.y0 + 0.905 * w.size
        ops.append(f"1 0 0 1 {w.x0:.2f} {page.height - baseline:.2f} Tm".encode("ascii"))
        ops.append(b"(" + _pdf_escape(w.text) + b") Tj")
    ops.append(b"ET")
    if getattr(page, "sidebar_box", None):
        x0, y0, x1, y1 = page.sidebar_box
        ops.append(f"0.5 w {x0:.2f} {page.height - y1:.2f} {x1-x0:.2f} "
                   f"{y1-y0:.2f} re S".encode("ascii"))
    content = b"\n".join(ops)

    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page.width:.0f} "
         f"{page.height:.0f}] /Resources << /Font << /F1 5 0 R >> >> "
         f"/Contents 4 0 R >>").encode("ascii"),
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(buf))
        buf += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(buf)
    buf += f"xref\n0 {len(objs)+1}\n".encode()
    buf += b"0000000000 65535 f \n"
    for off in offsets:
        buf += f"{off:010d} 00000 n \n".encode()
    buf += (f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n"
            f"{xref}\n%%EOF\n").encode()
    path.write_bytes(bytes(buf))
    return path


# ---------------------------------------------------------------------------
# RASTER
# ---------------------------------------------------------------------------

def render_raster(page: L.Page, dpi: int = RASTER_DPI) -> Image.Image:
    s = dpi / 72.0
    img = Image.new("L", (int(page.width * s), int(page.height * s)), 255)
    d = ImageDraw.Draw(img)
    for w in page.all_words:
        f = L.font_at(w.size)
        # Pillow measures at 10x; render with a same-face font at the true size.
        rf = L.ImageFont.truetype(str(L.FONT_PATH), max(1, int(round(w.size * s))))
        d.text((w.x0 * s, w.y0 * s), w.text, font=rf, fill=18)
    if getattr(page, "sidebar_box", None):
        x0, y0, x1, y1 = [v * s for v in page.sidebar_box]
        d.rectangle([x0, y0, x1, y1], outline=90, width=max(1, int(s)))
    return img


def camera(img: Image.Image, seed: int = CAMERA_SEED) -> Image.Image:
    """See the module docstring for what this models and what it does not."""
    rng = np.random.default_rng(seed)
    a = np.asarray(img).astype(np.float32)
    h, w = a.shape

    # 1. perspective. Corner offsets as a fraction of the page; fixed, not drawn
    #    from the RNG, so the geometry is inspectable and identical every run.
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dx, dy = 0.085 * w, 0.055 * h
    dst = np.float32([[0.30 * dx, 0.55 * dy],
                      [w - 1.00 * dx, 0.10 * dy],
                      [w - 0.55 * dx, h - 0.75 * dy],
                      [0.10 * dx, h - 0.20 * dy]])
    M = cv2.getPerspectiveTransform(src, dst)
    a = cv2.warpPerspective(a, M, (w, h), flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=138.0)

    # 2. illumination: one-sided gradient x radial falloff
    gx = np.linspace(1.14, 0.72, w, dtype=np.float32)[None, :]
    gy = np.linspace(1.05, 0.90, h, dtype=np.float32)[:, None]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    a *= gx * gy * (1.0 - 0.22 * np.clip(r, 0, 1.4) ** 2)

    # 3. defocus, stronger across the tilt axis
    a = cv2.GaussianBlur(a, (0, 0), sigmaX=1.35, sigmaY=0.85)

    # 4. sensor noise
    a += rng.normal(0.0, 3.4, size=a.shape).astype(np.float32)

    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), mode="L")
    # 5. lossy compression
    buf = io.BytesIO()
    out.convert("RGB").save(buf, format="JPEG", quality=68)
    buf.seek(0)
    return Image.open(buf).convert("L")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_all() -> dict:
    OUT.mkdir(exist_ok=True)
    manifest = {}
    for page in L.all_pages():
        radius = L.assert_context_unique(page.truth_tokens(), page.name)
        pdf = write_pdf(page, OUT / f"{page.name}.pdf")
        raster = render_raster(page)
        png = OUT / f"{page.name}-scan.png"
        raster.save(png, optimize=True)
        cam_path = OUT / f"{page.name}-camera.jpg"
        camera(raster).convert("RGB").save(cam_path, quality=95)
        manifest[page.name] = {
            "lang": page.lang,
            "body_tokens": len(page.body),
            "furniture_tokens": len(page.furniture),
            "context_radius": radius,
            "pdf": {"path": pdf.name, "sha256": sha256(pdf), "bytes": pdf.stat().st_size},
            "scan_png": {"path": png.name, "sha256": sha256(png), "bytes": png.stat().st_size},
            "camera_jpg": {"path": cam_path.name, "sha256": sha256(cam_path),
                           "bytes": cam_path.stat().st_size},
        }
        print(f"  {page.name:14s} pdf={pdf.stat().st_size//1024}kB "
              f"png={png.stat().st_size//1024}kB jpg={cam_path.stat().st_size//1024}kB "
              f"body={len(page.body)} furniture={len(page.furniture)} k={radius}")
    return manifest


if __name__ == "__main__":
    build_all()
