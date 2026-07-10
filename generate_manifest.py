#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CobbleverseMMO - Generador de Manifests
========================================
Escanea los perfiles de Modrinth App y genera:

  github-repo/manifests/normal.json     <- manifest descargado por el launcher
  github-repo/manifests/lite.json
  github-repo/configs/normal/...        <- configs en el repo de git
  github-repo/configs/lite/...

  upload_normal.ps1   <- sube binarios a GitHub Releases
  upload_lite.ps1

Los shader packs en carpeta se empaquetan como .zip automaticamente.

Uso:
  1. Edita GITHUB_OWNER abajo.
  2. python generate_manifest.py
  3. Sigue los pasos que aparecen al final.
"""

import hashlib
import json
import os
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

# UTF-8 en consola Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────────────────

GITHUB_OWNER = "DropsIZI"               # usuario de GitHub
GITHUB_REPO  = "cobbleversemmo-modpack"

RELEASE_TAG_NORMAL = "v1.5-normal"
RELEASE_TAG_LITE   = "v1.5-lite"

APPDATA = Path(os.environ.get("APPDATA", Path.home()))

PROFILES = {
    "normal": APPDATA / "ModrinthApp" / "profiles" / "COBBLEVERSEMMO 1.5",
    "lite":   APPDATA / "ModrinthApp" / "profiles" / "POTATOVERSEMMO 1.5",
}

# Carpetas con archivos binarios grandes -> GitHub Releases
BINARY_CATEGORIES = ["mods", "datapacks", "resourcepacks"]

# Config -> repo de git (raw.githubusercontent.com)
CONFIG_CATEGORIES = ["config"]

# Shaderpacks -> GitHub Releases (carpetas se empaquetan como ZIP)
SHADERPACK_CATEGORY = "shaderpacks"

# Estas carpetas se ignoran completamente
SKIP_CATEGORIES = {"saves", "screenshots", "logs", "crash-reports"}

# Archivos individuales a excluir
EXCLUDE_EXTENSIONS = {".bak", ".bak1"}
EXCLUDE_NAMES = {
    "usercache.json",
    "usernamecache.json",
    "sodium-fingerprint.json",
    "xaeropatreon.txt",
    "xaerohud.txt",
    "_0EUPHORIA_PATCHES_ERROR_LOGS.txt",
    ".data.json",   # euphoria_patcher lo crea oculto+solo-lectura en cada arranque
}

OUTPUT_DIR    = Path(__file__).parent / "github-repo"
MANIFESTS_DIR = OUTPUT_DIR / "manifests"
CONFIGS_OUT   = OUTPUT_DIR / "configs"
STAGING_DIR   = Path(__file__).parent / "_staging"  # temp ZIPs de shaders

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def fmt_bytes(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} GB"

def gh_release_url(tag: str, asset: str) -> str:
    o = GITHUB_OWNER if GITHUB_OWNER else "YOUR_GITHUB_USERNAME"
    return f"https://github.com/{o}/{GITHUB_REPO}/releases/download/{tag}/{asset}"

def gh_raw_url(repo_path: str) -> str:
    o = GITHUB_OWNER if GITHUB_OWNER else "YOUR_GITHUB_USERNAME"
    return f"https://raw.githubusercontent.com/{o}/{GITHUB_REPO}/main/{repo_path}"

def path_to_asset(rel_path: str) -> str:
    """Devuelve solo el nombre de archivo (sin directorio)."""
    return Path(rel_path).name

def should_skip(path: Path) -> bool:
    return path.suffix.lower() in EXCLUDE_EXTENSIONS or path.name in EXCLUDE_NAMES

def zip_folder(folder: Path, dest_zip: Path):
    """Empaqueta una carpeta en un archivo ZIP."""
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for fp in sorted(folder.rglob("*")):
            if fp.is_file():
                zf.write(fp, fp.relative_to(folder))

# ─────────────────────────────────────────────────────────────────────────────
#  Procesado de shaderpacks
# ─────────────────────────────────────────────────────────────────────────────

def process_shaderpacks(profile_path: Path, staging: Path) -> list:
    """
    Devuelve lista de entries de manifest para shaderpacks.
    - Archivos .zip / .txt / .properties: se incluyen tal cual.
    - Subcarpetas: se empaquetan como .zip en staging/.
    """
    shader_dir = profile_path / SHADERPACK_CATEGORY
    if not shader_dir.exists():
        return []

    entries = []
    staging.mkdir(parents=True, exist_ok=True)

    # Archivos directos (zip, txt, etc.)
    for fp in sorted(shader_dir.iterdir()):
        if fp.is_file() and not should_skip(fp):
            entries.append({
                "_src": fp,
                "rel":  f"shaderpacks/{fp.name}",
                "asset": f"shaderpacks--{fp.name}",
            })

    # Subcarpetas -> crear ZIP
    for folder in sorted(shader_dir.iterdir()):
        if not folder.is_dir():
            continue
        zip_name = folder.name + ".zip"
        zip_path = staging / zip_name
        print(f"    Empaquetando shader: {folder.name} ...", end=" ", flush=True)
        zip_folder(folder, zip_path)
        size = zip_path.stat().st_size
        print(f"{fmt_bytes(size)}")
        entries.append({
            "_src":  zip_path,
            "rel":   f"shaderpacks/{zip_name}",
            "asset": f"shaderpacks--{zip_name}",
        })

    return entries

# ─────────────────────────────────────────────────────────────────────────────
#  Generacion de manifest
# ─────────────────────────────────────────────────────────────────────────────

def generate_manifest(version_key: str, profile_path: Path, release_tag: str) -> dict:
    print(f"\n  Escaneando {version_key.upper()}: {profile_path}")

    if not profile_path.exists():
        print(f"  ERROR: Carpeta no encontrada: {profile_path}")
        sys.exit(1)

    files = []
    stats = {"bin": [0, 0], "cfg": [0, 0], "shd": [0, 0]}

    # --- Binarios (mods, datapacks, resourcepacks) -> GitHub Releases ---
    for category in BINARY_CATEGORIES:
        cat_dir = profile_path / category
        if not cat_dir.exists():
            continue
        for fp in sorted(cat_dir.rglob("*")):
            if not fp.is_file() or should_skip(fp):
                continue
            rel   = fp.relative_to(profile_path).as_posix()
            asset = path_to_asset(rel)
            size  = fp.stat().st_size
            cksum = sha256(fp)
            files.append({
                "path":   rel,
                "url":    gh_release_url(release_tag, asset),
                "sha256": cksum,
                "size":   size,
                "_type":  "release",
                "_src":   str(fp),
                "_asset": asset,
            })
            stats["bin"][0] += 1
            stats["bin"][1] += size

    # --- Config -> git repo (raw.githubusercontent.com) ---
    config_out_base = CONFIGS_OUT / version_key
    for category in CONFIG_CATEGORIES:
        cat_dir = profile_path / category
        if not cat_dir.exists():
            continue
        for fp in sorted(cat_dir.rglob("*")):
            if not fp.is_file() or should_skip(fp):
                continue
            rel      = fp.relative_to(profile_path).as_posix()
            repo_rel = f"configs/{version_key}/{rel}"
            size     = fp.stat().st_size
            cksum    = sha256(fp)

            out_fp = config_out_base / fp.relative_to(cat_dir.parent)
            out_fp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fp, out_fp)

            files.append({
                "path":   rel,
                "url":    gh_raw_url(repo_rel),
                "sha256": cksum,
                "size":   size,
                "_type":  "git",
            })
            stats["cfg"][0] += 1
            stats["cfg"][1] += size

    # --- Shaderpacks -> GitHub Releases (carpetas zipeadas) ---
    staging = STAGING_DIR / version_key
    shader_entries = process_shaderpacks(profile_path, staging)
    for se in shader_entries:
        fp    = se["_src"]
        size  = fp.stat().st_size
        cksum = sha256(fp)
        files.append({
            "path":   se["rel"],
            "url":    gh_release_url(release_tag, se["asset"]),
            "sha256": cksum,
            "size":   size,
            "_type":  "release",
            "_src":   str(fp),
            "_asset": se["asset"],
        })
        stats["shd"][0] += 1
        stats["shd"][1] += size

    print(f"  Mods/DP/RP : {stats['bin'][0]:3} archivos | {fmt_bytes(stats['bin'][1])}")
    print(f"  Config     : {stats['cfg'][0]:3} archivos | {fmt_bytes(stats['cfg'][1])}")
    print(f"  Shaderpacks: {stats['shd'][0]:3} archivos | {fmt_bytes(stats['shd'][1])}")

    names = {"normal": "CobbleverseMMO", "lite": "POTATOVERSEMMO (LITE)"}
    total = stats["bin"][1] + stats["cfg"][1] + stats["shd"][1]
    return {
        "version":           "1.5",
        "name":              names.get(version_key, version_key),
        "minecraft_version": "1.21.1",
        "loader":            "fabric",
        "updated_at":        str(date.today()),
        "file_count":        len(files),
        "total_size":        total,
        "files":             files,
    }

# ─────────────────────────────────────────────────────────────────────────────
#  Script PowerShell de subida
# ─────────────────────────────────────────────────────────────────────────────

def generate_upload_ps1(version_key: str, manifest: dict, release_tag: str) -> str:
    owner = GITHUB_OWNER if GITHUB_OWNER else "YOUR_GITHUB_USERNAME"

    # Agrupar por categoria
    categories: dict[str, list] = {}
    for entry in manifest["files"]:
        if entry.get("_type") != "release":
            continue
        cat = entry["path"].split("/")[0]
        categories.setdefault(cat, []).append(entry)

    # Nota: la release ya debe existir antes de correr este script
    lines = [
        "# -----------------------------------------------------------------",
        f"# Upload {version_key.upper()} modpack files to GitHub Releases",
        "# Requirements: GitHub CLI -> https://cli.github.com/",
        "#               Run first:   gh auth login",
        "# -----------------------------------------------------------------",
        "",
        f'$OWNER = "{owner}"',
        f'$REPO  = "{GITHUB_REPO}"',
        f'$TAG   = "{release_tag}"',
        "",
        "# Create release if it doesn't exist yet (skips silently if already there)",
        f'gh release create $TAG --title "CobbleverseMMO {version_key.upper()} {release_tag}" --notes "Modpack files auto-downloaded by the launcher." --repo "$OWNER/$REPO" 2>$null',
        "",
    ]

    for cat, entries in categories.items():
        exts = "|".join(sorted(set(Path(e["path"]).suffix for e in entries)))
        lines.append(f"# --- {cat}/ ({len(entries)} files [{exts}]) ---")
        lines.append(f"Write-Host 'Uploading {cat}/ ({len(entries)} files) ...'")
        lines.append("$uploads = @(")
        for idx, entry in enumerate(entries):
            src   = entry["_src"]
            asset = entry["_asset"]
            # Sin coma en el ultimo elemento del array
            comma = "," if idx < len(entries) - 1 else ""
            lines.append(f'    @{{ P="{src}"; N="{asset}" }}{comma}')
        lines.append(")")
        lines.append("foreach ($u in $uploads) {")
        lines.append("    Write-Host \"  $($u.N)\"")
        lines.append('    gh release upload $TAG $u.P --clobber --repo "$OWNER/$REPO"')
        lines.append("}")
        lines.append("")

    lines += [
        "Write-Host ''",
        "Write-Host 'Done!'",
        'Write-Host "  https://github.com/$OWNER/$REPO/releases/tag/$TAG"',
    ]
    return "\r\n".join(lines)

# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 62)
    print("  CobbleverseMMO - Generador de Manifests")
    print("=" * 62)

    if not GITHUB_OWNER:
        print()
        print("  AVISO: GITHUB_OWNER no esta configurado.")
        print("  Edita generate_manifest.py y pon tu usuario de GitHub.")

    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    configs = {
        "normal": (PROFILES["normal"], RELEASE_TAG_NORMAL),
        "lite":   (PROFILES["lite"],   RELEASE_TAG_LITE),
    }

    upload_scripts = {}

    for version_key, (profile_path, release_tag) in configs.items():
        manifest = generate_manifest(version_key, profile_path, release_tag)

        # Guardar manifest limpio (sin campos internos _*)
        manifest_clean = {k: v for k, v in manifest.items() if k != "files"}
        manifest_clean["files"] = [
            {fk: fv for fk, fv in e.items() if not fk.startswith("_")}
            for e in manifest["files"]
        ]

        manifest_file = MANIFESTS_DIR / f"{version_key}.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_clean, f, indent=2, ensure_ascii=False)
        print(f"\n  [OK] Manifest guardado: {manifest_file}")

        script = generate_upload_ps1(version_key, manifest, release_tag)
        script_file = Path(__file__).parent / f"upload_{version_key}.ps1"
        with open(script_file, "w", encoding="utf-8", newline="") as f:
            f.write(script)
        upload_scripts[version_key] = script_file
        print(f"  [OK] Script de subida : {script_file}")

    # Limpiar staging temporal
    if STAGING_DIR.exists():
        pass  # Mantener staging por si se necesita reintentar la subida

    print()
    print("=" * 62)
    print("  PASOS SIGUIENTES")
    print("=" * 62)
    print()
    print("1. Crea el repositorio GitHub:")
    print(f"   https://github.com/new  ->  nombre: {GITHUB_REPO}")
    print()
    print("2. Sube el repo:")
    print(f"   cd \"{OUTPUT_DIR}\"")
    print("   git init && git add .")
    print("   git commit -m \"Initial modpack v1.5\"")
    print(f"   git remote add origin https://github.com/TU_USUARIO/{GITHUB_REPO}.git")
    print("   git branch -M main && git push -u origin main")
    print()
    print("3. Instala GitHub CLI:  https://cli.github.com/")
    print("   gh auth login")
    print()
    print("4. Sube los binarios (mods, datapacks, resourcepacks, shaders):")
    print("   (puede tardar 30-90 min segun tu conexion)")
    for key, script in upload_scripts.items():
        print(f"   .\\{script.name}")
    print()
    print("5. Configura launcher_config.json:")
    print('   "github_owner": "tu-usuario-github"')
    print()
    print("6. Prueba: python launcher.py")
    print()
    print("Para futuros updates:")
    print("  a. Actualiza mods en Modrinth App")
    print("  b. python generate_manifest.py")
    print("  c. Sube solo los archivos NUEVOS/CAMBIADOS al release")
    print("  d. git add manifests/ configs/ && git commit && git push")
    print()


if __name__ == "__main__":
    main()
