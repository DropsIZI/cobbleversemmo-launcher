/* CobbleverseMMO Launcher — front-end controller (pywebview bridge) */
(function () {
  "use strict";

  // hover feedback for inline-styled buttons (inline styles can't carry :hover)
  var st = document.createElement("style");
  st.textContent =
    ".hov{transition:filter .15s,transform .15s,background .15s}" +
    ".hov:hover{filter:brightness(1.14)}" +
    "[data-hover-close]:hover{background:#cc2b2b!important;color:#fff!important;filter:none}" +
    "#presetList button:hover{filter:brightness(1.1)}";
  document.head.appendChild(st);

  var $ = function (id) { return document.getElementById(id); };

  var state = {
    loggedIn: false,
    premium: false,
    username: "",
    versions: [],
    versionIndex: 0,
    ram: 6,
    ready: false,
    playing: false,
    news: [],
    newsIndex: 0,
    newsOpen: true,
    skin: { head: null, body: null, source: null },
    appVersion: "1.0.0",
    bg: null,
    logo: null,
    cornerIcon: null,
    installDir: "",
    java: "",
  };

  // ── skin figures (real Minecraft skin rendered by Python → PNG data URIs) ────
  function applySkinImages() {
    var head = $("headAvatarImg");
    if (head) head.src = state.skin.head || "";
    [["skinFigureSm", 150], ["skinFigureLg", 250]].forEach(function (pair) {
      var el = $(pair[0]);
      if (!el || !state.skin.body) return;
      el.innerHTML = "<img alt='' style='height:" + pair[1] + "px;width:auto;image-rendering:pixelated;filter:drop-shadow(0 8px 14px rgba(0,0,0,.45))' src='" + state.skin.body + "'>";
    });
    var lbl = $("skinPresetName");
    if (lbl) lbl.textContent = state.skin.source === "premium" ? "Skin de tu cuenta"
      : state.skin.source === "custom" ? "Skin personalizada" : "Skin por defecto";
  }

  // ── starfield ──────────────────────────────────────────────────────────────
  function renderStars() {
    // Kept light for WebView2: fewer stars, no animated box-shadow (which forces
    // a full repaint every frame). Twinkle is opacity-only.
    var box = $("stars"); var html = "";
    for (var i = 0; i < 70; i++) {
      var gold = Math.random() < 0.24;
      var size = (1.2 + Math.random() * 1.6).toFixed(2);
      var top = (Math.random() * 100).toFixed(2);
      var left = (Math.random() * 100).toFixed(2);
      var dur = (2.4 + Math.random() * 3).toFixed(2);
      var del = (Math.random() * 4).toFixed(2);
      html += "<span style=\"position:absolute;top:" + top + "%;left:" + left + "%;width:" + size + "px;height:" + size +
        "px;border-radius:50%;background:" + (gold ? "#f4d77a" : "#fff") +
        ";opacity:.4;will-change:opacity;animation:cvtwinkle " + dur + "s ease-in-out " + del + "s infinite\"></span>";
    }
    box.innerHTML = html;
  }

  // ── news ─────────────────────────────────────────────────────────────────────
  function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

  function renderNews() {
    var track = $("newsTrack");
    var dots = $("newsDots");
    if (!state.news.length) {
      track.innerHTML = "<div style=\"min-width:100%;display:flex;align-items:center;justify-content:center;color:rgba(255,255,255,.4);font-size:13px\">No hay noticias por ahora.</div>";
      dots.innerHTML = ""; return;
    }
    var html = "";
    state.news.forEach(function (item, idx) {
      var thumb = item.image
        ? "background-image:url('" + esc(item.image) + "');background-size:cover;background-position:center"
        : "background:linear-gradient(135deg,#14323f,#2e2611)";
      html += "<article onclick=\"cv.openLightbox(" + idx + ")\" title=\"Ver noticia completa\" class=\"hov\" style=\"min-width:100%;height:100%;display:flex;gap:14px;align-items:stretch;padding:8px;border-radius:13px;cursor:pointer;border:1px solid transparent\">" +
        "<div style=\"position:relative;flex:none;align-self:center;width:150px;aspect-ratio:4/3;border-radius:11px;overflow:hidden;border:1px solid rgba(212,175,55,.28);" + thumb + "\">" +
        (item.image ? "" : "<div style=\"position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:ui-monospace,monospace;font-size:10px;color:rgba(255,255,255,.4)\">[ miniatura ]</div>") +
        "</div>" +
        "<div style=\"flex:1;display:flex;flex-direction:column;justify-content:center;min-width:0\">" +
        "<div style=\"display:flex;align-items:center;gap:9px;margin-bottom:7px\">" +
        "<span style=\"font-family:'Chakra Petch',sans-serif;font-size:9px;font-weight:700;letter-spacing:1.1px;color:#1a1407;background:#d4af37;padding:3px 8px;border-radius:5px\">" + esc(item.tag || "NOTICIA") + "</span>" +
        "<span style=\"font-size:10.5px;color:rgba(255,255,255,.45);font-weight:600\">" + esc(item.date || "") + "</span></div>" +
        "<h3 style=\"font-family:'Chakra Petch',sans-serif;font-size:17px;font-weight:700;line-height:1.18;margin-bottom:7px\">" + esc(item.title || "") + "</h3>" +
        "<p style=\"font-size:12px;line-height:1.55;color:rgba(255,255,255,.66);max-width:380px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical\">" + esc(item.text || item.description || "") + "</p>" +
        "<span style=\"align-self:flex-start;margin-top:11px;display:flex;align-items:center;gap:6px;font-size:11px;font-weight:700;color:#6fd3ec;padding:6px 12px;border-radius:8px;background:rgba(43,184,217,.12);border:1px solid rgba(43,184,217,.25)\">Leer más " +
        "<svg width=\"12\" height=\"12\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><line x1=\"5\" y1=\"12\" x2=\"19\" y2=\"12\"></line><polyline points=\"12 5 19 12 12 19\"></polyline></svg></span>" +
        "</div></article>";
    });
    track.innerHTML = html;
    track.style.transform = "translateX(-" + (state.newsIndex * 100) + "%)";

    var d = "";
    state.news.forEach(function (_, i) {
      var on = i === state.newsIndex;
      d += "<button onclick=\"cv.goNews(" + i + ")\" style=\"width:" + (on ? "24px" : "8px") + ";height:8px;border-radius:4px;cursor:pointer;border:none;background:" +
        (on ? "#d4af37" : "rgba(255,255,255,.25)") + ";box-shadow:" + (on ? "0 0 10px rgba(244,215,122,.6)" : "none") + ";transition:all .3s\"></button>";
    });
    dots.innerHTML = d;
  }

  // ── version dropdown ─────────────────────────────────────────────────────────
  function renderVersionMenu() {
    var menu = $("versionMenu"); var html = "";
    state.versions.forEach(function (v, i) {
      var sel = i === state.versionIndex;
      html += "<button onclick=\"cv.selectVersion(" + i + ")\" class=\"hov\" style=\"display:flex;flex-direction:column;gap:2px;width:100%;text-align:left;padding:10px 13px;border-radius:9px;border:none;cursor:pointer;background:" +
        (sel ? "rgba(212,175,55,.25)" : "transparent") + "\">" +
        "<span style=\"font-size:13px;font-weight:" + (sel ? 700 : 600) + ";color:" + (sel ? "#fff" : "rgba(255,255,255,.78)") + "\">" + esc(v.label) + "</span>" +
        "<span style=\"font-size:10.5px;font-weight:600;color:" + (sel ? "rgba(244,215,122,.9)" : "rgba(255,255,255,.4)") + "\">" + esc(v.sub) + "</span></button>";
    });
    menu.innerHTML = html;
    var cur = state.versions[state.versionIndex];
    $("currentVersion").textContent = cur ? cur.label : "—";
  }

  // ── auth / overall UI sync ───────────────────────────────────────────────────
  function syncAuthUI() {
    $("userCard").classList.toggle("hidden", !state.loggedIn);
    $("noSession").classList.toggle("hidden", state.loggedIn);
    $("playBtn").classList.toggle("hidden", !state.loggedIn);
    $("loginBtn").classList.toggle("hidden", state.loggedIn);
    $("loginScreen").classList.toggle("hidden", state.loggedIn);

    $("topUsername").textContent = state.username || "";
    $("topConn").textContent = state.premium ? "● Conectado" : "● Modo offline";
    $("topConn").style.color = state.premium ? "#2ed573" : "#ffa502";

    $("skinUsername").textContent = state.username || "Jugador";

    var badge = $("skinBadge");
    if (state.premium) {
      badge.textContent = "PREMIUM";
      badge.style.cssText = "font-family:'Chakra Petch',sans-serif;font-size:8.5px;font-weight:700;letter-spacing:.8px;color:#1a1407;background:#d4af37;padding:3px 7px;border-radius:5px";
    } else {
      badge.textContent = "OFFLINE";
      badge.style.cssText = "font-family:'Chakra Petch',sans-serif;font-size:8.5px;font-weight:700;letter-spacing:.8px;color:rgba(255,255,255,.6);background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);padding:2px 6px;border-radius:5px";
    }
    $("skinLock").classList.toggle("hidden", state.premium);
    $("skinEditBtn").classList.toggle("hidden", !state.premium);
    $("skinLockBtn").classList.toggle("hidden", state.premium);
  }

  function setRam(gb) {
    state.ram = gb;
    $("ramVal").textContent = gb;
    $("ramSetVal").textContent = gb;
    $("ramSlider").value = gb;
  }

  // ── pywebview bridge helpers ─────────────────────────────────────────────────
  function api() { return (window.pywebview && window.pywebview.api) || null; }
  function call(name) {
    var args = Array.prototype.slice.call(arguments, 1);
    var a = api();
    if (!a || typeof a[name] !== "function") return Promise.resolve(null);
    return a[name].apply(a, args);
  }

  // ── public controller (cv.*) ─────────────────────────────────────────────────
  var cv = {
    // login
    showLogin: function () { state.loggedIn = false; syncAuthUI(); },
    loginPremium: function () {
      $("premiumStatus").textContent = "Abriendo ventana de Microsoft...";
      $("premiumBtn").disabled = true;
      call("login_premium");
    },
    loginOffline: function () {
      var name = ($("offlineUser").value || "").trim();
      if (!name) { $("offlineUser").focus(); return; }
      call("login_offline", name);
    },
    logout: function () { call("logout"); state.loggedIn = false; state.premium = false; state.ready = false; state.skin = { head: null, body: null, source: null }; syncAuthUI(); cv.setProgress(0, "Inicia sesión para jugar"); },

    // play
    play: function () { if (state.playing) return; call("play"); },
    cancel: function () { call("cancel_play"); },
    playOrCancel: function () { if (state.playing) cv.cancel(); else cv.play(); },

    // version
    toggleVersion: function () { $("versionMenu").classList.toggle("hidden"); },
    selectVersion: function (i) {
      state.versionIndex = i;
      $("versionMenu").classList.add("hidden");
      renderVersionMenu();
      state.ready = false;
      call("set_version", i).then(function (r) {
        if (r && typeof r.ram === "number") setRam(r.ram);
        if (r && r.installDir) { state.installDir = r.installDir; $("installPath").value = r.installDir; }
      });
    },

    // news
    toggleNews: function () {
      state.newsOpen = !state.newsOpen;
      $("newsBody").style.display = state.newsOpen ? "flex" : "none";
      $("newsChevron").style.transform = state.newsOpen ? "rotate(0deg)" : "rotate(180deg)";
    },
    goNews: function (i) { state.newsIndex = i; renderNews(); },
    nextNews: function () { if (state.news.length) { state.newsIndex = (state.newsIndex + 1) % state.news.length; renderNews(); refreshLightbox(); } },
    prevNews: function () { if (state.news.length) { state.newsIndex = (state.newsIndex - 1 + state.news.length) % state.news.length; renderNews(); refreshLightbox(); } },
    openLightbox: function (i) { state.newsIndex = i; renderNews(); $("lightbox").classList.remove("hidden"); refreshLightbox(); },
    closeLightbox: function (e) { if (e && e.target.closest && e.target.closest("div[onclick='event.stopPropagation()']")) return; $("lightbox").classList.add("hidden"); },

    // skin
    openSkinEditor: function () { if (!state.premium) return; applySkinImages(); $("skinUploadInfo").textContent = ""; $("skinEditor").classList.remove("hidden"); },
    closeSkinEditor: function (e) { if (e && e.type === "click" && e.target !== $("skinEditor")) return; $("skinEditor").classList.add("hidden"); },
    applySkin: function () { $("skinEditor").classList.add("hidden"); },
    uploadSkin: function () {
      $("skinUploadInfo").textContent = "Selecciona un archivo...";
      call("upload_skin").then(function (msg) { $("skinUploadInfo").textContent = msg || ""; });
    },

    // settings
    openSettings: function () { $("installPath").value = state.installDir || ""; $("javaPath").value = state.java || "(se instalará al jugar)"; $("settings").classList.remove("hidden"); },
    closeSettings: function (e) { if (e && e.type === "click" && e.target !== $("settings")) return; $("settings").classList.add("hidden"); },
    onRamSlide: function (v) { setRam(Number(v)); },
    saveSettings: function () { call("set_ram", state.ram); $("settings").classList.add("hidden"); },
    browseJava: function () { call("browse_java").then(function (p) { if (p) { state.java = p; $("javaPath").value = p; } }); },
    openMods: function () { call("open_mods"); },
    openShaders: function () { call("open_shaders"); },
    browseInstall: function () { call("open_install"); },

    // misc
    openUrl: function (kind) { call("open_url", kind); },
    minimize: function () { call("minimize"); },
    closeApp: function () { call("close_app"); },

    // ── callbacks invoked from Python ──────────────────────────────────────────
    setProgress: function (pct, label) {
      pct = Math.max(0, Math.min(100, pct));
      $("progressBar").style.width = pct + "%";
      $("progressPct").textContent = Math.round(pct) + "%";
      if (label != null) $("progressLabel").textContent = label;
    },
    onPlaying: function (playing) {
      state.playing = playing;
      var btn = $("playBtn");
      btn.style.cursor = "pointer";
      if (playing) {
        $("playLabel").textContent = "CANCELAR";
        btn.style.background = "linear-gradient(135deg,#e0584f,#a31f1f)";
        btn.style.boxShadow = "0 10px 32px rgba(204,43,43,.5),inset 0 1px 0 rgba(255,255,255,.2)";
        // spinner (actividad) + se entiende que al pulsar se cancela
        $("playIcon").outerHTML = "<span id=\"playIcon\" style=\"width:19px;height:19px;border-radius:50%;border:3px solid rgba(255,255,255,.35);border-top-color:#fff;animation:cvspin .8s linear infinite\"></span>";
      } else {
        $("playLabel").textContent = "JUGAR";
        btn.style.background = "linear-gradient(135deg,#e8c75a,#b8901f)";
        btn.style.boxShadow = "0 10px 32px rgba(212,175,55,.5),inset 0 1px 0 rgba(255,255,255,.25)";
        $("playIcon").outerHTML = "<svg id=\"playIcon\" width=\"22\" height=\"22\" viewBox=\"0 0 24 24\" fill=\"#fff\"><polygon points=\"6 4 20 12 6 20 6 4\"></polygon></svg>";
      }
    },
    onReady: function () { state.ready = true; cv.setProgress(100, "¡Listo para jugar!"); $("updatedTag").textContent = "✓ Actualizado"; },
    onMsStatus: function (msg, ok) {
      $("premiumStatus").textContent = msg || "";
      $("premiumStatus").style.color = ok ? "#2ed573" : "#6fd3ec";
      if (msg && /error|cancel/i.test(msg)) { $("premiumBtn").disabled = false; $("premiumStatus").style.color = "#ff6b6b"; }
    },
    onLogin: function (data) {
      state.loggedIn = !!data.loggedIn;
      state.premium = !!data.premium;
      state.username = data.username || "";
      $("premiumBtn").disabled = false;
      $("premiumStatus").textContent = "";
      if (typeof data.ram === "number") setRam(data.ram);
      syncAuthUI();
      cv.setProgress(state.ready ? 100 : 0, state.ready ? "¡Listo para jugar!" : "Pulsa JUGAR para verificar archivos");
    },
    onNews: function (list) { state.news = list || []; state.newsIndex = 0; renderNews(); },
    onJava: function (path) { state.java = path || ""; $("javaPath").value = path || "(se instalará al jugar)"; },
    onSkin: function (data) {
      if (!data) return;
      state.skin = { head: data.head || null, body: data.body || null, source: data.source || null };
      applySkinImages();
    },

    // bootstrap
    init: function (data) {
      Object.keys(data || {}).forEach(function (k) { state[k] = data[k]; });
      renderStars();
      var logo = state.logo || state.bg;
      if (logo) {
        $("bgwatermark").style.backgroundImage = "url('" + logo + "')";
        $("loginLogo").src = logo;
        $("splashLogo").src = logo;
      }
      if (state.cornerIcon) $("cornerIcon").src = state.cornerIcon;
      $("footVersion").textContent = "Launcher v" + state.appVersion;
      $("loginVer").textContent = "CobbleverseMMO Launcher · v" + state.appVersion;
      setRam(state.ram);
      renderVersionMenu();
      renderNews();
      syncAuthUI();
      $("javaPath").value = state.java || "(se instalará al jugar)";
      $("installPath").value = state.installDir || "";
      cv.setProgress(state.loggedIn ? (state.ready ? 100 : 0) : 0,
        state.loggedIn ? (state.ready ? "¡Listo para jugar!" : "Pulsa JUGAR para verificar archivos") : "Inicia sesión para jugar");
      // hide the loading splash now that the UI is ready
      var sp = $("splash");
      if (sp) { sp.style.opacity = "0"; setTimeout(function () { sp.style.display = "none"; }, 480); }
    },
  };

  function refreshLightbox() {
    if ($("lightbox").classList.contains("hidden")) return;
    var item = state.news[state.newsIndex] || {};
    $("lbTag").textContent = item.tag || "NOTICIA";
    $("lbDate").textContent = item.date || "";
    $("lbTitle").textContent = item.title || "";
    $("lbImage").style.backgroundImage = item.image ? "url('" + item.image + "')" : "";
    var body = item.body && item.body.length ? item.body : [item.text || item.description || ""];
    $("lbBody").innerHTML = body.map(function (p) {
      return "<p style=\"font-size:14px;line-height:1.7;color:rgba(255,255,255,.74)\">" + esc(p) + "</p>";
    }).join("");
  }

  window.cv = cv;

  // pywebview is ready → ask Python for initial state.
  // Only initialise once, and only with a valid payload (the api may not be
  // bound yet on the first event, in which case call() resolves to null).
  // get_initial is pure/idempotent on the Python side, so it's safe to retry.
  // We keep polling until the api is injected AND a call actually resolves with
  // a valid payload (the bridge can take a moment to be fully ready), then init
  // once and start the background tasks.
  var booted = false;
  function boot() {
    if (booted) return;
    var a = window.pywebview && window.pywebview.api;
    if (!a || typeof a.get_initial !== "function") {
      setTimeout(boot, 200);
      return;
    }
    a.get_initial().then(function (data) {
      if (booted) return;
      if (data && data.versions && data.versions.length) {
        booted = true;
        cv.init(data);
        if (a.start_background) a.start_background();
      } else {
        setTimeout(boot, 250);
      }
    });
    // safety re-arm in case the first promise stalls before the bridge is ready
    setTimeout(function () { if (!booted) boot(); }, 1500);
  }
  window.addEventListener("pywebviewready", boot);
  boot();
})();
