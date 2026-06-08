# CobbleverseMMO Launcher

Open-source launcher for the **CobbleverseMMO** Minecraft modpack (Fabric 1.21.1).

## Features

- Auto-update: downloads mods, configs, datapacks, resourcepacks and shaderpacks from GitHub Releases
- Two modpack variants: **NORMAL** (full quality) and **LITE** (potato-friendly)
- Microsoft (Premium) login via OAuth 2.0 + PKCE
- Offline (No-Premium) login
- Animated Space UI built with tkinter
- Skin preview and management
- Server online status indicator

## Requirements

- Python 3.10+
- Dependencies are auto-installed on first run, or manually:

```
pip install -r requirements.txt
```

## Usage

```
python launcher.py
```

## Azure App Registration

This launcher uses Microsoft OAuth for premium login.  
**Azure Application (client) ID:** `9807cd61-bf58-4245-b40c-b8ffeea785dd`  
**Supported account types:** Personal Microsoft accounts only  
**Redirect URI:** `http://localhost` (public client / mobile & desktop)

The app requests only the `XboxLive.signin offline_access` scopes needed to authenticate a Minecraft account. No data is stored on external servers — authentication tokens are kept locally.

## Project Structure

| File | Description |
|------|-------------|
| `launcher.py` | Main launcher GUI (player-facing) |
| `generate_manifest.py` | Admin tool: scans Modrinth profiles, generates JSON manifests |
| `upload_normal.ps1` / `upload_lite.ps1` | Upload mod binaries to GitHub Releases |
| `upload_release.py` | Helper for GitHub Release uploads |
| `launcher_config.json` | Config: GitHub repo, install directories |
| `requirements.txt` | Python dependencies |

## Server

- **IP:** cobbleversemmo.net
- **Discord:** https://discord.gg/atTNKrR8eb
- **TikTok:** https://www.tiktok.com/@cobbleversemmo.net

## License

MIT License — open source, free to use and modify.
