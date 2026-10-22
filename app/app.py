"""Interfaz Streamlit — Lector de boletas de Servicios Básicos (LAR Group).

Flujo: elegir formato -> subir boletas (PDF) y capturas (imágenes) -> Procesar ->
revisar la tabla con la reconciliación -> descargar el Excel del formato elegido.
"""
import io
import os
import sys
import shutil
import tempfile

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extractor import procesar_carpeta, _resumen
from salidas import ESCRITORES
from edificios import CONFIG

VERDE = "#08424D"
TEAL = "#00A8B4"
VERSION = "v1.2 · 2026-10-22 (FECHA CHECK IN: fecha o 'CORTE EN TRÁMITE')"

# Formatos de salida que ofrece la app y si usan capturas.
FORMATOS = {
    "Aguas Andinas — Consumo (todos los edificios)": ("aguas", True),
    "Rendición Servicios Básicos — Enel (SC-020)": ("rendicion", False),
}
ARCHIVO_SALIDA = {
    "aguas": "aguas_consumo.xlsx",
    "rendicion": "rendicion_servicios_basicos.xlsx",
}
IMG_EXT = ("png", "jpg", "jpeg", "webp", "bmp")


def _encabezado():
    st.markdown(
        f"""<style>
          header[data-testid="stHeader"] {{display: none;}}
          #MainMenu, footer {{visibility: hidden;}}
          .block-container {{padding-top: 1.4rem; padding-bottom: 2rem;}}
          .stButton > button, .stDownloadButton > button,
          [data-testid="stFileUploader"] button {{
            background: {TEAL}; color: #fff; border: 1px solid {TEAL};
            border-radius: 6px; font-weight: 600; padding: 6px 18px;
          }}
          .stButton > button:hover, .stDownloadButton > button:hover,
          [data-testid="stFileUploader"] button:hover {{
            background: {VERDE}; border-color: {VERDE}; color: #fff;
          }}
          .stButton > button:disabled {{
            background: #B5B5B5; border-color: #B5B5B5; color: #fff;
          }}
        </style>""",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'''<div style="background:{VERDE};border-radius:10px;padding:16px 22px;
        display:flex;align-items:center;gap:16px;margin-bottom:16px">
        <div style="background:{TEAL};height:50px;width:50px;border-radius:10px;
          display:flex;align-items:center;justify-content:center;font-size:26px">💧</div>
        <div>
          <div style="color:#fff;font-size:24px;font-weight:700;
          font-family:Segoe UI,Arial,sans-serif;line-height:1.15">
            Lector de boletas · Servicios Básicos</div>
          <div style="color:#9fd4da;font-size:13px;font-family:Segoe UI,Arial,sans-serif">
            LAR Group · Tesorería &nbsp;·&nbsp; Aguas Andinas y Enel → Excel</div>
        </div></div>''',
        unsafe_allow_html=True,
    )


def _auto_reconexion():
    """Si el equipo se suspende, Streamlit muestra 'Connection error'; esto refresca
    la página para reconectar con el programa (que sigue corriendo)."""
    components.html(
        """
        <script>
        (function () {
          var top = window.parent;
          function desconectado() {
            try {
              var t = top.document.body ? top.document.body.innerText : "";
              return /Connection error|Is Streamlit still running|Please wait/i.test(t);
            } catch (e) { return false; }
          }
          var fallos = 0;
          setInterval(function () {
            if (desconectado()) { if (++fallos >= 3) { try { top.location.reload(); } catch (e) {} } }
            else { fallos = 0; }
          }, 5000);
        })();
        </script>
        """,
        height=0,
    )


def _guardar_subidas(archivos, carpeta, exts=None):
    """Escribe los archivos subidos a disco conservando su nombre original."""
    n = 0
    for f in archivos or []:
        if exts and not f.name.lower().endswith(tuple("." + e for e in exts)):
            continue
        with open(os.path.join(carpeta, f.name), "wb") as fh:
            fh.write(f.getbuffer())
        n += 1
    return n


def _fecha(d):
    return d.strftime("%d-%m-%Y") if d else ""


def _tabla(filas):
    def recon(f):
        return {"OK": "✓ OK", "DIFERENCIA": "⚠ revisar", "SIN CAPTURA": "— sin captura",
                "SIN_OCR": "OCR no disp."}.get(f.get("estado_reconc"), f.get("estado_reconc", ""))
    data = [{
        "Archivo": f.get("archivo", ""),
        "Proveedor": f.get("proveedor", ""),
        "Tipo": f.get("tipo_doc", ""),
        "Folio": f.get("folio", ""),
        "Fecha": _fecha(f.get("fecha_emision")),
        "Depto": f.get("depto", ""),
        "N° cuenta": f.get("n_cuenta", ""),
        "Monto": f.get("monto"),
        "Monto captura": f.get("monto_captura"),
        "Lectura": f.get("estado", ""),
        "Captura": recon(f),
    } for f in filas]
    return pd.DataFrame(data)


# ── App ───────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Boletas SSBB · LAR", page_icon="💧", layout="wide")
_encabezado()
_auto_reconexion()
st.caption(VERSION)

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0
k = st.session_state["uploader_key"]

col_fmt, col_info = st.columns([2, 3])
etiqueta = col_fmt.selectbox("Formato de salida", list(FORMATOS.keys()))
formato, usa_capturas = FORMATOS[etiqueta]
col_info.markdown(
    f"<div style='padding-top:30px;color:#555'>Se generará la hoja "
    f"<b>{CONFIG[formato]['hoja']}</b>." +
    ("" if usa_capturas else " <i>Este formato no usa capturas.</i>") + "</div>",
    unsafe_allow_html=True,
)

c1, c2 = st.columns(2)
boletas = c1.file_uploader("Boletas (PDF)", type="pdf", accept_multiple_files=True,
                           key=f"pdf_{k}")
if usa_capturas:
    capturas = c2.file_uploader("Capturas del portal (imágenes) — opcional",
                                type=list(IMG_EXT), accept_multiple_files=True,
                                key=f"img_{k}")
else:
    capturas = []
    c2.markdown("<div style='padding-top:38px;color:#999'>— sin capturas para este "
                "formato —</div>", unsafe_allow_html=True)

b1, b2, _ = st.columns([1, 1, 5])
procesar = b1.button("Procesar", type="primary", disabled=not boletas)
if b2.button("Limpiar todo"):
    st.session_state.pop("filas", None)
    st.session_state.pop("formato", None)
    st.session_state["uploader_key"] += 1
    st.rerun()

if procesar and boletas:
    tmp = tempfile.mkdtemp(prefix="ssbb_")
    bdir = os.path.join(tmp, "boletas"); os.makedirs(bdir)
    cdir = os.path.join(tmp, "capturas"); os.makedirs(cdir)
    try:
        _guardar_subidas(boletas, bdir, exts=["pdf"])
        _guardar_subidas(capturas, cdir, exts=list(IMG_EXT))
        barra = st.progress(0.0, text="Iniciando…")

        def _prog(i, n, nombre):
            barra.progress(i / max(n, 1), text=f"Procesando {i+1}/{n}: {nombre}")

        filas = procesar_carpeta(bdir, cdir, con_captura=usa_capturas, progreso=_prog)
        barra.progress(1.0, text=f"Listo — {len(filas)} boleta(s)")
        st.session_state["filas"] = filas
        st.session_state["formato"] = formato
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if st.session_state.get("filas"):
    filas = st.session_state["filas"]
    formato = st.session_state["formato"]
    ok, dif, sincap = _resumen(filas)
    rev_lectura = sum(1 for f in filas if not str(f.get("estado", "")).startswith("OK"))

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Boletas", len(filas))
    m2.metric("Leídas OK", ok)
    m3.metric("Revisar lectura", rev_lectura)
    m4.metric("Dif. captura", dif)
    m5.metric("Sin captura", sincap)

    df = _tabla(filas)

    def _color(val):
        s = str(val)
        if s.startswith("✓"):   return "background-color:#d4edda;color:#155724"
        if "revisar" in s or "REVISAR" in s:  return "background-color:#fff3cd;color:#856404"
        if "OCR" in s:          return "background-color:#f8d7da;color:#721c24"
        return ""

    disp = df.copy()
    for col in ("Monto", "Monto captura"):
        disp[col] = disp[col].apply(
            lambda v: f"{int(v):,}".replace(",", ".") if pd.notna(v) and v != "" else "")
    try:
        import jinja2  # noqa: F401
        styled = disp.style.map(_color, subset=["Captura", "Lectura"])
        st.dataframe(styled, use_container_width=True, hide_index=True,
                     height=min(560, 60 + 36 * len(df)))
    except Exception:
        st.dataframe(disp, use_container_width=True, hide_index=True,
                     height=min(560, 60 + 36 * len(df)))

    try:
        buf = io.BytesIO()
        ESCRITORES[formato](filas, buf)
        buf.seek(0)
        st.download_button(
            f"Descargar Excel — {CONFIG[formato]['descripcion']}",
            data=buf, file_name=ARCHIVO_SALIDA[formato],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as exc:
        st.error(f"Error generando Excel: {exc}")
