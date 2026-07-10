#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Optimiza las imágenes de fondo del launcher.
============================================
Lee   "imagenes fondo/*.png|jpg|webp"   (las originales, pesadas)
Genera "web/bg/bg1.jpg, bg2.jpg, ..."   (ligeras, las que usa el launcher)

Ejecuta esto cada vez que cambies las imágenes de fondo:
    python optimizar_fondos.py
"""

from pathlib import Path
from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "imagenes fondo"
DST = ROOT / "web" / "bg"

TARGET = (1600, 900)   # suficiente para la ventana del launcher
QUALITY = 80
EXTS = {".png", ".jpg", ".jpeg", ".webp"}

# Las capturas del juego suelen ser oscuras (cuevas/noche). Las realzamos un poco
# para que se vean bien detrás de la interfaz.
BRIGHTNESS = 1.45
CONTRAST = 1.06
SATURATION = 1.12


def main():
    if not SRC.is_dir():
        print(f"No existe la carpeta: {SRC}")
        return

    DST.mkdir(parents=True, exist_ok=True)
    for old in DST.glob("bg*.jpg"):
        old.unlink()

    imgs = sorted(p for p in SRC.iterdir() if p.suffix.lower() in EXTS)
    if not imgs:
        print("No hay imágenes en 'imagenes fondo/'")
        return

    total_in = total_out = 0
    for i, p in enumerate(imgs, 1):
        im = Image.open(p).convert("RGB")
        # recorta/escala a 16:9 cubriendo todo el área (como background-size: cover)
        tw, th = TARGET
        scale = max(tw / im.width, th / im.height)
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        left = (im.width - tw) // 2
        top = (im.height - th) // 2
        im = im.crop((left, top, left + tw, top + th))

        im = ImageEnhance.Brightness(im).enhance(BRIGHTNESS)
        im = ImageEnhance.Contrast(im).enhance(CONTRAST)
        im = ImageEnhance.Color(im).enhance(SATURATION)

        out = DST / f"bg{i}.jpg"
        im.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        total_in += p.stat().st_size
        total_out += out.stat().st_size
        print(f"  {p.name}  ->  {out.name}  ({out.stat().st_size // 1024} KB)")

    print(f"\n{len(imgs)} imágenes: {total_in // 1024 // 1024} MB -> {total_out // 1024} KB")
    print(f"Guardadas en: {DST}")


if __name__ == "__main__":
    main()
