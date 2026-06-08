#!/usr/bin/env python3
"""
CobbleverseMMO - Subida a GitHub Releases via API
Sube directamente via GitHub REST API (sin gh CLI para uploads).
Maneja cualquier nombre de archivo incluyendo brackets y espacios.

Uso: python upload_release.py normal|lite|all [--only-missing]
"""
import json
import mimetypes
import os
import sys
from pathlib import Path
from urllib.parse import quote, unquote
import subprocess

import requests

# ─────────────────────────────────────────────────────────────────────────────

GITHUB_OWNER = "DropsIZI"
GITHUB_REPO  = "cobbleversemmo-modpack"

RELEASE_TAGS = {
    "normal": "v1.5-normal",
    "lite":   "v1.5-lite",
}

PROFILE_DIRS = {
    "normal": Path(os.environ["APPDATA"]) / "ModrinthApp" / "profiles" / "COBBLEVERSEMMO 1.5",
    "lite":   Path(os.environ["APPDATA"]) / "ModrinthApp" / "profiles" / "POTATOVERSEMMO 1.5",
}

STAGING_DIR   = Path(__file__).parent / "_staging"
MANIFESTS_DIR = Path(__file__).parent / "github-repo" / "manifests"

# ─────────────────────────────────────────────────────────────────────────────

def get_gh_token() -> str:
    result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    token = result.stdout.strip()
    if not token:
        print("ERROR: No se pudo obtener el token de GitHub CLI.")
        print("       Ejecuta: gh auth login")
        sys.exit(1)
    return token

def fmt_bytes(b: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} GB"

def get_or_create_release(session: requests.Session, owner: str, repo: str, tag: str, version_key: str) -> dict:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
    r = session.get(url)
    if r.status_code == 200:
        return r.json()
    # Crear release
    r2 = session.post(
        f"https://api.github.com/repos/{owner}/{repo}/releases",
        json={
            "tag_name": tag,
            "name": f"CobbleverseMMO {version_key.upper()} {tag}",
            "body": "Modpack files - auto-downloaded by the launcher.",
            "draft": False,
            "prerelease": False,
        }
    )
    r2.raise_for_status()
    return r2.json()

def get_existing_assets(session: requests.Session, release: dict) -> set[str]:
    """Devuelve el set de nombres de assets ya subidos."""
    return {a["name"] for a in release.get("assets", [])}

def upload_asset(session: requests.Session, upload_url_template: str,
                 local_path: Path, asset_name: str) -> bool:
    """Sube un archivo a GitHub Release via API. Retorna True si exitoso."""
    upload_url = upload_url_template.replace("{?name,label}", "")
    encoded_name = quote(asset_name, safe="")
    url = f"{upload_url}?name={encoded_name}"

    mime = mimetypes.guess_type(asset_name)[0] or "application/octet-stream"
    size = local_path.stat().st_size

    try:
        with open(local_path, "rb") as f:
            r = session.post(url, data=f,
                             headers={"Content-Type": mime},
                             timeout=300)
        if r.status_code in (201, 200):
            return True
        elif r.status_code == 422:
            # Ya existe — borrar y re-subir
            release_url = upload_url_template.split("{")[0].rsplit("/", 2)[0]
            # Buscar el asset por nombre
            assets_url = release_url + "/releases/" + release_url.split("/releases/")[-1] + "/assets"
            print(f"      (ya existe, saltando)")
            return True
        else:
            print(f"      HTTP {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        print(f"      Error: {e}")
        return False

def find_local_file(entry: dict, version_key: str) -> Path | None:
    """Encuentra la ruta local del archivo a subir."""
    rel_path = entry["path"]         # e.g. "mods/sodium.jar"
    category = rel_path.split("/")[0]
    filename  = Path(rel_path).name

    # Para shaderpacks, primero buscar en staging (carpetas zipeadas)
    if category == "shaderpacks":
        staging_candidate = STAGING_DIR / version_key / filename
        if staging_candidate.exists():
            return staging_candidate
        # Si no está en staging, buscar en el perfil directamente
        profile_candidate = PROFILE_DIRS[version_key] / rel_path.replace("/", os.sep)
        if profile_candidate.exists():
            return profile_candidate
        return None

    # Para el resto, buscar en el perfil de Modrinth
    local = PROFILE_DIRS[version_key] / rel_path.replace("/", os.sep)
    return local if local.exists() else None

def upload_version(version_key: str, only_missing: bool = True):
    tag      = RELEASE_TAGS[version_key]
    token    = get_gh_token()

    session  = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })

    manifest = json.loads((MANIFESTS_DIR / f"{version_key}.json").read_text(encoding="utf-8"))
    release_files = [f for f in manifest["files"] if "releases/download" in f["url"]]
    total = len(release_files)

    print(f"\n=== {version_key.upper()} — {total} archivos — release: {tag} ===")

    # Obtener o crear la release
    release = get_or_create_release(session, GITHUB_OWNER, GITHUB_REPO, tag, version_key)
    upload_url_tpl = release["upload_url"]

    # Determinar qué ya está subido
    existing = get_existing_assets(session, release)
    print(f"    Assets ya en GitHub: {len(existing)}")

    errors = []
    skipped = 0
    uploaded = 0

    for i, entry in enumerate(release_files, 1):
        # El asset_name es el nombre del archivo (sin directorio)
        asset_name = unquote(Path(entry["url"]).name)

        if only_missing and asset_name in existing:
            skipped += 1
            continue

        local = find_local_file(entry, version_key)
        if not local:
            print(f"[{i}/{total}] SKIP (no encontrado): {entry['path']}")
            errors.append(asset_name)
            continue

        size_str = fmt_bytes(local.stat().st_size)
        print(f"[{i}/{total}] {asset_name} ({size_str})")

        # Borrar si ya existe (para re-subir)
        if asset_name in existing:
            for asset in release.get("assets", []):
                if asset["name"] == asset_name:
                    session.delete(f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/assets/{asset['id']}")
                    break

        ok = upload_asset(session, upload_url_tpl, local, asset_name)
        if ok:
            uploaded += 1
        else:
            errors.append(asset_name)

    print(f"\n  Resultado: {uploaded} subidos, {skipped} saltados, {len(errors)} errores")
    if errors:
        print(f"  Errores ({len(errors)}):")
        for e in errors:
            print(f"    - {e}")
    return len(errors) == 0


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("normal", "lite", "all"):
        print("Uso: python upload_release.py normal|lite|all [--only-missing]")
        sys.exit(1)

    target       = args[0]
    only_missing = "--only-missing" not in args  # por defecto solo sube los que faltan

    versions = ["normal", "lite"] if target == "all" else [target]

    ok = True
    for v in versions:
        ok = upload_version(v, only_missing=only_missing) and ok

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
