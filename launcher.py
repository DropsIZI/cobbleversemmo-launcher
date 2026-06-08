#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CobbleverseMMO Launcher — Space Edition v2"""

import base64, hashlib, http.server, json, math, os, random, socket, subprocess, sys
import threading, tkinter as tk, urllib.parse, uuid
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from tkinter import messagebox, filedialog

NOWND = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

for pkg in ("requests", "minecraft_launcher_lib", "PIL", "webview"):
    try: __import__("PIL" if pkg == "PIL" else pkg)
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install",
             "requests", "minecraft-launcher-lib", "Pillow", "pywebview"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=NOWND)
        break

import requests
import minecraft_launcher_lib
from PIL import Image, ImageTk, ImageEnhance, ImageFilter, ImageDraw

# ─────────────────────────────────────────────────────────────────────────────
APP_VERSION  = "1.0.0"
MC_VERSION   = "1.21.1"
APPDATA      = Path(os.environ.get("APPDATA", Path.home()))
BASE_DIR     = APPDATA / "CobbleverseMMO"
MC_DIR       = BASE_DIR / ".minecraft"
GITHUB_OWNER = "DropsIZI"
GITHUB_REPO  = "cobbleversemmo-modpack"
SERVER_HOST  = "cobbleversemmo.net"
SERVER_PORT  = 25565
LAUNCHER_DIR = (Path(sys.executable).parent
                if getattr(sys, "frozen", False)
                else Path(__file__).parent)

W, H = 960, 580

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

CFG_FILE = BASE_DIR / "launcher.json"

GOLD        = "#f5c518"
GOLD2       = "#ffd700"
GOLD_DIM    = "#7a6008"
TEAL        = "#00e5aa"
TEAL_DIM    = "#006644"
GREEN_PX    = "#5cff00"
DARK_BG     = "#06080f"
DARK_CARD   = "#0b1220"
TEXT_W      = "#e0e8f0"
TEXT_DIM    = "#5a7090"
BLACK       = "#000000"

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

def find_bg():
    for d in [LAUNCHER_DIR/"Imagen fondo del Launcher",
               LAUNCHER_DIR/"imagen de Fondo Launcher",
               LAUNCHER_DIR]:
        if not d.is_dir(): continue
        for f in d.iterdir():
            if f.suffix.lower() in {".webp",".png",".jpg",".jpeg"}:
                return f
    return None

# ─────────────────────────────────────────────────────────────────────────────
#  Descargas
# ─────────────────────────────────────────────────────────────────────────────
def sha256(path):
    h = hashlib.sha256()
    with open(path,"rb") as f:
        for c in iter(lambda: f.read(65536), b""): h.update(c)
    return h.hexdigest()

def fetch_manifest(url):
    r = requests.get(url, timeout=30); r.raise_for_status(); return r.json()

def pending_files(manifest, game_dir):
    out = []
    for e in manifest.get("files", []):
        p = game_dir/e["path"]
        if not p.exists() or (e.get("sha256") and sha256(p) != e["sha256"]):
            out.append(e)
    return out

def dl_one(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest,"wb") as f:
            for chunk in r.iter_content(65536): f.write(chunk)

def dl_parallel(files, game_dir, on_prog, on_log, cancel_ev=None, workers=16):
    total=len(files); done=0; errors=[]; lock=threading.Lock()
    def _t(e):
        nonlocal done
        if cancel_ev and cancel_ev.is_set():
            with lock: done+=1; on_prog(done/total*100)
            return
        try:
            dl_one(e["url"], game_dir/e["path"])
            with lock: done+=1; on_prog(done/total*100); on_log(f"  + {e['path']}")
        except Exception as ex:
            with lock: done+=1; on_prog(done/total*100); errors.append((e["path"],str(ex)))
    with ThreadPoolExecutor(max_workers=workers) as ex: list(ex.map(_t,files))
    return errors

def fmt_bytes(b):
    for u in ("B","KB","MB","GB"):
        if b<1024: return f"{b:.1f} {u}"
        b/=1024
    return f"{b:.1f} GB"

# ─────────────────────────────────────────────────────────────────────────────
#  Auth / MC
# ─────────────────────────────────────────────────────────────────────────────
def offline_creds(username):
    return {"username":username,"uuid":str(uuid.uuid3(uuid.NAMESPACE_DNS,username)),
            "token":"0","user_type":"legacy"}

def vanilla_auth():
    try:
        f=APPDATA/".minecraft"/"launcher_accounts.json"
        if not f.exists(): return None
        data=json.loads(f.read_text(encoding="utf-8"))
        aid=data.get("activeAccountLocalId")
        if not aid: return None
        acc=data.get("accounts",{}).get(aid,{})
        mc=acc.get("minecraftProfile",{})
        return {"username":mc.get("name","Player"),"uuid":mc.get("id",str(uuid.uuid4())),
                "token":acc.get("accessToken",""),"user_type":"msa"}
    except: return None

def latest_fabric():
    try:
        vers=minecraft_launcher_lib.fabric.get_all_loader_versions()
        for v in vers:
            if v.get("stable"): return v["version"]
        return vers[0]["version"]
    except: return "0.16.14"

def find_java():
    for p in [MC_DIR/"runtime"/"java-runtime-delta"/"windows"/"java-runtime-delta"/"bin"/"java.exe",
              MC_DIR/"runtime"/"java-runtime-delta"/"windows-x64"/"java-runtime-delta"/"bin"/"java.exe"]:
        if p.exists(): return str(p)
    try:
        subprocess.run(["java","-version"],capture_output=True,timeout=3,creationflags=NOWND)
        return "java"
    except: return None

# ─────────────────────────────────────────────────────────────────────────────
#  Starfield animado con parpadeo random
# ─────────────────────────────────────────────────────────────────────────────
class StarField:
    def __init__(self, canvas, w, h, bg_color=DARK_BG):
        self.c=canvas; self.data=[]; self.bg=bg_color
        # Estrellas con pulso suave
        for _ in range(180): self._a(w,h,0.4,1.1,0.04,0.42,"cool","pulse")
        for _ in range(45):  self._a(w,h,0.9,1.9,0.14,0.65,"cool","pulse")
        for _ in range(20):  self._a(w,h,1.5,2.8,0.38,1.00,"warm","pulse")
        # Estrellas con parpadeo random (se apagan y encienden)
        for _ in range(70):  self._a(w,h,0.5,1.8,0.6,1.0,"cool","blink")
        for _ in range(20):  self._a(w,h,0.8,2.2,0.5,1.0,"warm","blink")
        self._tick()

    def _a(self,w,h,r0,r1,b0,b1,k,mode="pulse"):
        x=random.uniform(0,w); y=random.uniform(0,h); r=random.uniform(r0,r1)
        ph=random.uniform(0,6.28); sp=random.uniform(0.010,0.065)
        sid=self.c.create_oval(x-r,y-r,x+r,y+r,fill="#fff",outline="",tags="star")
        self.data.append({"id":sid,"ph":ph,"sp":sp,"b0":b0,"b1":b1,"k":k,
                           "mode":mode,"on":True,
                           "timer":random.randint(15,110),
                           "off_dur":random.randint(3,28)})

    def _color(self, s, b):
        if s["k"]=="warm":
            return f"#{int(b*255):02x}{int(b*235):02x}{int(b*160):02x}"
        return f"#{int(b*190):02x}{int(b*205):02x}{int(min(b*255,255)):02x}"

    def _tick(self):
        for s in self.data:
            if s["mode"]=="blink":
                s["timer"]-=1
                if s["timer"]<=0:
                    if s["on"]:
                        s["on"]=False
                        s["timer"]=s["off_dur"]
                        self.c.itemconfig(s["id"],fill=self.bg)
                    else:
                        s["on"]=True
                        s["timer"]=random.randint(25,130)
                        s["off_dur"]=random.randint(2,22)
                if s["on"]:
                    s["ph"]=(s["ph"]+s["sp"])%6.2832
                    b=(math.sin(s["ph"])+1)/2*(s["b1"]-s["b0"])+s["b0"]
                    self.c.itemconfig(s["id"],fill=self._color(s,b))
            else:
                s["ph"]=(s["ph"]+s["sp"])%6.2832
                t=(math.sin(s["ph"])+1)/2; b=s["b0"]+t*(s["b1"]-s["b0"])
                self.c.itemconfig(s["id"],fill=self._color(s,b))
        self.c.after(45,self._tick)

# ─────────────────────────────────────────────────────────────────────────────
#  Partículas de brillo alrededor de un widget
# ─────────────────────────────────────────────────────────────────────────────
class SparkleEffect:
    """Partículas doradas que orbitan un botón."""
    def __init__(self, canvas, cx, cy, radius=60, n=10):
        self.c=canvas; self.cx=cx; self.cy=cy; self.r=radius; self.particles=[]
        for i in range(n):
            angle=random.uniform(0,6.28); speed=random.uniform(0.03,0.07)
            dist=random.uniform(radius*0.5, radius)
            pr=random.uniform(1,2.5)
            sid=canvas.create_oval(0,0,0,0,fill=GOLD,outline="",tags="sparkle")
            self.particles.append({"id":sid,"angle":angle,"speed":speed,
                                    "dist":dist,"pr":pr,"life":random.uniform(0,6.28)})
        self._tick()

    def on_scale(self, sx, sy):
        """Actualiza centro y radio cuando el canvas se redimensiona."""
        self.cx *= sx
        self.cy *= sy
        self.r  *= (sx+sy)/2
        for p in self.particles:
            p["dist"] *= (sx+sy)/2

    def _tick(self):
        for p in self.particles:
            p["angle"]=(p["angle"]+p["speed"])%6.2832
            p["life"]=(p["life"]+0.06)%6.2832
            x=self.cx+math.cos(p["angle"])*p["dist"]
            y=self.cy+math.sin(p["angle"])*p["dist"]*0.45
            alpha=(math.sin(p["life"])+1)/2
            r=p["pr"]
            b=int(alpha*255); g=int(alpha*190)
            color=f"#{b:02x}{g:02x}{0:02x}"
            self.c.coords(p["id"],x-r,y-r,x+r,y+r)
            self.c.itemconfig(p["id"],fill=color)
        self.c.after(40,self._tick)

# ─────────────────────────────────────────────────────────────────────────────
#  Botón gold pulsante con borde animado
# ─────────────────────────────────────────────────────────────────────────────
class GlowButton:
    """Botón con borde dorado pulsante."""
    def __init__(self, canvas, x, y, w, h, text, command,
                 font_size=11, color=GOLD, is_play=False):
        self.c=canvas; self.x=x; self.y=y; self.w=w; self.h=h
        self.color=color; self.is_play=is_play; self.command=command
        self._phase=random.uniform(0,6.28)
        self._enabled=True

        # Sombra / glow base
        self._glow=canvas.create_rectangle(
            x-4,y-4,x+w+4,y+h+4, fill="", outline=GOLD_DIM, width=1)
        # Fondo del botón
        self._bg=canvas.create_rectangle(
            x,y,x+w,y+h, fill=DARK_CARD, outline=color, width=2)
        # Texto
        self._txt=canvas.create_text(
            x+w//2, y+h//2, text=text,
            font=("Consolas", font_size, "bold"),
            fill=color, anchor=tk.CENTER)

        for iid in (self._glow, self._bg, self._txt):
            canvas.tag_bind(iid,"<Button-1>",self._click)
            canvas.tag_bind(iid,"<Enter>",self._enter)
            canvas.tag_bind(iid,"<Leave>",self._leave)

        canvas.config(cursor="")
        self._animate()

    def _animate(self):
        self._phase=(self._phase+0.04)%6.2832
        t=(math.sin(self._phase)+1)/2
        if self._enabled:
            if self.is_play:
                r=int(0+t*0); g=int(150+t*105); b=int(100+t*70)
                glow_c=f"#{r:02x}{g:02x}{b:02x}"
            else:
                r=int(80+t*175); g=int(80+t*120); b=0
                glow_c=f"#{r:02x}{g:02x}{b:02x}"
            self.c.itemconfig(self._glow, outline=glow_c)
            self.c.itemconfig(self._bg,   outline=glow_c)
        self.c.after(40,self._animate)

    def _enter(self,_):
        if not self._enabled: return
        self.c.itemconfig(self._bg, fill="#1a2a3a")
        self.c.config(cursor="hand2")

    def _leave(self,_):
        self.c.itemconfig(self._bg, fill=DARK_CARD)
        self.c.config(cursor="")

    def _click(self,_):
        if self._enabled: self.command()

    def set_text(self, text):
        self.c.itemconfig(self._txt, text=text)

    def set_color(self, color):
        self.color=color
        self.c.itemconfig(self._txt, fill=color)

    def disable(self):
        self._enabled=False
        self.c.itemconfig(self._txt, fill="#404040")
        self.c.itemconfig(self._bg,  fill="#0a0f18", outline="#1a2030")
        self.c.itemconfig(self._glow,outline="#0f1820")

    def enable(self):
        self._enabled=True
        self.c.itemconfig(self._txt, fill=self.color)
        self.c.itemconfig(self._bg,  fill=DARK_CARD, outline=self.color)

    def hide(self):
        for iid in (self._glow,self._bg,self._txt):
            self.c.itemconfig(iid,state="hidden")
        self._enabled=False

    def show(self):
        for iid in (self._glow,self._bg,self._txt):
            self.c.itemconfig(iid,state="normal")
        self._enabled=True

# ─────────────────────────────────────────────────────────────────────────────
#  Login Microsoft — abre navegador, usuario pega la URL de redirección
# ─────────────────────────────────────────────────────────────────────────────
class MicrosoftLoginWindow:
    CLIENT_ID = "9807cd61-bf58-4245-b40c-b8ffeea785dd"

    def __init__(self, parent, on_success):
        self.on_success = on_success
        self._code_ver  = ""
        self._state     = ""
        # Puerto libre para servidor local
        with socket.socket() as s:
            s.bind(("", 0)); self._port = s.getsockname()[1]
        self._redirect = f"http://localhost:{self._port}"

        self.win = tk.Toplevel(parent)
        self.win.title("Login Premium — Microsoft")
        self.win.geometry("420x200")
        self.win.configure(bg="#0b1525")
        self.win.resizable(False, False)
        self.win.grab_set()
        self._build()

    def _build(self):
        tk.Label(self.win, text="Login Premium (Microsoft)",
                 font=("Consolas",13,"bold"), bg="#0b1525", fg=GOLD
                 ).pack(pady=(18,6))
        self._status = tk.Label(self.win,
            text="Preparando ventana de login...",
            font=("Consolas",10), bg="#0b1525", fg=TEXT_DIM, wraplength=400)
        self._status.pack(pady=8)
        tk.Label(self.win,
            text="Se abrirá una ventana de Microsoft para iniciar sesión.",
            font=("Consolas",8), bg="#0b1525", fg=TEXT_DIM).pack(pady=4)
        tk.Button(self.win, text="Cancelar", font=("Consolas",9),
                  bg="#1a2840", fg=TEXT_DIM, relief=tk.FLAT, cursor="hand2",
                  padx=8, pady=4, command=self.win.destroy).pack(pady=10)
        # Lanzar el webview tras mostrar la ventana
        self.win.after(200, self._launch_webview)

    def _launch_webview(self):
        from minecraft_launcher_lib.microsoft_account import get_secure_login_data
        try:
            login_url, self._state, self._code_ver = get_secure_login_data(
                self.CLIENT_ID, self._redirect)
        except Exception as e:
            self._status.config(text=f"Error: {e}", fg="#ff6040"); return

        threading.Thread(target=self._serve, args=(login_url,), daemon=True).start()

    def _serve(self, login_url):
        import time as _t
        captured = [None]
        self_ = self

        try:
            import webview

            def _monitor(window):
                while True:
                    try:
                        url = window.get_current_url() or ""
                        if url.startswith(self_._redirect):
                            captured[0] = url
                            window.destroy()
                            return
                    except Exception: pass
                    _t.sleep(0.25)

            win = webview.create_window(
                "Login con Microsoft — CobbleverseMMO",
                login_url, width=500, height=660)
            webview.start(_monitor, win, gui="edgechromium")

        except Exception:
            # Fallback: servidor HTTP + navegador
            import webbrowser, http.server as _hs
            webbrowser.open(login_url)
            redir = [None]

            class H(_hs.BaseHTTPRequestHandler):
                def do_GET(self):
                    redir[0] = f"http://localhost:{self_._port}{self.path}"
                    self.send_response(200)
                    self.send_header("Content-type","text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"<html><body>OK</body></html>")
                    threading.Thread(target=srv.shutdown, daemon=True).start()
                def log_message(self,*a): pass

            srv = _hs.HTTPServer(("localhost", self_._port), H)
            srv.serve_forever()
            captured[0] = redir[0]

        if captured[0]:
            self_.win.after(0, lambda u=captured[0]: self_._complete(u))
        else:
            try:
                self_.win.after(0, lambda: self_._status.config(
                    text="Login cancelado.", fg="#ff6040"))
            except Exception: pass

    def _complete(self, redirect_url):
        if not self.win.winfo_exists(): return
        self._status.config(text="Verificando cuenta de Minecraft...")
        threading.Thread(target=self._finish, args=(redirect_url,), daemon=True).start()

    def _finish(self, redirect_url):
        try:
            from minecraft_launcher_lib.microsoft_account import parse_auth_code_url
            self.win.after(0, lambda: self._status.config(text="Paso 1/5: Parseando código OAuth..."))
            auth_code = parse_auth_code_url(redirect_url, self._state)
            creds = self._manual_auth(auth_code)
            self.win.after(0, lambda: self._success(creds))
        except Exception as e:
            import traceback
            err_detail = traceback.format_exc()
            print("[LOGIN ERROR]", err_detail)
            msg = f"{type(e).__name__}: {e}"
            try:
                self.win.after(0, lambda m=msg[:300]: self._status.config(
                    text=m, fg="#ff6040"))
            except Exception: pass

    def _manual_auth(self, auth_code):
        """Usa las funciones internas de minecraft_launcher_lib para el auth."""
        from minecraft_launcher_lib.microsoft_account import (
            get_authorization_token,
            authenticate_with_xbl,
            authenticate_with_xsts,
            authenticate_with_minecraft,
            get_profile,
        )

        def _step(n, total, msg):
            try:
                self.win.after(0, lambda m=f"Paso {n}/{total}: {msg}":
                               self._status.config(text=m))
            except Exception: pass

        # 1. OAuth token
        _step(2, 5, "Obteniendo token OAuth...")
        token_data = get_authorization_token(
            self.CLIENT_ID, None, self._redirect, auth_code, self._code_ver)
        if "access_token" not in token_data:
            err = token_data.get("error_description") or token_data.get("error","Token error")
            raise ValueError(f"[OAuth] {err}")
        ms_token = token_data["access_token"]

        # 2. Xbox Live
        _step(3, 5, "Autenticando con Xbox Live...")
        xbl = authenticate_with_xbl(ms_token)
        if "Token" not in xbl:
            xerr = xbl.get("XErr",""); msg = xbl.get("Message", str(xbl)[:150])
            raise ValueError(f"[XBL] XErr={xerr}: {msg}")
        uhs = xbl["DisplayClaims"]["xui"][0]["uhs"]

        # 3. XSTS para Minecraft
        _step(4, 5, "Verificando XSTS...")
        xsts = authenticate_with_xsts(xbl["Token"])
        if "Token" not in xsts:
            xerr = xsts.get("XErr",""); msg = xsts.get("Message", str(xsts)[:150])
            raise ValueError(f"[XSTS] XErr={xerr}: {msg}")
        xsts_t = xsts["Token"]

        # 4. Minecraft token
        _step(5, 5, "Obteniendo token de Minecraft...")
        mc = authenticate_with_minecraft(uhs, xsts_t)
        if "access_token" not in mc:
            raise ValueError(f"[MC Auth] {str(mc)[:200]}")
        mc_token = mc["access_token"]

        # 5. Perfil (username + UUID)
        try:
            profile = get_profile(mc_token)
            name = profile.get("name","Player")
            uid  = profile.get("id", str(uuid.uuid4()))
        except Exception:
            name = xbl.get("DisplayClaims",{}).get("xui",[{}])[0].get("gtg","Player")
            uid  = str(uuid.uuid4())

        return {
            "username":  name,
            "uuid":      uid,
            "token":     mc_token,
            "user_type": "msa",
        }

    def _success(self, creds):
        if not self.win.winfo_exists(): return
        self._status.config(text=f"¡Bienvenido, {creds['username']}!", fg="#00cc55")
        self.win.after(1500, lambda: (self.win.destroy(), self.on_success(creds)))

# ─────────────────────────────────────────────────────────────────────────────
#  Ventana de skin — preview 2-D + cargar / buscar por nombre
# ─────────────────────────────────────────────────────────────────────────────
class SkinWindow:
    SCALE = 8   # px por pixel de skin

    def __init__(self, parent, game_dir, username="Steve"):
        self.game_dir = Path(game_dir)
        self.username = username
        self.skin_img = None
        self.win = tk.Toplevel(parent)
        self.win.title("Mi Skin")
        self.win.geometry("520x420")
        self.win.configure(bg="#0b1525")
        self.win.resizable(False, False)
        self._build()

    def _build(self):
        tk.Label(self.win, text="Configurar Skin",
                 font=("Consolas",13,"bold"), bg="#0b1525", fg=GOLD
                 ).pack(pady=(12,4))

        content = tk.Frame(self.win, bg="#0b1525")
        content.pack(fill=tk.BOTH, expand=True, padx=16)

        # Columna izquierda — preview
        left = tk.Frame(content, bg="#0b1525")
        left.pack(side=tk.LEFT, padx=(0,16))

        s = self.SCALE
        cw, ch = 16*s, 32*s   # 128×256
        self._cv = tk.Canvas(left, width=cw, height=ch,
                              bg="#060d1a", highlightthickness=2,
                              highlightbackground=GOLD_DIM)
        self._cv.pack()
        tk.Label(left, text="Vista previa", font=("Consolas",7),
                 bg="#0b1525", fg=TEXT_DIM).pack(pady=(4,0))

        # Columna derecha — controles
        right = tk.Frame(content, bg="#0b1525")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(right, text="Buscar por nombre (Minecraft):",
                 font=("Consolas",8), bg="#0b1525", fg=TEXT_DIM
                 ).pack(anchor=tk.W, pady=(4,2))

        row1 = tk.Frame(right, bg="#0b1525")
        row1.pack(fill=tk.X)
        self._name_var = tk.StringVar(value=self.username)
        tk.Entry(row1, textvariable=self._name_var,
                 font=("Consolas",10), bg="#0d1828", fg=GOLD,
                 insertbackground=GOLD, relief=tk.FLAT, width=16
                 ).pack(side=tk.LEFT, ipady=4, padx=(0,6))
        tk.Button(row1, text="Buscar", font=("Consolas",9,"bold"),
                  bg="#1a2840", fg=GOLD, relief=tk.FLAT, cursor="hand2",
                  padx=8, pady=4,
                  command=self._fetch_by_name).pack(side=tk.LEFT)

        tk.Label(right, text="O carga un archivo .png local:",
                 font=("Consolas",8), bg="#0b1525", fg=TEXT_DIM
                 ).pack(anchor=tk.W, pady=(14,2))
        tk.Button(right, text="  Cargar .png  ",
                  font=("Consolas",9,"bold"), bg="#1a2840", fg=GOLD,
                  relief=tk.FLAT, cursor="hand2", padx=8, pady=4,
                  command=self._load_file).pack(anchor=tk.W)

        tk.Label(right, text="Guardar skin en carpeta del juego:",
                 font=("Consolas",8), bg="#0b1525", fg=TEXT_DIM
                 ).pack(anchor=tk.W, pady=(14,2))
        tk.Button(right, text="  Guardar skin  ",
                  font=("Consolas",9,"bold"), bg=GOLD, fg=BLACK,
                  relief=tk.FLAT, cursor="hand2", padx=8, pady=4,
                  command=self._save).pack(anchor=tk.W)

        self._status = tk.Label(self.win, text="Busca o carga una skin para previsualizar.",
                                font=("Consolas",8), bg="#0b1525", fg=TEXT_DIM,
                                wraplength=480)
        self._status.pack(pady=8)

        # Intentar cargar skin guardada
        self._try_existing()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _try_existing(self):
        p = self.game_dir / "skin.png"
        if p.exists():
            try:
                self.skin_img = Image.open(p).convert("RGBA")
                self._render(); self._status.config(text="Skin guardada cargada.")
            except: pass

    def _load_file(self):
        path = filedialog.askopenfilename(
            title="Seleccionar skin PNG",
            filetypes=[("PNG", "*.png")])
        if path:
            try:
                self.skin_img = Image.open(path).convert("RGBA")
                self._render(); self._status.config(text="Skin cargada desde archivo.")
            except Exception as e:
                self._status.config(text=f"Error: {e}")

    def _fetch_by_name(self):
        name = self._name_var.get().strip()
        if not name: return
        self._status.config(text=f"Buscando skin de '{name}'...")
        self.win.update()
        threading.Thread(target=self._do_fetch, args=(name,), daemon=True).start()

    def _do_fetch(self, name):
        try:
            r = requests.get(
                f"https://api.mojang.com/users/profiles/minecraft/{name}",
                timeout=8); r.raise_for_status()
            uid = r.json()["id"]
            r2 = requests.get(
                f"https://sessionserver.mojang.com/session/minecraft/profile/{uid}",
                timeout=8); r2.raise_for_status()
            for prop in r2.json().get("properties",[]):
                if prop["name"] == "textures":
                    decoded = json.loads(base64.b64decode(prop["value"]).decode())
                    skin_url = decoded["textures"]["SKIN"]["url"]
                    r3 = requests.get(skin_url, timeout=8); r3.raise_for_status()
                    self.skin_img = Image.open(BytesIO(r3.content)).convert("RGBA")
                    self.win.after(0, self._render)
                    self.win.after(0, lambda: self._status.config(
                        text=f"Skin de '{name}' cargada.", fg=TEXT_DIM))
                    return
            self.win.after(0, lambda: self._status.config(text="No se encontró skin."))
        except Exception as e:
            self.win.after(0, lambda: self._status.config(text=f"Error: {e}"))

    def _render(self):
        if not self.skin_img: return
        skin = self.skin_img
        s = self.SCALE

        def crop(x, y, w, h):
            return skin.crop((x, y, x+w, y+h)).resize((w*s, h*s), Image.NEAREST)

        head  = crop(8,  8,  8, 8)
        hat   = crop(40, 8,  8, 8)
        body  = crop(20, 20, 8, 12)
        r_arm = crop(44, 20, 4, 12)
        l_arm = crop(36, 52, 4, 12)   # formato 1.8+
        r_leg = crop(4,  20, 4, 12)
        l_leg = crop(20, 52, 4, 12)   # formato 1.8+

        cw, ch = 16*s, 32*s
        out = Image.new("RGBA", (cw, ch), (0,0,0,0))
        # Cabeza centrada
        out.paste(head,  (4*s, 0),     head)
        out.paste(hat,   (4*s, 0),     hat)
        # Cuerpo
        out.paste(body,  (4*s, 8*s),   body)
        # Brazos
        out.paste(r_arm, (0,   8*s),   r_arm)
        out.paste(l_arm, (12*s, 8*s),  l_arm)
        # Piernas
        out.paste(r_leg, (4*s, 20*s),  r_leg)
        out.paste(l_leg, (8*s, 20*s),  l_leg)

        bg = Image.new("RGBA", (cw, ch), (10, 18, 35, 255))
        final = Image.alpha_composite(bg, out)
        self._tk_img = ImageTk.PhotoImage(final)
        self._cv.create_image(0, 0, anchor=tk.NW, image=self._tk_img)

    def _save(self):
        if not self.skin_img:
            self._status.config(text="No hay skin cargada para guardar."); return
        try:
            self.game_dir.mkdir(parents=True, exist_ok=True)
            self.skin_img.save(self.game_dir / "skin.png")
            self._status.config(text=f"Skin guardada en: {self.game_dir / 'skin.png'}")
        except Exception as e:
            self._status.config(text=f"Error al guardar: {e}")

# ─────────────────────────────────────────────────────────────────────────────
#  PANTALLA 1 — Login
# ─────────────────────────────────────────────────────────────────────────────
class LoginScreen(tk.Frame):
    def __init__(self, root, on_continue):
        super().__init__(root, bg=DARK_BG)
        self.on_continue=on_continue
        self._auth="offline"
        self._ms_creds=None          # credenciales Microsoft guardadas
        self._cv_w=W; self._cv_h=H
        self._resize_job=None
        self._build()

    def _build(self):
        cv=tk.Canvas(self,width=W,height=H,bg=DARK_BG,highlightthickness=0)
        cv.pack(fill=tk.BOTH,expand=True)
        self.cv=cv
        cv.bind("<Configure>",self._on_resize)
        StarField(cv,W,H,bg_color=DARK_BG)

        # Título
        cv.create_text(W//2+2,82,text="COBBLEVERSEMMO",
                       font=("Consolas",38,"bold"),fill="#3a2600",anchor=tk.CENTER)
        cv.create_text(W//2,80,text="COBBLEVERSEMMO",
                       font=("Consolas",38,"bold"),fill=GOLD,anchor=tk.CENTER)
        cv.create_text(W//2,114,text=f"Fabric {MC_VERSION}  ·  v{APP_VERSION}",
                       font=("Consolas",9),fill=TEXT_DIM,anchor=tk.CENTER)

        # Línea decorativa
        cv.create_line(100,132,W-100,132,fill="#1a2840",width=1)

        # Tarjeta — más alta para que el botón quepa
        cw,ch=500,315; cx=W//2; cy=H//2+20   # cy=310
        card_top=cy-ch//2          # 152
        card_bot=cy+ch//2          # 467
        cv.create_rectangle(cx-cw//2-3,card_top-3,cx+cw//2+3,card_bot+3,
                            fill=GOLD_DIM,outline="")
        cv.create_rectangle(cx-cw//2,card_top,cx+cw//2,card_bot,
                            fill="#0b1525",outline="#1e3a60",width=1)

        cv.create_text(cx,card_top+26,text="Selecciona tu modo de juego",
                       font=("Consolas",12,"bold"),fill=GOLD,anchor=tk.CENTER)

        # Frame interior — posicionado en la mitad superior de la tarjeta
        # Su borde inferior queda en ~375, dejando espacio para el botón abajo
        inner_cy = cy - 30           # 280
        inner_h  = ch - 155          # 160
        inner=tk.Frame(cv,bg="#0b1525")
        cv.create_window(cx, inner_cy, window=inner, anchor=tk.CENTER,
                         width=cw-20, height=inner_h)

        # Botones de modo (como tabs)
        tab_row=tk.Frame(inner,bg="#0b1525")
        tab_row.pack(pady=(8,0))

        self._btn_off=tk.Button(tab_row,text="  No-Premium (Offline)  ",
                                font=("Consolas",10,"bold"),
                                bg=GOLD,fg=BLACK,relief=tk.FLAT,
                                padx=12,pady=8,cursor="hand2",
                                activebackground=GOLD2,activeforeground=BLACK,
                                command=lambda:self._set_mode("offline"))
        self._btn_off.pack(side=tk.LEFT,padx=(0,6))

        self._btn_pre=tk.Button(tab_row,text="  Premium (Microsoft)  ",
                                font=("Consolas",10,"bold"),
                                bg="#1a2840",fg=TEXT_DIM,relief=tk.FLAT,
                                padx=12,pady=8,cursor="hand2",
                                activebackground="#2a3a55",activeforeground=TEXT_W,
                                command=lambda:self._set_mode("premium"))
        self._btn_pre.pack(side=tk.LEFT)

        # Campo usuario
        self._user_outer=tk.Frame(inner,bg="#0b1525")
        self._user_outer.pack(pady=(14,0),fill=tk.X,padx=20)

        tk.Label(self._user_outer,text="Tu nombre en el juego:",
                 font=("Consolas",9),bg="#0b1525",fg=TEXT_DIM
                 ).pack(anchor=tk.W)

        entry_fr=tk.Frame(self._user_outer,bg=GOLD,padx=2,pady=2)
        entry_fr.pack(fill=tk.X,pady=(4,0))
        self._uvar=tk.StringVar(value=load_cfg().get("username",""))
        self._uentry=tk.Entry(entry_fr,textvariable=self._uvar,
                              font=("Consolas",13),
                              bg="#0d1828",fg=GOLD,
                              insertbackground=GOLD,
                              relief=tk.FLAT,bd=0)
        self._uentry.pack(fill=tk.X,ipady=6,padx=2)
        self._uentry.focus_set()

        # Info premium + botón de detectar sesión
        self._prem_info=tk.Label(inner,
                                  text="Inicia sesión con tu cuenta Microsoft / Minecraft.",
                                  font=("Consolas",9),bg="#0b1525",fg=TEAL,
                                  wraplength=400)
        self._prem_login_fr=tk.Frame(inner,bg="#0b1525")
        self._prem_login_btn=tk.Button(
            self._prem_login_fr, text="  Iniciar sesión con Microsoft  ",
            font=("Consolas",10,"bold"),
            bg="#1a2840", fg=TEAL, relief=tk.FLAT, padx=10, pady=7,
            cursor="hand2", activebackground="#2a3a55", activeforeground=TEAL,
            command=self._open_ms_login)
        self._prem_login_btn.pack(pady=(6,0))
        self._prem_status=tk.Label(self._prem_login_fr, text="",
                                    font=("Consolas",8), bg="#0b1525", fg="#00cc55")

        # Botón CONTINUAR — posicionado DEBAJO del inner frame (fuera de su área)
        # inner va de ~200 a ~360; botón empieza en ~400
        btn_y = inner_cy + inner_h//2 + 38   # ~398, bien debajo del frame
        self._sparkle_cont=SparkleEffect(cv, cx, btn_y + 21, radius=85, n=10)
        GlowButton(cv, cx-95, btn_y, 190, 46,
                   "CONTINUAR  ▶", self._do_continue,
                   font_size=12, color=TEAL)

        # Links sociales en la parte inferior de la pantalla
        social_fr=tk.Frame(cv,bg=DARK_BG)
        tk.Button(social_fr,text="⬡  Discord",
                  font=("Consolas",9,"bold"),
                  bg="#5865F2",fg="white",
                  relief=tk.FLAT,padx=10,pady=5,cursor="hand2",bd=0,
                  activebackground="#7289da",activeforeground="white",
                  command=self._open_discord).pack(side=tk.LEFT,padx=(0,8))
        tk.Button(social_fr,text="♪  TikTok",
                  font=("Consolas",9,"bold"),
                  bg="#010101",fg="white",
                  relief=tk.FLAT,padx=10,pady=5,cursor="hand2",bd=0,
                  activebackground="#333",activeforeground="white",
                  command=self._open_tiktok).pack(side=tk.LEFT)
        cv.create_window(cx, H-18, window=social_fr, anchor=tk.CENTER)

        self._set_mode("offline")

    def _on_resize(self,event):
        if self._resize_job: self.after_cancel(self._resize_job)
        nw,nh=event.width,event.height
        self._resize_job=self.after(80,lambda:self._do_resize(nw,nh))

    def _do_resize(self,nw,nh):
        self._resize_job=None
        sx=nw/self._cv_w; sy=nh/self._cv_h
        if abs(sx-1.0)<0.005 and abs(sy-1.0)<0.005: return
        self.cv.scale("all",0,0,sx,sy)
        self._cv_w=nw; self._cv_h=nh
        if hasattr(self,"_sparkle_cont"):
            self._sparkle_cont.on_scale(sx,sy)

    def _set_mode(self, mode):
        self._auth=mode
        if mode=="offline":
            self._btn_off.config(bg=GOLD,fg=BLACK)
            self._btn_pre.config(bg="#1a2840",fg=TEXT_DIM)
            self._prem_info.pack_forget()
            self._prem_login_fr.pack_forget()
            self._user_outer.pack(pady=(14,0),fill=tk.X,padx=20)
        else:
            self._btn_pre.config(bg=TEAL,fg=BLACK)
            self._btn_off.config(bg="#1a2840",fg=TEXT_DIM)
            self._user_outer.pack_forget()
            self._prem_info.pack(pady=(10,0))
            self._prem_login_fr.pack(pady=(4,0))

    def _open_discord(self):
        import webbrowser; webbrowser.open("https://discord.gg/atTNKrR8eb")
    def _open_tiktok(self):
        import webbrowser; webbrowser.open("https://www.tiktok.com/@cobbleversemmo.net")

    def _open_ms_login(self):
        MicrosoftLoginWindow(self, self._on_ms_success)

    def _on_ms_success(self, creds):
        self._ms_creds=creds
        self._prem_login_btn.config(
            text=f"  ✓  {creds['username']}  ", bg="#0d2010", fg="#00cc55")
        self._prem_status.config(text="Sesión iniciada correctamente.")
        self._prem_status.pack()

    def _detect_premium(self):
        """Lee la sesión activa del Minecraft Launcher oficial de Mojang."""
        creds = vanilla_auth()
        if creds and creds.get("username","Player") != "Player":
            self._on_ms_success(creds)
        else:
            # Intentar leer launcher_accounts.json de varias ubicaciones
            creds = self._find_mc_session()
            if creds:
                self._on_ms_success(creds)
            else:
                self._prem_status.config(
                    text="No se encontró sesión. Abre el Minecraft Launcher oficial,\n"
                         "inicia sesión y vuelve a intentarlo.",
                    fg="#ff6040")
                self._prem_status.pack()

    def _find_mc_session(self):
        """Busca cuentas en varias ubicaciones del launcher oficial."""
        paths=[
            APPDATA/".minecraft"/"launcher_accounts.json",
            Path.home()/".minecraft"/"launcher_accounts.json",
            APPDATA/"Roaming"/".minecraft"/"launcher_accounts.json",
        ]
        for f in paths:
            try:
                if not f.exists(): continue
                data=json.loads(f.read_text(encoding="utf-8"))
                # Intentar cuenta activa primero
                aid=data.get("activeAccountLocalId")
                accounts=data.get("accounts",{})
                if aid and aid in accounts:
                    acc=accounts[aid]
                    mc=acc.get("minecraftProfile",{})
                    name=mc.get("name") or acc.get("displayName","")
                    uid=mc.get("id","")
                    token=acc.get("accessToken","")
                    if name:
                        return {"username":name,"uuid":uid or str(uuid.uuid4()),
                                "token":token,"user_type":"msa"}
                # Si no hay activa, tomar la primera
                for acc in accounts.values():
                    mc=acc.get("minecraftProfile",{})
                    name=mc.get("name") or acc.get("displayName","")
                    if name:
                        return {"username":name,
                                "uuid":mc.get("id",str(uuid.uuid4())),
                                "token":acc.get("accessToken",""),
                                "user_type":"msa"}
            except: continue
        return None

    def _do_continue(self):
        auth=self._auth; username=self._uvar.get().strip()
        if auth=="offline" and not username:
            messagebox.showwarning("Nombre requerido",
                                   "Escribe tu nombre de usuario.")
            return
        if auth=="premium" and not self._ms_creds:
            messagebox.showwarning("Login requerido",
                                   "Primero inicia sesión con Microsoft.")
            return
        cfg=load_cfg()
        cfg.update({"auth":auth,"username":username})
        if self._ms_creds:
            cfg["ms_creds"]=self._ms_creds
        save_cfg(cfg)
        self.on_continue(auth, username, self._ms_creds)

# ─────────────────────────────────────────────────────────────────────────────
#  PANTALLA 2 — Launcher principal
# ─────────────────────────────────────────────────────────────────────────────
class MainLauncher(tk.Frame):
    def __init__(self, root, auth, username, ms_creds=None):
        super().__init__(root,bg=BLACK)
        self._auth=auth; self._username=username; self._ms_creds=ms_creds
        self._thread=None; self._ready=False; self._ldata=None
        self._bg_ref=None
        self._cv_w=W; self._cv_h=H
        self.cfg=load_cfg()
        self._ver=self.cfg.get("version","normal")
        self._close_after=tk.BooleanVar(value=False)
        self._cancel_ev=threading.Event()
        self._mc_proc=None
        self._build()

    def _build(self):
        cv=tk.Canvas(self,width=W,height=H,bg=BLACK,highlightthickness=0)
        cv.pack(fill=tk.BOTH,expand=True)
        self.cv=cv
        self._bg_item=None
        self._resize_job=None
        self._bg_path=find_bg()
        self._load_bg()
        cv.bind("<Configure>",self._on_resize)

        # Separadores (los overlays oscuros están bakeados en la imagen)
        cv.create_line(0,52,W,52,fill="#1a2840",width=1)
        cv.create_line(0,H-118,W,H-118,fill="#1a2840",width=1)

        # Estrellas decorativas en las barras
        for _ in range(30):
            x=random.randint(0,W); y=random.choice([random.randint(4,48),random.randint(H-114,H-4)])
            r=random.uniform(0.5,1.5)
            cv.create_oval(x-r,y-r,x+r,y+r,fill="#6080a0",outline="")

        self._build_topbar()
        self._build_action_buttons()
        self._build_left_bar()
        self._build_bottom_bar()

    def _make_bg_image(self, bg, nw, nh):
        img=Image.open(bg).resize((nw,nh),Image.LANCZOS)
        img=ImageEnhance.Brightness(img).enhance(0.75)
        img_rgba=img.convert("RGBA")
        ov=Image.new("RGBA",(nw,nh),(0,0,0,0))
        draw=ImageDraw.Draw(ov)
        top_h=58
        for yi in range(top_h):
            a=int(210*(1-yi/top_h))
            draw.rectangle([0,yi,nw,yi+1],fill=(5,8,15,a))
        bot_start=nh-125
        for yi in range(max(0,bot_start),nh):
            t=(yi-bot_start)/(nh-bot_start) if nh>bot_start else 1.0
            draw.rectangle([0,yi,nw,yi+1],fill=(5,8,15,int(230*t)))
        return Image.alpha_composite(img_rgba,ov).convert("RGB")

    def _load_bg(self):
        if self._bg_path:
            try:
                img=self._make_bg_image(self._bg_path,W,H)
                self._bg_ref=ImageTk.PhotoImage(img)
                self._bg_item=self.cv.create_image(0,0,anchor=tk.NW,image=self._bg_ref)
                return
            except: pass
        StarField(self.cv,W,H,bg_color=BLACK)

    def _on_resize(self,event):
        if self._resize_job: self.after_cancel(self._resize_job)
        nw,nh=event.width,event.height
        self._resize_job=self.after(80,lambda:self._do_resize(nw,nh))

    def _do_resize(self,nw,nh):
        self._resize_job=None
        sx=nw/self._cv_w; sy=nh/self._cv_h
        if abs(sx-1.0)<0.005 and abs(sy-1.0)<0.005: return
        # Escala todos los items del canvas proporcionalmente
        self.cv.scale("all",0,0,sx,sy)
        self._cv_w=nw; self._cv_h=nh
        # Notifica a SparkleEffects del nuevo centro/radio
        if hasattr(self,"_sparkle_play"):
            self._sparkle_play.on_scale(sx,sy)
        # Actualiza imagen de fondo al nuevo tamaño
        if self._bg_path and self._bg_item:
            try:
                img=self._make_bg_image(self._bg_path,nw,nh)
                self._bg_ref=ImageTk.PhotoImage(img)
                self.cv.itemconfig(self._bg_item,image=self._bg_ref)
            except: pass

    def _build_topbar(self):
        cv=self.cv
        # Logo texto
        cv.create_text(W//2+2,27,text="COBBLEVERSEMMO",
                       font=("Consolas",15,"bold"),fill="#3a2600",anchor=tk.CENTER)
        cv.create_text(W//2,26,text="COBBLEVERSEMMO",
                       font=("Consolas",15,"bold"),fill=GOLD,anchor=tk.CENTER)

        # Volver
        self._back_btn=tk.Button(self,text="◀ Cuenta",
                                  font=("Consolas",8),
                                  bg="#05080f",fg=TEXT_DIM,
                                  relief=tk.FLAT,bd=0,cursor="hand2",
                                  activebackground="#05080f",activeforeground=GOLD,
                                  command=self._go_back)
        cv.create_window(12,26,window=self._back_btn,anchor=tk.W)

        # Selector versión
        self._ver_fr=tk.Frame(self,bg="#05080f")
        for key,ver in VERSIONS_CFG.items():
            active=key==self._ver
            tk.Button(self._ver_fr,text=ver["tag"],
                      font=("Consolas",8,"bold" if active else "normal"),
                      bg=GOLD if active else "#141e30",
                      fg=BLACK if active else TEXT_DIM,
                      relief=tk.FLAT,padx=10,pady=3,cursor="hand2",
                      bd=0,activebackground=GOLD2,activeforeground=BLACK,
                      command=lambda k=key:self._select_ver(k)
                      ).pack(side=tk.LEFT,padx=2)
        cv.create_window(W-10,26,window=self._ver_fr,anchor=tk.E)

    def _build_action_buttons(self):
        cv=self.cv
        rx=W-20; bw=200; bh=40

        # UPDATE
        self._btn_upd=GlowButton(cv,rx-bw,72,bw,bh,
                                  "  Actualizar",self._on_update,
                                  font_size=11,color=GOLD)

        # PLAY (grande, con partículas)
        ph=90
        self._btn_play=GlowButton(cv,rx-bw-20,72+bh+14,bw+20,ph,
                                   "  JUGAR",self._on_play,
                                   font_size=20,color=TEAL,is_play=True)
        self._sparkle_play=SparkleEffect(cv,rx-bw//2-10,72+bh+14+ph//2,radius=bw//2+20,n=12)

        # MODS
        self._btn_mods=GlowButton(cv,rx-bw,72+bh+14+ph+14,bw,bh,
                                   "  Mods",self._open_mods,
                                   font_size=11,color=GOLD)

        # CANCELAR (visible solo durante carga)
        by2=72+bh+14+ph+14+bh+10
        self._btn_cancel=GlowButton(cv,rx-bw,by2,bw,36,
                                     "  ✕  Cancelar carga",self._on_cancel,
                                     font_size=10,color="#ff6040")
        self._btn_cancel.hide()

        # CERRAR MINECRAFT (visible solo cuando MC está corriendo)
        self._btn_close_mc=GlowButton(cv,rx-bw,by2,bw,36,
                                       "  ⏹  Cerrar Minecraft",self._on_close_mc,
                                       font_size=10,color="#ff3333")
        self._btn_close_mc.hide()

    def _build_left_bar(self):
        cv=self.cv

        # Settings
        GlowButton(cv,14,64,130,36,"  Settings",self._open_settings,
                   font_size=9,color=GOLD)
        # Tienda
        GlowButton(cv,14,108,130,36,"  Tienda",self._open_store,
                   font_size=9,color=GOLD)
        # Discord y TikTok como GlowButtons pequeños debajo
        GlowButton(cv,14,152,63,28,"Discord",self._open_discord,
                   font_size=8,color="#7289da")
        GlowButton(cv,81,152,63,28,"TikTok",self._open_tiktok,
                   font_size=8,color="#ffffff")
        # Skin
        GlowButton(cv,14,190,130,30,"  Skin",self._open_skin_window,
                   font_size=9,color=TEAL)

    def _build_bottom_bar(self):
        cv=self.cv
        y0=H-120   # barra inferior más alta para que todo quepa

        # ── Barra de progreso (más gruesa, 16px) ─────────────────────────────
        cv.create_rectangle(14,y0+5,W-14,y0+21,
                            fill="#060d1a",outline="#1a2840",width=1)
        self._prog_fill=cv.create_rectangle(15,y0+6,15,y0+20,
                                             fill=GOLD,outline="")
        self._prog_pct=cv.create_text(W//2,y0+13,text="",
                                       font=("Consolas",7,"bold"),
                                       fill=DARK_BG,anchor=tk.CENTER)

        # ── Fila de estado ────────────────────────────────────────────────────
        self._status_id=cv.create_text(14,y0+30,text="Listo.",
                                        font=("Consolas",8),
                                        fill=TEXT_DIM,anchor=tk.W)

        # Indicador de servidor (punto + texto)
        self._srv_dot=cv.create_oval(W//2-52,y0+25,W//2-40,y0+35,
                                      fill="#333344",outline="")
        self._srv_txt=cv.create_text(W//2-34,y0+30,text="Servidor...",
                                      font=("Consolas",8),fill=TEXT_DIM,
                                      anchor=tk.W)

        # Checkbox — en su propio frame, bg oscuro para que sea legible
        close_fr=tk.Frame(self,bg=DARK_BG)
        tk.Checkbutton(close_fr,
                       text="Cerrar al iniciar Minecraft",
                       variable=self._close_after,
                       font=("Consolas",8),
                       bg=DARK_BG,fg=TEXT_DIM,
                       selectcolor="#0a1220",
                       activebackground=DARK_BG,
                       activeforeground=GOLD).pack(side=tk.LEFT)
        cv.create_window(W-14,y0+30,window=close_fr,anchor=tk.E)

        # ── Log ───────────────────────────────────────────────────────────────
        log_fr=tk.Frame(self,bg="#050a15")
        self._log=tk.Text(log_fr,font=("Consolas",7),
                          bg="#050a15",fg="#3a6080",
                          relief=tk.FLAT,bd=0,
                          state=tk.DISABLED,wrap=tk.WORD,height=4)
        sb=tk.Scrollbar(log_fr,command=self._log.yview,
                        bg="#0d1628",troughcolor="#050a15")
        self._log.config(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT,fill=tk.Y)
        self._log.pack(fill=tk.BOTH,expand=True)
        cv.create_window(14,y0+42,window=log_fr,anchor=tk.NW,
                         width=W-28,height=66)

        # Lanzar ping al servidor en background
        self.after(800,self._check_server)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _log_line(self,msg):
        def _d():
            self._log.config(state=tk.NORMAL)
            self._log.insert(tk.END,msg+"\n")
            self._log.see(tk.END)
            self._log.config(state=tk.DISABLED)
        self.after(0,_d)

    def _set_status(self,msg):
        self.after(0,lambda:self.cv.itemconfig(self._status_id,text=msg))

    def _set_prog(self,pct):
        def _d():
            sx=self._cv_w/W; sy=self._cv_h/H
            y0s=int((H-120)*sy)
            x0=int(15*sx)
            x1=x0+int((W-30)*sx*min(pct,100)/100)
            self.cv.coords(self._prog_fill,x0,y0s+int(6*sy),x1,y0s+int(20*sy))
            self.cv.itemconfig(self._prog_pct,
                               text=f"{pct:.0f}%" if pct>0 else "")
        self.after(0,_d)

    def _select_ver(self,key):
        self._ver=key; self.cfg["version"]=key; save_cfg(self.cfg)
        for w in self._ver_fr.winfo_children(): w.destroy()
        for k,ver in VERSIONS_CFG.items():
            active=k==self._ver
            tk.Button(self._ver_fr,text=ver["tag"],
                      font=("Consolas",8,"bold" if active else "normal"),
                      bg=GOLD if active else "#141e30",
                      fg=BLACK if active else TEXT_DIM,
                      relief=tk.FLAT,padx=10,pady=3,cursor="hand2",
                      bd=0,command=lambda kk=k:self._select_ver(kk)
                      ).pack(side=tk.LEFT,padx=2)

    def _go_back(self):
        self.master.show_login()
        self.destroy()

    def _open_skin_window(self):
        game_dir=VERSIONS_CFG[self._ver]["game_dir"]
        name=self._ms_creds["username"] if self._ms_creds else self._username
        SkinWindow(self, game_dir, username=name or "Steve")

    def _open_settings(self):
        win=tk.Toplevel(self); win.title("Configuración")
        win.geometry("420x160"); win.configure(bg="#0b1525"); win.resizable(False,False)
        ver=self._ver
        tk.Label(win,text=f"Carpeta de instalación ({ver}):",
                 font=("Consolas",9),bg="#0b1525",fg=TEXT_DIM
                 ).pack(anchor=tk.W,padx=16,pady=(16,4))
        dvar=tk.StringVar(value=VERSIONS_CFG[ver]["game_dir"])
        tk.Entry(win,textvariable=dvar,font=("Consolas",9),width=44,
                 bg="#0d1828",fg=GOLD,relief=tk.FLAT,
                 highlightthickness=2,highlightbackground="#2a4070"
                 ).pack(padx=16,ipady=4)
        def _save():
            VERSIONS_CFG[ver]["game_dir"]=dvar.get(); win.destroy()
        tk.Button(win,text="Guardar",command=_save,
                  font=("Consolas",10,"bold"),
                  bg=GOLD,fg=BLACK,relief=tk.FLAT,padx=16,pady=6,
                  cursor="hand2").pack(pady=14)

    def _open_store(self):
        import webbrowser; webbrowser.open("https://cobbleversemmo.tebex.io")
    def _open_discord(self):
        import webbrowser; webbrowser.open("https://discord.gg/atTNKrR8eb")
    def _open_tiktok(self):
        import webbrowser; webbrowser.open("https://www.tiktok.com/@cobbleversemmo.net")
    def _open_mods(self):
        d=Path(VERSIONS_CFG[self._ver]["game_dir"])/"mods"
        d.mkdir(parents=True,exist_ok=True); os.startfile(str(d))

    # ── Update / Play ─────────────────────────────────────────────────────────

    def _on_update(self):
        if self._thread and self._thread.is_alive(): return
        self._ready=False; self._cancel_ev.clear()
        self._btn_upd.disable(); self._btn_play.disable()
        self._btn_play.set_text("  Actualizando...")
        self._btn_cancel.show()
        self._set_prog(0)
        self._thread=threading.Thread(target=self._worker,daemon=True)
        self._thread.start()

    def _on_play(self):
        if self._thread and self._thread.is_alive(): return
        if not self._ready:
            self._cancel_ev.clear()
            self._btn_play.disable()
            self._btn_play.set_text("  Preparando...")
            self._btn_cancel.show()
            self._set_prog(0)
            self._thread=threading.Thread(target=self._worker,
                                          args=(True,),daemon=True)
            self._thread.start()
        else:
            self._launch()

    def _on_cancel(self):
        self._cancel_ev.set()
        self._btn_cancel.hide()
        self._log_line("  Cancelando...")
        self._set_status("Cancelado.")

    def _worker(self, launch_after=False):
        try:
            ver_cfg=VERSIONS_CFG[self._ver]
            game_dir=Path(ver_cfg["game_dir"])
            game_dir.mkdir(parents=True,exist_ok=True)

            # 1. Modpack
            self._log_line(f"\n[ {ver_cfg['name']} ] verificando archivos...")
            self._set_status("Obteniendo manifest...")
            try:
                manifest=fetch_manifest(ver_cfg["manifest"])
            except Exception as e:
                self._log_line(f"  Error: {e}")
                self._set_status("Error de red.")
                self._restore(); return

            pending=pending_files(manifest,game_dir)
            if pending:
                sz=fmt_bytes(sum(e.get("size",0) for e in pending))
                self._log_line(f"  {len(pending)} archivos ({sz}) — descargando...")
                errs=dl_parallel(pending,game_dir,
                                 on_prog=lambda p:self._set_prog(p*0.35),
                                 on_log=self._log_line,
                                 cancel_ev=self._cancel_ev,workers=16)
                if self._cancel_ev.is_set():
                    self._log_line("  Descarga cancelada.")
                    self._restore(); return
                if errs:
                    for p,e in errs: self._log_line(f"  ! {p}: {e}")
            else:
                self._log_line("  Modpack al dia.")
            self._set_prog(35)

            # 2. Minecraft
            self._log_line(f"\n[ Minecraft {MC_VERSION} ]")
            self._set_status(f"Verificando Minecraft...")
            inst=[v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(str(MC_DIR))]
            if MC_VERSION not in inst:
                self._log_line("  Descargando (solo la primera vez)...")
                minecraft_launcher_lib.install.install_minecraft_version(
                    version=MC_VERSION,minecraft_directory=str(MC_DIR),
                    callback={"setStatus":lambda s:self._set_status(s),
                              "setProgress":lambda v:None,"setMax":lambda v:None})
            else:
                self._log_line("  OK.")
            self._set_prog(60)

            # 3. Fabric
            self._log_line("\n[ Fabric Loader ]")
            loader=latest_fabric(); fab_id=f"fabric-loader-{loader}-{MC_VERSION}"
            inst2=[v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(str(MC_DIR))]
            if fab_id not in inst2:
                self._log_line(f"  Instalando Fabric {loader}...")
                minecraft_launcher_lib.fabric.install_fabric(
                    minecraft_version=MC_VERSION,minecraft_directory=str(MC_DIR),
                    loader_version=loader,
                    callback={"setStatus":lambda s:self._set_status(s),
                              "setProgress":lambda v:None,"setMax":lambda v:None})
            else:
                self._log_line("  OK.")
            self._set_prog(80)

            # 4. Java
            java=find_java()
            if not java:
                self._log_line("\n[ Java 21 ] instalando...")
                minecraft_launcher_lib.runtime.install_jvm_runtime(
                    jvm_version="java-runtime-delta",minecraft_directory=str(MC_DIR),
                    callback={"setStatus":lambda s:self._set_status(s),
                              "setProgress":lambda v:None,"setMax":lambda v:None})
                java=find_java() or "java"

            # 5. Auth
            if self._auth=="premium" and self._ms_creds:
                creds=self._ms_creds
            elif self._auth=="premium":
                creds=vanilla_auth() or offline_creds(self._username or "Jugador")
            else:
                creds=offline_creds(self._username)
            self._log_line(f"\n  Cuenta: {creds['username']}")
            self._set_prog(100)

            self._ldata={"fab_id":fab_id,"game_dir":str(game_dir),
                          "java":java,"creds":creds}
            self._log_line("  Listo para jugar.")
            self._set_status("¡Listo!")
            self._ready=True

            def _ok():
                self._btn_upd.enable()
                self._btn_play.enable()
                self._btn_play.set_text("  JUGAR")
                self._btn_play.set_color(TEAL)
                self._btn_cancel.hide()
            self.after(0,_ok)

            if launch_after: self._launch()

        except Exception as ex:
            import traceback
            self._log_line(f"\nError: {ex}")
            self._set_status("Error.")
            self._restore()

    def _restore(self):
        def _d():
            self._btn_upd.enable()
            self._btn_play.enable()
            self._btn_play.set_text("  JUGAR")
            self._btn_cancel.hide()
            self._btn_close_mc.hide()
        self.after(0,_d)

    def _check_server(self):
        import socket
        def _ping():
            try:
                s=socket.create_connection((SERVER_HOST,SERVER_PORT),timeout=3)
                s.close(); online=True
            except: online=False
            self.after(0,lambda:self._set_srv_status(online))
            self.after(30000,self._check_server)
        threading.Thread(target=_ping,daemon=True).start()

    def _set_srv_status(self,online):
        try:
            color="#00cc55" if online else "#cc3333"
            label=f"Online — {SERVER_HOST}" if online else "Offline"
            self.cv.itemconfig(self._srv_dot,fill=color)
            self.cv.itemconfig(self._srv_txt,text=label,
                               fill="#00cc55" if online else "#cc3333")
        except: pass

    def _launch(self):
        if not self._ldata: return
        d=self._ldata
        try:
            opts={
                "username":d["creds"]["username"],
                "uuid":d["creds"]["uuid"],
                "token":d["creds"]["token"],
                "userType":d["creds"].get("user_type","legacy"),
                "gameDirectory":d["game_dir"],
                "jvmArguments":["-Xmx4G","-Xms1G","-XX:+UseG1GC",
                                 "-XX:+ParallelRefProcEnabled"],
                "executablePath":d["java"],
                "launcherName":"CobbleverseMMO",
                "launcherVersion":APP_VERSION,
            }
            cmd=minecraft_launcher_lib.command.get_minecraft_command(
                version=d["fab_id"],minecraft_directory=str(MC_DIR),options=opts)
            self._log_line("\n▶ Lanzando Minecraft...")
            self._btn_play.disable()
            self._btn_play.set_text("  Jugando...")
            self._btn_cancel.hide()
            self._mc_proc=subprocess.Popen(cmd,cwd=d["game_dir"],creationflags=NOWND)
            self._btn_close_mc.show()
            if self._close_after.get():
                self.after(3000,self.master.destroy)
        except Exception as ex:
            messagebox.showerror("Error al lanzar",str(ex))
            self._restore()

    def _on_close_mc(self):
        if self._mc_proc and self._mc_proc.poll() is None:
            self._mc_proc.terminate()
            self._log_line("  Minecraft cerrado.")
        self._mc_proc=None
        self._btn_close_mc.hide()
        self._btn_play.enable()
        self._btn_play.set_text("  JUGAR")
        self._set_status("Listo.")

# ─────────────────────────────────────────────────────────────────────────────
#  App
# ─────────────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CobbleverseMMO Launcher")
        self.geometry(f"{W}x{H}")
        self.minsize(W, H)
        self.resizable(True, True)
        self.configure(bg=DARK_BG)
        self._screen=None
        self.show_login()

    def show_login(self):
        if self._screen: self._screen.destroy()
        self._screen=LoginScreen(self,self._on_login)
        self._screen.pack(fill=tk.BOTH,expand=True)

    def _on_login(self,auth,username,ms_creds=None):
        if self._screen: self._screen.destroy()
        self._screen=MainLauncher(self,auth,username,ms_creds=ms_creds)
        self._screen.pack(fill=tk.BOTH,expand=True)

if __name__=="__main__":
    App().mainloop()
