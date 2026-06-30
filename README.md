# CobbleverseMMO Launcher

Open-source launcher for the **CobbleverseMMO** Minecraft modpack (Fabric 1.21.1).

## Features

- Auto-update: downloads mods, configs, datapacks, resourcepacks and shaderpacks from GitHub Releases
- Two modpack variants: **NORMAL** (full quality) and **LITE** (potato-friendly)
- Microsoft (Premium) login via OAuth 2.0 + PKCE — persistent session + silent re-login
- Offline (No-Premium) login
- Modern UI (HTML/CSS/JS) rendered with **pywebview** (WebView2) — "Arceus Edition" design
- Real Minecraft skin rendering (head + body), custom `.png` upload
- News & events feed (read live from the modpack repo) and in-launcher settings
- Responsive window that fits any screen / DPI; self-installs WebView2 if missing

## Requirements

- **To run from source:** Python 3.10+ (dependencies auto-installed on first run, or `pip install -r requirements.txt`)
- **To use the built `.exe`:** nothing — it's self-contained (WebView2 auto-installs if absent)

## Run from source

```
python launcher.py
```

## Build the .exe (for distribution)

```
pip install pyinstaller
pyinstaller "CobbleverseMMO Launcher.spec"
```

The distributable is the whole `dist/CobbleverseMMO Launcher/` folder (zip it — keep the
`.exe` next to its `_internal` folder). Players don't need Python installed.

## Team / contributors

How to add mods, datapacks, resource packs (new Pokémon) and post news/events:
see **[GUIA-EQUIPO.md](GUIA-EQUIPO.md)**.

## Azure App Registration

This launcher uses Microsoft OAuth for premium login.  
**Azure Application (client) ID:** `9807cd61-bf58-4245-b40c-b8ffeea785dd`  
**Supported account types:** Personal Microsoft accounts only  
**Redirect URI:** `http://localhost` (public client / mobile & desktop)

The app requests only the `XboxLive.signin offline_access` scopes needed to authenticate a Minecraft account. No data is stored on external servers — authentication tokens are kept locally.

## Project Structure

| Path | Description |
|------|-------------|
| `launcher.py` | Main launcher + JS↔Python bridge (player-facing) |
| `web/` | UI: `launcher.html`, `launcher.js`, `steve.png` (default skin) |
| `Imagenes/` | App icon + corner icon + background logo |
| `app.ico` | Window/exe icon |
| `CobbleverseMMO Launcher.spec` | PyInstaller build config |
| `generate_manifest.py` | Admin tool: scans Modrinth profiles, generates JSON manifests |
| `upload_release.py` | Helper for GitHub Release uploads |
| `GUIA-EQUIPO.md` | Guide for contributors (mods, datapacks, news) |
| `requirements.txt` | Python dependencies |

## Server

- **IP:** cobbleversemmo.net
- **Discord:** https://discord.gg/atTNKrR8eb
- **TikTok:** https://www.tiktok.com/@cobbleversemmo.net

## License

MIT License — open source, free to use and modify.
