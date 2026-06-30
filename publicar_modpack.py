#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publicar modpack — TODO en un solo comando.
============================================
Ejecuta:  python publicar_modpack.py   (o doble clic en Publicar-Modpack.bat)

Hace los 3 pasos seguidos:
  1. Regenera los manifests escaneando tus perfiles de Modrinth
  2. Sube los binarios (mods, datapacks, resourcepacks, shaders) a GitHub Releases
  3. Sube los manifests y configs al repo del modpack (git push)

Requisitos (una sola vez):
  - Tener el/los perfil(es) de Modrinth del modpack instalados
  - GitHub CLI:  https://cli.github.com/   ->   gh auth login
  - Acceso de escritura al repo cobbleversemmo-modpack
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE / "github-repo"


def paso(titulo):
    print("\n" + "=" * 60)
    print("  " + titulo)
    print("=" * 60)


def run(cmd, cwd=None, obligatorio=True):
    print(f"\n$ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if r.returncode != 0 and obligatorio:
        print("\n  ⚠ Este paso falló. Revisa el mensaje de arriba y vuelve a intentarlo.")
        input("  (Enter para salir)")
        sys.exit(1)
    return r.returncode


def main():
    print("=" * 60)
    print("  PUBLICAR MODPACK — CobbleverseMMO")
    print("=" * 60)

    # 1. Regenerar manifests
    paso("Paso 1/3 · Regenerando manifests desde Modrinth")
    run([sys.executable, str(HERE / "generate_manifest.py")])

    # 2. Subir binarios a los Releases
    paso("Paso 2/3 · Subiendo archivos a GitHub Releases (puede tardar)")
    for ps1 in ("upload_normal.ps1", "upload_lite.ps1"):
        script = HERE / ps1
        if script.exists():
            run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)])
        else:
            print(f"  (saltando {ps1}: no existe — ¿no hay esa versión?)")

    # 3. Subir manifests + configs al repo
    paso("Paso 3/3 · Subiendo manifests y configs a GitHub")
    run(["git", "add", "manifests", "configs"], cwd=REPO)
    msg = input("\n  Describe el cambio (ej. 'añadidos 3 Pokémon'): ").strip() \
        or "Actualización del modpack"
    # commit puede no tener nada que confirmar; no es error
    run(["git", "commit", "-m", msg], cwd=REPO, obligatorio=False)
    run(["git", "push"], cwd=REPO)

    print("\n" + "=" * 60)
    print("  ✓ ¡LISTO! Los jugadores lo descargarán al pulsar JUGAR.")
    print("=" * 60 + "\n")
    input("  (Enter para cerrar)")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n  Cancelado.")
