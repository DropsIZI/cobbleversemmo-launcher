# Guía del equipo — CobbleverseMMO

Cómo colaborar para **añadir mods, datapacks, resource packs (texturas/Pokémon nuevos)
y publicar noticias/eventos** en el launcher.

---

## 1. Cómo está montado (2 repositorios + Releases)

| Repositorio | Qué contiene | Para qué |
|---|---|---|
| **`cobbleversemmo-launcher`** | El código del launcher (este proyecto) + herramientas (`generate_manifest.py`) | Solo se toca para cambiar el launcher en sí |
| **`cobbleversemmo-modpack`** | `manifests/`, `configs/`, **`news.json`**, `news/images/` | El launcher lo lee **en vivo** |
| **GitHub Releases** de `cobbleversemmo-modpack` (tags `v1.5-normal`, `v1.5-lite`) | Los archivos pesados: **mods, datapacks, resourcepacks, shaders** | El launcher los descarga al pulsar JUGAR |

> El launcher NO trae los mods dentro. Lee `manifests/normal.json` y `lite.json`, compara con lo que el jugador tiene, y descarga lo que falte desde los Releases. Por eso **actualizar el modpack = actualizar el manifest + subir los archivos nuevos al Release**.

La carpeta `github-repo/` dentro del launcher es la copia local del repo `cobbleversemmo-modpack`.

---

## 2. Quién hace qué

| Tarea | Necesita | Dificultad |
|---|---|---|
| **Publicar noticias/eventos** | Solo editar `news.json` + push | 🟢 Fácil (cualquiera) |
| **Añadir/quitar mods, datapacks, resourcepacks, shaders** | El perfil de Modrinth + `gh` CLI + permiso de push | 🟡 Media (encargado del modpack) |
| **Cambiar el launcher** | Python + editar el código | 🔴 Avanzado |

Da acceso a tus compañeros en **GitHub → repo → Settings → Collaborators**.

---

## 3. Preparación (una sola vez por persona)

1. Instala **Git**: https://git-scm.com/
2. Clona el repo de contenido:
   ```bash
   git clone https://github.com/DropsIZI/cobbleversemmo-modpack.git
   ```
3. Solo si vas a tocar mods/datapacks/resourcepacks:
   - Instala **GitHub CLI**: https://cli.github.com/  →  luego `gh auth login`
   - Ten el **perfil de Modrinth** del modpack instalado (`COBBLEVERSEMMO 1.5` y/o `POTATOVERSEMMO 1.5`).

---

## 4. Publicar una noticia o evento (con imagen) 🟢

**La forma SIN instalar nada (desde el navegador):** entra a
https://github.com/DropsIZI/cobbleversemmo-modpack
→ abre `news.json` → botón ✏️ (editar) → añade tu noticia arriba → *Commit changes*.
Para imágenes: entra a la carpeta `news/images` → *Add file* → *Upload files* → arrastra
la imagen → *Commit*. (Solo necesitas cuenta de GitHub con acceso al repo.)

**La forma fácil en tu PC (sin terminal):** doble clic en **`Agregar-Noticia.bat`**.
Te hace unas preguntas, y al final te pregunta *"¿Subir a GitHub ahora?"* → pones `s`
y **se sube solo**. ¡Eso es todo! El launcher la muestra al instante.

Si la noticia lleva imagen: copia primero la imagen en la carpeta `news/images/` y,
cuando pregunte, escribe solo el nombre del archivo (ej. `evento-verano.png`).

> Lo mismo desde terminal: `python add_news.py`

**La forma manual:** edita `news.json` directamente. Cada noticia es:
```json
{
  "tag": "EVENTO",
  "date": "30 jun 2026",
  "title": "Título de la noticia",
  "text": "Resumen corto que sale en la tarjeta (1-2 frases).",
  "body": [
    "Primer párrafo del texto completo.",
    "Segundo párrafo.",
    "Tercer párrafo."
  ],
  "image": "https://raw.githubusercontent.com/DropsIZI/cobbleversemmo-modpack/main/news/images/evento-verano.png"
}
```
- Las noticias se muestran en el **orden del archivo** → pon las nuevas **arriba**.
- `image` puede quedar vacío (`""`) para una noticia sin foto.
- Detalles de imágenes en `news/images/README.md`.

---

## 5. Añadir mods / datapacks / resource packs

Hay **dos vías** según de dónde venga el contenido:

### 5A · Tu propio contenido (mods/datapacks/texturas que hiciste tú) — 🟢 cualquiera

Para contenido **propio del equipo** (no de Modrinth/CurseForge). **Sin instalar nada:**

1. Entra a https://github.com/DropsIZI/cobbleversemmo-modpack
2. Abre la carpeta:
   - **`extra/mods/`** → tus mods (`.jar`, Fabric 1.21.1)
   - **`extra/datapacks/`** → Pokémon/datapacks nuevos (`.zip`)
   - **`extra/resourcepacks/`** → texturas (`.zip`)
3. **Add file → Upload files** → arrastra tu archivo → **Commit changes**

¡Y ya! Un **robot (GitHub Action)** regenera la lista solo, y al siguiente **JUGAR**
todos los jugadores lo descargan. Varios compañeros pueden subir a la vez sin pisarse.
(Más detalles en `extra/README.md`.)

> Esto es para contenido **propio y ligero**. Aplica a **ambas** versiones (Normal y LITE).

### 5B · Mods grandes de Modrinth/CurseForge — 🟡 el encargado del modpack

Los mods pesados de terceros (Cobblemon, Sodium…) se gestionan con el perfil de Modrinth:

1. Modifica el modpack en **Modrinth App** (perfil `COBBLEVERSEMMO 1.5` y, si aplica, `POTATOVERSEMMO 1.5`):
   mods → `mods/`, datapacks → `datapacks/`, texturas → `resourcepacks/`, shaders → `shaderpacks/`
2. Doble clic en **`Publicar-Modpack.bat`** (o `python publicar_modpack.py`): regenera
   los manifests + sube a los Releases + `git push`, todo de golpe.

> Requisito una sola vez: GitHub CLI (`gh auth login`) y acceso al repo del modpack.

**En ningún caso hay que recompilar ni redistribuir el `.exe`** — el launcher lee todo en vivo.

> ⚠️ Si subes archivos **muy grandes** o muchos, el `gh release upload` puede tardar.
> Cada quien que haga esto debe tener el mismo perfil de Modrinth sincronizado, si no
> el manifest reflejaría su versión local. Por eso conviene que **una sola persona** (o
> turnos coordinados) gestione los binarios, y el resto haga noticias.

---

## 6. Trabajar en equipo sin pisarse (Git básico)

Antes de empezar a editar, **baja lo último**:
```bash
git pull
```
Después de tus cambios:
```bash
git add .
git commit -m "describe lo que hiciste"
git push
```

Si dos personas tocan lo mismo a la vez, Git avisará de un *conflicto*. Para evitarlo:
- **Noticias** y **modpack** son archivos distintos → rara vez chocan.
- Avisa en el Discord del equipo antes de subir binarios grandes.
- Para cambios grandes, usa una **rama** y un *Pull Request*:
  ```bash
  git checkout -b mi-cambio
  # ...editas, commit...
  git push -u origin mi-cambio
  # luego abre el Pull Request en GitHub
  ```

---

## 7. Resumen rápido

- **Noticia nueva** → `Agregar-Noticia.bat`, o subir a `news.json` desde github.com.
- **Tu propio mod/datapack/textura** → subir a la carpeta **`extra/`** en github.com (el robot hace el resto). 🟢 cualquiera, sin instalar nada.
- **Mods grandes de Modrinth** → editar perfil Modrinth → **`Publicar-Modpack.bat`** (el encargado).
- **Nada de esto necesita recompilar el `.exe`.** El launcher lee todo en vivo desde GitHub.
- El `.exe` solo se recompila si cambia el **código del launcher** (ver `README.md`).
