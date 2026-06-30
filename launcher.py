#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CobbleverseMMO Launcher — Arceus Edition (pywebview UI)."""

import base64, hashlib, json, os, shutil, subprocess, sys
import threading, uuid
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

NOWND = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

# When running as compiled exe all packages are already bundled — skip pip install
if not getattr(sys, "frozen", False):
    for pkg in ("requests", "minecraft_launcher_lib", "PIL", "webview"):
        try: __import__(pkg)
        except ImportError:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install",
                 "requests", "minecraft-launcher-lib", "Pillow", "pywebview"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=NOWND)
            break

import requests
import minecraft_launcher_lib
import webview
from PIL import Image

# ─────────────────────────────────────────────────────────────────────────────
APP_VERSION  = "1.0.0"
MC_VERSION   = "1.21.1"
APPDATA      = Path(os.environ.get("APPDATA", Path.home()))
BASE_DIR     = APPDATA / "CobbleverseMMO"
MC_DIR       = BASE_DIR / ".minecraft"
GITHUB_OWNER = "DropsIZI"
GITHUB_REPO  = "cobbleversemmo-modpack"
SERVER_HOST  = "cobbleversemmo.net"
SERVER_PORT  = 30270
NEWS_URL     = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/main/news.json"
# Registro local de archivos que el launcher instaló (para borrar los que se
# quiten del modpack sin tocar lo que el jugador añadió por su cuenta).
MANAGED_FILE = ".cobbleverse_managed.json"

LAUNCHER_DIR = (Path(sys.executable).parent
                if getattr(sys, "frozen", False)
                else Path(__file__).parent)

WIN_W, WIN_H = 1280, 720

VERSIONS_CFG = {
    "normal": {
        "name":     "CobbleverseMMO",
        "tag":      "NORMAL",
        "manifest": f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/main/manifests/normal.json",
        "game_dir": str(BASE_DIR / "normal"),
    },
    "lite": {
        "name":     "POTATOVERSEMMO",
        "tag":      "LITE",
        "manifest": f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/main/manifests/lite.json",
        "game_dir": str(BASE_DIR / "lite"),
    },
}

# Order + display metadata for the version dropdown
VERSIONS = [
    {"key": "normal", "label": "CobbleverseMMO Normal",
     "sub": "Experiencia completa · 6 GB", "ram": 6},
    {"key": "lite",   "label": "CobbleverseMMO Lite",
     "sub": "Optimizado para PCs modestos · 4 GB", "ram": 4},
]

# Fallback news shown if news.json can't be fetched.
FALLBACK_NEWS = [
    {"tag": "BIENVENIDA", "date": "", "title": "¡Bienvenido a CobbleverseMMO!",
     "text": "Inicia sesión, elige tu modpack y pulsa JUGAR. El launcher mantiene tus mods siempre actualizados.",
     "body": ["Inicia sesión con tu cuenta Microsoft (Premium) o entra en modo offline con un nombre de usuario.",
              "Elige entre la versión Normal (experiencia completa) o Lite (optimizada). El botón JUGAR verifica y descarga automáticamente los mods que falten.",
              "Únete a nuestro Discord para enterarte de eventos, torneos y novedades del servidor."]},
]

CFG_FILE = BASE_DIR / "launcher.json"
# Azure Application (client) ID — se lee de ms_config.py (privado, no en GitHub).
# Si no existe, el login premium queda deshabilitado (offline sigue funcionando).
try:
    from ms_config import MS_CLIENT_ID
except Exception:
    MS_CLIENT_ID = ""

# Página que ve el usuario en el navegador tras iniciar sesión con Microsoft.
_LOGIN_DONE_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>CobbleverseMMO</title></head>
<body style="margin:0;background:#04060d;color:#f4d77a;font-family:system-ui,sans-serif;
display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;text-align:center">
<h1 style="margin:0 0 10px">✓ Sesión iniciada</h1>
<p style="color:#bdbdbd">Ya puedes cerrar esta pestaña y volver al launcher de CobbleverseMMO.</p>
</body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────────────────────────────────────
def load_cfg():
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    if CFG_FILE.exists():
        try: return json.loads(CFG_FILE.read_text(encoding="utf-8"))
        except: pass
    return {"version": "normal", "auth": "offline", "username": ""}

def save_cfg(c):
    CFG_FILE.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")


def find_web_dir():
    """Locate the web/ folder both in dev and in a PyInstaller bundle."""
    cands = []
    if getattr(sys, "frozen", False):
        cands.append(Path(getattr(sys, "_MEIPASS", "")) / "web")
    cands += [LAUNCHER_DIR / "web", Path(__file__).parent / "web"]
    for d in cands:
        if (d / "launcher.html").exists():
            return d
    return LAUNCHER_DIR / "web"

def find_assets_dir():
    """Locate the Imagenes/ folder (icons + logo) in dev and in a bundle."""
    cands = []
    if getattr(sys, "frozen", False):
        cands.append(Path(getattr(sys, "_MEIPASS", "")) / "Imagenes")
    cands += [LAUNCHER_DIR / "Imagenes", Path(__file__).parent / "Imagenes"]
    for d in cands:
        if d.is_dir():
            return d
    return LAUNCHER_DIR / "Imagenes"

def stage_web_assets():
    """Copy the icon/logo into web/ so the page can load them as same-origin
    relative URLs (cross-directory file:// references don't load in WebView2)."""
    web = find_web_dir()
    out = {}
    for key, name in (("cornerIcon", "Icono.png"), ("logo", "LOGO.png")):
        src = find_assets_dir() / name
        dst = web / name
        try:
            if src.exists():
                if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
                    shutil.copyfile(src, dst)
            if dst.exists():
                out[key] = name  # relative to launcher.html
        except Exception:
            pass
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  Skins — render head (top bar) + body figure (Tu Aspecto) from a MC texture
# ─────────────────────────────────────────────────────────────────────────────
def _steve_image():
    """Default 64×64 Steve texture (bundled in web/) for offline / non-premium."""
    p = find_web_dir() / "steve.png"
    if p.exists():
        return Image.open(p).convert("RGBA")
    # last-resort: a flat 64×64 so rendering never crashes
    return Image.new("RGBA", (64, 64), (140, 110, 90, 255))

def _fetch_skin_texture(creds):
    """Download a premium player's real skin from the Mojang session server."""
    try:
        uid = (creds or {}).get("uuid", "").replace("-", "")
        if not uid:
            return None
        r = requests.get(
            f"https://sessionserver.mojang.com/session/minecraft/profile/{uid}",
            timeout=8)
        if not r.ok:
            return None
        for prop in r.json().get("properties", []):
            if prop.get("name") == "textures":
                dec = json.loads(base64.b64decode(prop["value"]).decode())
                url = dec.get("textures", {}).get("SKIN", {}).get("url")
                if url:
                    rr = requests.get(url, timeout=8)
                    if rr.ok:
                        return Image.open(BytesIO(rr.content)).convert("RGBA")
    except Exception:
        pass
    return None

def _datauri(im):
    buf = BytesIO(); im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

def render_skin_head(tex, scale=8):
    """Front face + hat overlay → square PNG."""
    head = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    head.alpha_composite(tex.crop((8, 8, 16, 16)))
    head.alpha_composite(tex.crop((40, 8, 48, 16)))
    return head.resize((8 * scale, 8 * scale), Image.NEAREST)

def render_skin_body(tex, scale=11):
    """Compose a 2-D front-facing figure (head+body+arms+legs) → PNG."""
    legacy = tex.height < 64
    def c(x, y, w, h): return tex.crop((x, y, x + w, y + h))
    head = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    head.alpha_composite(c(8, 8, 8, 8)); head.alpha_composite(c(40, 8, 8, 8))
    body  = c(20, 20, 8, 12)
    r_arm = c(44, 20, 4, 12)
    r_leg = c(4, 20, 4, 12)
    l_arm = r_arm.transpose(Image.FLIP_LEFT_RIGHT) if legacy else c(36, 52, 4, 12)
    l_leg = r_leg.transpose(Image.FLIP_LEFT_RIGHT) if legacy else c(20, 52, 4, 12)
    canvas = Image.new("RGBA", (16, 32), (0, 0, 0, 0))
    canvas.alpha_composite(head,  (4, 0))
    canvas.alpha_composite(r_arm, (0, 8))
    canvas.alpha_composite(body,  (4, 8))
    canvas.alpha_composite(l_arm, (12, 8))
    canvas.alpha_composite(r_leg, (4, 20))
    canvas.alpha_composite(l_leg, (8, 20))
    return canvas.resize((16 * scale, 32 * scale), Image.NEAREST)


# ─────────────────────────────────────────────────────────────────────────────
#  Descargas
# ─────────────────────────────────────────────────────────────────────────────
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(65536), b""): h.update(c)
    return h.hexdigest()

def fetch_manifest(url):
    r = requests.get(url, timeout=30); r.raise_for_status(); return r.json()

def fetch_extra_files(version):
    """Archivos propios del equipo para esta versión (extra-normal.json /
    extra-lite.json). API primero (sin caché → al instante) y raw de respaldo."""
    path = f"manifests/extra-{version}.json"
    api = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
    raw = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/main/{path}"
    for url, hdr in ((api, {"Accept": "application/vnd.github.raw+json",
                            "User-Agent": "CobbleverseMMO-Launcher"}),
                     (raw, {})):
        try:
            r = requests.get(url, headers=hdr, timeout=15)
            r.raise_for_status()
            data = r.json()
            files = data.get("files", []) if isinstance(data, dict) else []
            if isinstance(files, list):
                return files
        except Exception:
            continue
    return []

def apply_removals(manifest, game_dir):
    """Borra del juego los archivos que el launcher instaló antes y que ya NO
    están en el modpack (un mod retirado). No toca lo que el jugador añadió por
    su cuenta, porque eso nunca estuvo en la lista de archivos gestionados."""
    mf = game_dir / MANAGED_FILE
    current = {e["path"] for e in manifest.get("files", []) if e.get("path")}
    try:
        old = set(json.loads(mf.read_text(encoding="utf-8")))
    except Exception:
        old = set()
    removed = []
    for path in (old - current):
        p = game_dir / path
        try:
            if p.is_file():
                p.unlink(); removed.append(path)
        except Exception:
            pass
    try:
        mf.write_text(json.dumps(sorted(current), ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return removed

def pending_files(manifest, game_dir):
    out = []
    for e in manifest.get("files", []):
        p = game_dir / e["path"]
        if not p.exists() or (e.get("sha256") and sha256(p) != e["sha256"]):
            out.append(e)
    return out

def dl_one(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(65536): f.write(chunk)

def dl_parallel(files, game_dir, on_prog, on_log, cancel_ev=None, workers=16):
    total = len(files); done = 0; errors = []; lock = threading.Lock()
    def _t(e):
        nonlocal done
        if cancel_ev and cancel_ev.is_set():
            with lock: done += 1; on_prog(done / total * 100)
            return
        try:
            dl_one(e["url"], game_dir / e["path"])
            with lock: done += 1; on_prog(done / total * 100); on_log(f"  + {e['path']}")
        except Exception as ex:
            with lock: done += 1; on_prog(done / total * 100); errors.append((e["path"], str(ex)))
    with ThreadPoolExecutor(max_workers=workers) as ex: list(ex.map(_t, files))
    return errors

def fmt_bytes(b):
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} GB"


# ─────────────────────────────────────────────────────────────────────────────
#  Auth / MC
# ─────────────────────────────────────────────────────────────────────────────
def offline_creds(username):
    return {"username": username, "uuid": str(uuid.uuid3(uuid.NAMESPACE_DNS, username)),
            "token": "0", "user_type": "legacy"}

def vanilla_auth():
    try:
        f = APPDATA / ".minecraft" / "launcher_accounts.json"
        if not f.exists(): return None
        data = json.loads(f.read_text(encoding="utf-8"))
        aid = data.get("activeAccountLocalId")
        if not aid: return None
        acc = data.get("accounts", {}).get(aid, {})
        mc = acc.get("minecraftProfile", {})
        return {"username": mc.get("name", "Player"), "uuid": mc.get("id", str(uuid.uuid4())),
                "token": acc.get("accessToken", ""), "user_type": "msa"}
    except: return None

def latest_fabric():
    try:
        vers = minecraft_launcher_lib.fabric.get_all_loader_versions()
        for v in vers:
            if v.get("stable"): return v["version"]
        return vers[0]["version"]
    except: return "0.16.14"

def find_java():
    for p in [MC_DIR / "runtime" / "java-runtime-delta" / "windows" / "java-runtime-delta" / "bin" / "java.exe",
              MC_DIR / "runtime" / "java-runtime-delta" / "windows-x64" / "java-runtime-delta" / "bin" / "java.exe"]:
        if p.exists(): return str(p)
    try:
        subprocess.run(["java", "-version"], capture_output=True, timeout=3, creationflags=NOWND)
        return "java"
    except: return None


def _ms_chain(ms_token, on_step, step_start=2):
    """XBL → XSTS → MC token → perfil. Devuelve creds dict."""
    from minecraft_launcher_lib.microsoft_account import (
        authenticate_with_xbl, authenticate_with_xsts,
        authenticate_with_minecraft, get_profile,
    )
    on_step(step_start, 5, "Autenticando con Xbox Live...")
    xbl = authenticate_with_xbl(ms_token)
    if "Token" not in xbl:
        raise ValueError(f"[XBL] XErr={xbl.get('XErr','')}: {xbl.get('Message', str(xbl)[:150])}")
    uhs = xbl["DisplayClaims"]["xui"][0]["uhs"]

    on_step(step_start + 1, 5, "Verificando XSTS...")
    xsts = authenticate_with_xsts(xbl["Token"])
    if "Token" not in xsts:
        raise ValueError(f"[XSTS] XErr={xsts.get('XErr','')}: {xsts.get('Message', str(xsts)[:150])}")

    on_step(step_start + 2, 5, "Obteniendo token de Minecraft...")
    mc = authenticate_with_minecraft(uhs, xsts["Token"])
    if "access_token" not in mc:
        raise ValueError(f"[MC Auth] {str(mc)[:200]}")
    mc_token = mc["access_token"]

    on_step(min(step_start + 3, 5), 5, "Obteniendo perfil...")
    try:
        profile = get_profile(mc_token)
        name = profile.get("name", "Player")
        uid  = profile.get("id", str(uuid.uuid4()))
    except Exception:
        name = xbl.get("DisplayClaims", {}).get("xui", [{}])[0].get("gtg", "Player")
        uid  = str(uuid.uuid4())

    return {"username": name, "uuid": uid, "token": mc_token, "user_type": "msa"}


def ms_manual_auth(client_id, redirect, code_ver, auth_code, on_step):
    """Cadena completa OAuth→XBL→XSTS→MC. Devuelve (creds, refresh_token)."""
    from minecraft_launcher_lib.microsoft_account import get_authorization_token
    on_step(1, 5, "Obteniendo token OAuth...")
    token_data = get_authorization_token(client_id, None, redirect, auth_code, code_ver)
    if "access_token" not in token_data:
        err = token_data.get("error_description") or token_data.get("error", "Token error")
        raise ValueError(f"[OAuth] {err}")
    creds = _ms_chain(token_data["access_token"], on_step, step_start=2)
    return creds, token_data.get("refresh_token", "")


def ms_refresh_auth(client_id, refresh_token, on_step):
    """Renueva sesión con refresh_token sin interacción del usuario."""
    on_step(1, 5, "Renovando sesión...")
    resp = requests.post(
        "https://login.live.com/oauth20_token.srf",
        data={"client_id": client_id, "refresh_token": refresh_token,
              "grant_type": "refresh_token", "scope": "XboxLive.signin offline_access"},
        timeout=20)
    resp.raise_for_status()
    token_data = resp.json()
    if "access_token" not in token_data:
        raise ValueError(token_data.get("error_description", "Refresh failed"))
    creds = _ms_chain(token_data["access_token"], on_step, step_start=2)
    return creds, token_data.get("refresh_token", refresh_token)


# ─────────────────────────────────────────────────────────────────────────────
#  JS API bridge
# ─────────────────────────────────────────────────────────────────────────────
class Api:
    def __init__(self):
        self._window = None
        self.cfg = load_cfg()
        self.auth = None
        self.username = ""
        self.ms_creds = None
        self.ver = self.cfg.get("version", "normal")
        if self.ver not in VERSIONS_CFG:
            self.ver = "normal"
        _def_ram = next((v["ram"] for v in VERSIONS if v["key"] == self.ver), 6)
        self.ram = int(self.cfg.get("ram", _def_ram))
        self.ready = False
        self.playing = False
        self._mc_proc = None
        self._ldata = None
        self._cancel_ev = threading.Event()
        self._thread = None

    # ── helpers ───────────────────────────────────────────────────────────────
    def _ver_index(self):
        for i, v in enumerate(VERSIONS):
            if v["key"] == self.ver: return i
        return 0

    def _emit(self, fn, *args):
        if not self._window: return
        try:
            payload = ",".join(json.dumps(a, ensure_ascii=False) for a in args)
            self._window.evaluate_js(f"window.cv && cv.{fn}({payload})")
        except Exception:
            pass

    def _progress(self, pct, label=None):
        self._emit("setProgress", pct, label)

    # ── bootstrap ─────────────────────────────────────────────────────────────
    def get_initial(self):
        assets = stage_web_assets()
        data = {
            "appVersion": APP_VERSION,
            "logo": assets.get("logo"),
            "cornerIcon": assets.get("cornerIcon"),
            "versions": [{"label": v["label"], "sub": v["sub"], "ram": v["ram"]} for v in VERSIONS],
            "versionIndex": self._ver_index(),
            "ram": self.ram,
            "loggedIn": False,
            "premium": False,
            "username": "",
            "ready": False,
            "news": FALLBACK_NEWS,
            "java": find_java() or "",
            "installDir": VERSIONS_CFG[self.ver]["game_dir"],
        }
        return data

    def start_background(self):
        """Kick off news + silent re-login once the UI has initialised.
        Guarded so repeated calls (boot retries) only run it once."""
        if getattr(self, "_bg_started", False):
            return True
        self._bg_started = True
        threading.Thread(target=self._load_news, daemon=True).start()
        threading.Thread(target=self._try_autologin, daemon=True).start()
        return True

    def _load_news(self):
        # Try the GitHub API first (no CDN cache → noticias al instante para el
        # equipo), then the raw CDN (~5 min de caché) como respaldo.
        api_url = (f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
                   "/contents/news.json")
        sources = [
            (api_url, {"Accept": "application/vnd.github.raw+json",
                       "User-Agent": "CobbleverseMMO-Launcher"}),
            (NEWS_URL, {}),
        ]
        for url, headers in sources:
            try:
                r = requests.get(url, headers=headers, timeout=10)
                r.raise_for_status()
                payload = r.json()
                news = payload.get("news", payload) if isinstance(payload, dict) else payload
                if isinstance(news, list) and news:
                    self._emit("onNews", news)
                    return
            except Exception:
                continue  # prueba la siguiente fuente; si todas fallan, queda el fallback

    def _try_autologin(self):
        token = self.cfg.get("ms_refresh_token", "")
        if not token:
            return
        try:
            def step(n, t, msg): pass
            creds, new_refresh = ms_refresh_auth(MS_CLIENT_ID, token, step)
            self.cfg["ms_refresh_token"] = new_refresh
            save_cfg(self.cfg)
            self._set_logged_in("premium", creds["username"], creds)
        except Exception:
            self.cfg.pop("ms_refresh_token", None)
            save_cfg(self.cfg)

    def _set_logged_in(self, auth, username, ms_creds=None):
        self.auth = auth
        self.username = username
        self.ms_creds = ms_creds
        self.ready = False
        self.cfg.update({"auth": auth, "username": username})
        save_cfg(self.cfg)
        self._emit("onLogin", {"loggedIn": True, "premium": auth == "premium",
                               "username": username, "ram": self.ram})
        self._emit_skin()

    def _emit_skin(self):
        threading.Thread(target=self._render_skin_worker, daemon=True).start()

    def _render_skin_worker(self):
        """Pick the skin texture (uploaded > premium real > Steve) and push the
        rendered head + body to the UI as small PNG data URIs."""
        tex = None
        try:
            up = Path(VERSIONS_CFG[self.ver]["game_dir"]) / "skin.png"
            if up.exists():
                tex = Image.open(up).convert("RGBA")
        except Exception:
            tex = None
        source = "custom" if tex is not None else "steve"
        if tex is None and self.auth == "premium":
            real = _fetch_skin_texture(self.ms_creds)
            if real is not None:
                tex, source = real, "premium"
        if tex is None:
            tex = _steve_image()
        try:
            self._emit("onSkin", {
                "head": _datauri(render_skin_head(tex, 9)),
                "body": _datauri(render_skin_body(tex, 12)),
                "source": source,
            })
        except Exception:
            pass

    # ── login ─────────────────────────────────────────────────────────────────
    def login_offline(self, username):
        username = (username or "").strip()[:16] or "Jugador"
        self._set_logged_in("offline", username, None)
        return True

    def login_premium(self):
        if getattr(self, "_ms_busy", False):
            return False
        self._ms_busy = True
        threading.Thread(target=self._premium_worker, daemon=True).start()
        return True

    def _premium_worker(self):
        """Login con Microsoft usando el NAVEGADOR del sistema + un mini-servidor
        local que captura la redirección. Evita la ventana embebida (webview), que
        Microsoft bloquea con 'There was an issue looking up your account'."""
        import http.server, webbrowser, time
        from minecraft_launcher_lib.microsoft_account import (
            get_secure_login_data, parse_auth_code_url)
        captured = {"url": None}
        httpd = None
        try:
            try:
                class _H(http.server.BaseHTTPRequestHandler):
                    def do_GET(s):
                        captured["url"] = f"http://localhost:{port}{s.path}"
                        s.send_response(200)
                        s.send_header("Content-Type", "text/html; charset=utf-8")
                        s.end_headers()
                        s.wfile.write(_LOGIN_DONE_HTML.encode("utf-8"))
                    def log_message(s, *a): pass
                httpd = http.server.HTTPServer(("127.0.0.1", 0), _H)
                port = httpd.server_address[1]
                redirect = f"http://localhost:{port}"
                url, state, code_ver = get_secure_login_data(MS_CLIENT_ID, redirect)
                # forzar el selector "Elige una cuenta" (por si hay varias / PC compartido)
                if "prompt=" not in url:
                    url += ("&" if "?" in url else "?") + "prompt=select_account"
            except Exception as e:
                self._emit("onMsStatus", f"Error: {str(e)[:120]}", False)
                return

            httpd.timeout = 1
            webbrowser.open(url)
            self._emit("onMsStatus", "Inicia sesión en el navegador que se abrió y vuelve aquí…", True)
            deadline = time.time() + 300
            while captured["url"] is None and time.time() < deadline:
                httpd.handle_request()  # bloquea ≤1s por iteración
            if not captured["url"]:
                self._emit("onMsStatus", "Login cancelado o expirado.", False)
                return

            self._emit("onMsStatus", "Verificando cuenta...", True)
            try:
                auth_code = parse_auth_code_url(captured["url"], state)
                def step(n, t, msg): self._emit("onMsStatus", f"Paso {n}/{t}: {msg}", True)
                creds, refresh = ms_manual_auth(MS_CLIENT_ID, redirect, code_ver, auth_code, step)
                self.cfg["ms_refresh_token"] = refresh
                save_cfg(self.cfg)
                self._set_logged_in("premium", creds["username"], creds)
            except Exception as e:
                self._emit("onMsStatus", f"Error: {type(e).__name__}: {str(e)[:140]}", False)
        finally:
            if httpd:
                try: httpd.server_close()
                except Exception: pass
            self._ms_busy = False

    def logout(self):
        self.auth = None; self.username = ""; self.ms_creds = None
        self.ready = False; self._ldata = None
        self.cfg.pop("ms_refresh_token", None)
        save_cfg(self.cfg)
        return True

    # ── version / RAM / settings ──────────────────────────────────────────────
    def set_version(self, index):
        try: index = int(index)
        except Exception: index = 0
        index = max(0, min(len(VERSIONS) - 1, index))
        self.ver = VERSIONS[index]["key"]
        self.ram = VERSIONS[index]["ram"]
        self.ready = False; self._ldata = None
        self.cfg.update({"version": self.ver, "ram": self.ram})
        save_cfg(self.cfg)
        self._emit("onJava", find_java() or "")
        if self.auth:
            self._emit_skin()  # skin.png is per game_dir
        return {"ram": self.ram, "installDir": VERSIONS_CFG[self.ver]["game_dir"]}

    def set_ram(self, gb):
        try: self.ram = max(1, min(32, int(gb)))
        except Exception: pass
        self.cfg["ram"] = self.ram
        save_cfg(self.cfg)
        return self.ram

    def browse_java(self):
        if not self._window: return ""
        try:
            res = self._window.create_file_dialog(
                webview.OPEN_DIALOG, allow_multiple=False,
                file_types=("Java ejecutable (*.exe)", "Todos los archivos (*.*)"))
            if res:
                path = res[0] if isinstance(res, (list, tuple)) else res
                self.cfg["java_path"] = path; save_cfg(self.cfg)
                return path
        except Exception:
            pass
        return ""

    def _open_game_subfolder(self, *parts):
        d = Path(VERSIONS_CFG[self.ver]["game_dir"]).joinpath(*parts)
        d.mkdir(parents=True, exist_ok=True)
        try: os.startfile(str(d))
        except Exception: pass
        return str(d)

    def open_install(self):
        return self._open_game_subfolder()

    def open_mods(self):
        return self._open_game_subfolder("mods")

    def open_shaders(self):
        return self._open_game_subfolder("shaderpacks")

    # ── skin upload ───────────────────────────────────────────────────────────
    def upload_skin(self):
        if not self._window: return ""
        try:
            res = self._window.create_file_dialog(
                webview.OPEN_DIALOG, allow_multiple=False,
                file_types=("Skin PNG (*.png)",))
            if not res:
                return "Subida cancelada."
            src = res[0] if isinstance(res, (list, tuple)) else res
            dest_dir = Path(VERSIONS_CFG[self.ver]["game_dir"])
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest_dir / "skin.png")
            self._emit_skin()  # re-render the figure with the new skin
            return f"Skin aplicada: {Path(src).name}"
        except Exception as e:
            return f"Error: {str(e)[:80]}"

    # ── links / window ────────────────────────────────────────────────────────
    def open_url(self, kind):
        import webbrowser
        urls = {
            "discord": "https://discord.gg/atTNKrR8eb",
            "store":   "https://cobbleversemmo.tebex.io",
            "web":     "https://cobbleversemmo.net",
            "tiktok":  "https://www.tiktok.com/@cobbleversemmo.net",
        }
        if kind in urls:
            webbrowser.open(urls[kind])
        return True

    def minimize(self):
        try: self._window.minimize()
        except Exception: pass

    def close_app(self):
        try:
            if self._mc_proc and self._mc_proc.poll() is None:
                pass  # leave MC running
            self._window.destroy()
        except Exception:
            os._exit(0)

    # ── play / sync ───────────────────────────────────────────────────────────
    def play(self):
        if self.playing:
            return False
        if self._thread and self._thread.is_alive():
            return False
        if not self.auth:
            self._emit("showLogin")
            return False
        self.playing = True
        self._cancel_ev.clear()
        self._emit("onPlaying", True)
        if self.ready and self._ldata:
            self._progress(100, "Iniciando Minecraft...")
            self._launch()
        else:
            self._progress(0, "Preparando...")
            self._thread = threading.Thread(target=self._worker, daemon=True)
            self._thread.start()
        return True

    def cancel_play(self):
        """Cancela la descarga en curso y/o cierra el Minecraft que se está iniciando."""
        self._cancel_ev.set()
        p = self._mc_proc
        if p and p.poll() is None:
            try: p.terminate()
            except Exception: pass
            try: p.wait(timeout=3)
            except Exception:
                try: p.kill()
                except Exception: pass
        self._mc_proc = None
        self.playing = False
        self._emit("onPlaying", False)
        self._progress(100 if self.ready else 0,
                       "Minecraft cancelado." if self.ready else "Cancelado.")
        return True

    def _worker(self):
        try:
            ver_cfg = VERSIONS_CFG[self.ver]
            game_dir = Path(ver_cfg["game_dir"]); game_dir.mkdir(parents=True, exist_ok=True)

            # 1. Modpack (base de Modrinth + contenido propio del equipo en extra/)
            self._progress(2, "Verificando archivos...")
            try:
                manifest = fetch_manifest(ver_cfg["manifest"])
            except Exception as e:
                self._fail(f"Error de red: {str(e)[:80]}"); return
            manifest.setdefault("files", [])
            manifest["files"] += fetch_extra_files(self.ver)   # best-effort; [] si no hay

            pending = pending_files(manifest, game_dir)
            if pending:
                sz = fmt_bytes(sum(e.get("size", 0) for e in pending))
                self._progress(5, f"Descargando {len(pending)} archivos ({sz})...")
                dl_parallel(pending, game_dir,
                            on_prog=lambda p: self._progress(5 + p * 0.30, None),
                            on_log=lambda m: None,
                            cancel_ev=self._cancel_ev, workers=16)
                if self._cancel_ev.is_set():
                    self._fail("Cancelado."); return
            # borrar mods/archivos retirados del modpack (no toca lo del jugador)
            removed = apply_removals(manifest, game_dir)
            if removed:
                self._progress(34, f"Eliminados {len(removed)} archivo(s) retirado(s) del modpack")
            self._progress(35, "Verificando Minecraft...")

            # 2. Minecraft
            inst = [v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(str(MC_DIR))]
            if MC_VERSION not in inst:
                minecraft_launcher_lib.install.install_minecraft_version(
                    version=MC_VERSION, minecraft_directory=str(MC_DIR),
                    callback={"setStatus": lambda s: self._progress(45, f"Minecraft: {s}"),
                              "setProgress": lambda v: None, "setMax": lambda v: None})
            self._progress(60, "Instalando Fabric...")

            # 3. Fabric
            loader = latest_fabric(); fab_id = f"fabric-loader-{loader}-{MC_VERSION}"
            inst2 = [v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(str(MC_DIR))]
            if fab_id not in inst2:
                minecraft_launcher_lib.fabric.install_fabric(
                    minecraft_version=MC_VERSION, minecraft_directory=str(MC_DIR),
                    loader_version=loader,
                    callback={"setStatus": lambda s: self._progress(70, f"Fabric: {s}"),
                              "setProgress": lambda v: None, "setMax": lambda v: None})
            self._progress(80, "Comprobando Java...")

            # 4. Java
            java = self.cfg.get("java_path") or find_java()
            if not java:
                self._progress(85, "Instalando Java 21...")
                minecraft_launcher_lib.runtime.install_jvm_runtime(
                    jvm_version="java-runtime-delta", minecraft_directory=str(MC_DIR),
                    callback={"setStatus": lambda s: self._progress(90, f"Java: {s}"),
                              "setProgress": lambda v: None, "setMax": lambda v: None})
                java = find_java() or "java"
            self._emit("onJava", java)

            # 5. Auth
            if self.auth == "premium" and self.ms_creds:
                creds = self.ms_creds
            elif self.auth == "premium":
                creds = vanilla_auth() or offline_creds(self.username or "Jugador")
            else:
                creds = offline_creds(self.username or "Jugador")

            self._ldata = {"fab_id": fab_id, "game_dir": str(game_dir), "java": java, "creds": creds}
            self.ready = True
            self._emit("onReady")
            if self._cancel_ev.is_set():
                self._fail("Cancelado.", reset_ready=False); return
            self._launch()
        except Exception as ex:
            self._fail(f"Error: {str(ex)[:100]}")

    def _fail(self, msg, reset_ready=True):
        self.playing = False
        if reset_ready:
            self.ready = False
        self._mc_proc = None
        self._emit("onPlaying", False)
        self._progress(0, msg)

    def _launch(self):
        if not self._ldata:
            return
        d = self._ldata
        try:
            opts = {
                "username": d["creds"]["username"],
                "uuid":     d["creds"]["uuid"],
                "token":    d["creds"]["token"],
                "userType": d["creds"].get("user_type", "legacy"),
                "gameDirectory": d["game_dir"],
                "jvmArguments": [f"-Xmx{self.ram}G", "-Xms1G", "-XX:+UseG1GC",
                                 "-XX:+ParallelRefProcEnabled"],
                "executablePath": d["java"],
                "launcherName": "CobbleverseMMO",
                "launcherVersion": APP_VERSION,
            }
            cmd = minecraft_launcher_lib.command.get_minecraft_command(
                version=d["fab_id"], minecraft_directory=str(MC_DIR), options=opts)
            if self._cancel_ev.is_set():
                return
            self._progress(100, "▶ Lanzando Minecraft...")
            proc = subprocess.Popen(cmd, cwd=d["game_dir"], creationflags=NOWND)
            self._mc_proc = proc
            self._progress(100, "Minecraft iniciándose… (pulsa CANCELAR para detenerlo)")
            threading.Thread(target=self._watch_mc, args=(proc,), daemon=True).start()
        except Exception as ex:
            self._fail(f"Error al lanzar: {str(ex)[:100]}")

    def _watch_mc(self, proc):
        """Espera a que Minecraft termine y devuelve el botón a JUGAR."""
        try: proc.wait()
        except Exception: pass
        if self._mc_proc is proc:           # sigue siendo el proceso actual
            self._mc_proc = None
            self.playing = False
            if not self._cancel_ev.is_set():  # cierre normal (no cancelado)
                self._emit("onPlaying", False)
                self._progress(100, "Minecraft cerrado. ¡Listo para volver a jugar!")


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────
def _work_area():
    """Desktop work area (screen minus the taskbar), so the frameless window
    never gets clipped behind the taskbar on smaller / scaled displays."""
    try:
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)  # SPI_GETWORKAREA
        return r.left, r.top, r.right - r.left, r.bottom - r.top
    except Exception:
        return 0, 0, WIN_W, WIN_H

def webview2_available():
    """True if the Edge WebView2 runtime is installed (required to render the UI)."""
    if os.name != "nt":
        return True
    import winreg
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
        (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
    ]
    for root, path in keys:
        try:
            with winreg.OpenKey(root, path) as k:
                pv, _ = winreg.QueryValueEx(k, "pv")
                if pv and pv not in ("", "0.0.0.0"):
                    return True
        except OSError:
            continue
    return False

def ensure_webview2():
    """Offer to install the WebView2 runtime if it's missing (no admin needed)."""
    if webview2_available():
        return True
    import ctypes
    msg = ("Este launcher necesita el componente 'Microsoft Edge WebView2'.\n\n"
           "¿Quieres descargarlo e instalarlo ahora? (no requiere permisos de administrador)")
    if ctypes.windll.user32.MessageBoxW(0, msg, "CobbleverseMMO Launcher", 0x4 | 0x20) != 6:  # MB_YESNO|ICON?
        return False
    try:
        boot = Path(os.environ.get("TEMP", ".")) / "MicrosoftEdgeWebview2Setup.exe"
        with requests.get("https://go.microsoft.com/fwlink/p/?LinkId=2124703",
                          stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(boot, "wb") as f:
                for chunk in r.iter_content(65536): f.write(chunk)
        subprocess.run([str(boot), "/silent", "/install"], creationflags=NOWND, timeout=600)
        return webview2_available()
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(
            0, f"No se pudo instalar WebView2 automáticamente.\n\nDescárgalo manualmente desde:\n"
               f"https://go.microsoft.com/fwlink/p/?LinkId=2124703\n\n{str(e)[:120]}",
            "CobbleverseMMO Launcher", 0x10)
        return False

def main():
    api = Api()
    web_dir = find_web_dir()
    html_path = str(web_dir / "launcher.html")

    wx, wy, ww, wh = _work_area()
    margin = 8
    win_w = max(900, min(WIN_W, ww - margin))
    win_h = max(560, min(WIN_H, wh - margin))
    x = wx + max(0, (ww - win_w) // 2)
    y = wy + max(0, (wh - win_h) // 2)

    window = webview.create_window(
        "CobbleverseMMO Launcher",
        url=html_path,
        js_api=api,
        width=win_w, height=win_h, x=x, y=y,
        resizable=False, frameless=True, easy_drag=False,
        background_color="#04060d",
    )
    api._window = window
    webview.start(gui="edgechromium")


if __name__ == "__main__":
    if os.name == "nt":
        import ctypes
        _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "CobbleverseMMO_Launcher_Mutex")
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            ctypes.windll.user32.MessageBoxW(0, "El launcher ya está abierto.",
                                             "CobbleverseMMO Launcher", 0x40)
            sys.exit(0)
        if not ensure_webview2():
            sys.exit(0)
    main()
