# Compartir el panel en Streamlit Community Cloud

Guía para publicar el Lector de boletas SSBB como un sitio web, gratis, al que la
gente entra con un link (sin instalar nada). Toma ~15 minutos la primera vez.

## Qué ya quedó preparado en esta carpeta
- `app/` — la aplicación.
- `requirements.txt` — librerías de Python (se instalan solas).
- `packages.txt` — instala **Tesseract** (OCR) con idioma español en el servidor.
- `.gitignore` — evita subir las boletas reales y los Excel a GitHub.

## Requisitos
- Una cuenta de **GitHub** (gratis).
- La cuenta de **Streamlit Community Cloud** (gratis, se entra con GitHub):
  https://share.streamlit.io

## Paso 1 — Subir el proyecto a GitHub (repo PRIVADO)
> Importante: el repo debe ser **privado**. El `.gitignore` ya excluye las boletas,
> pero igual conviene mantenerlo privado.

Desde esta carpeta (`11.- Lector boletas SSBB`), en una terminal:
```
git init
git add .
git commit -m "Lector boletas SSBB"
```
Luego crea un repositorio privado en GitHub y súbelo. Con GitHub CLI (`gh`):
```
gh repo create lector-boletas-ssbb --private --source . --push
```
(O crea el repo a mano en github.com y sigue las instrucciones de "push existing repository".)

## Paso 2 — Desplegar en Streamlit Cloud
1. Entra a https://share.streamlit.io y conéctate con GitHub.
2. Botón **Create app** → **Deploy a public app from GitHub** (luego lo hacemos privado).
3. Completa:
   - **Repository:** `tu-usuario/lector-boletas-ssbb`
   - **Branch:** `main`
   - **Main file path:** `app/app.py`
4. **Deploy**. La primera vez tarda unos minutos (instala Python, las librerías y Tesseract).
   Cuando termine, tendrás una URL tipo `https://lector-boletas-ssbb.streamlit.app`.

## Paso 3 — Restringir el acceso a LAR (recomendado)
Para que no sea público:
1. En el panel de Streamlit Cloud, abre tu app → **Settings** (⚙️) → **Sharing**.
2. En "Who can view this app" elige **Specific people** / invita por correo a quienes
   deban usarlo (correos `@largroup.cl`). Cada persona entra con su login y listo.

## Uso
Comparte la URL. Cada quien:
1. Elige el formato (Aguas / Rendición Enel).
2. Sube las boletas (PDF) y, para Aguas, las capturas.
3. Procesa, revisa la tabla y descarga el Excel.

## Actualizar la app más adelante
Cualquier cambio: `git add . && git commit -m "ajuste" && git push`.
Streamlit Cloud **redepliega solo** al detectar el push.

## Notas
- El OCR de capturas funciona en el servidor gracias a `packages.txt`. Si algún día
  no reconcilia, revisa que ese archivo siga en el repo.
- Los archivos que sube la gente se procesan en memoria y no quedan guardados en el
  repositorio.
- Si más adelante quieres alojarlo **dentro** de LAR con login corporativo (Entra ID)
  en vez de Streamlit Cloud, se puede migrar a Azure App Service con el mismo código.
