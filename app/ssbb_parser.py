"""Lector de boletas de Servicios Básicos (SSBB) — LAR Group.

Extrae los campos de cada PDF de boleta/factura de servicios básicos:
Aguas Andinas (boleta y factura) y Enel. Todas las boletas traen capa de
texto nativa limpia, así que el método principal es TEXTO (pypdf). Como
respaldo para PDFs escaneados se puede añadir OCR más adelante.

Campos que entrega `leer_boleta(path)`:
    proveedor     "AGUAS ANDINAS" | "ENEL" | ""      (detectado por RUT emisor)
    tipo_doc      "BOLETA" | "FACTURA"
    folio         str (número de documento)
    rut_emisor    str normalizado del emisor del servicio
    fecha_emision datetime | None
    periodo       (ini: date|None, fin: date|None)     — periodo de consumo
    vencimiento   datetime | None
    n_cuenta      str  "2961082-7"  (nro de cliente/cuenta del servicio)
    depto         str  (desde el nombre de archivo; respaldo: dirección)
    cliente       str  (razón social / titular, best-effort)
    consumo       str  (m3 o kWh, best-effort)
    monto         int | None  (total a pagar, CLP)
    metodo        "texto" | "timbre" | "ocr"
    estado        "OK" | "REVISAR: faltan ..."
"""
import io
import os
import re
from datetime import datetime

from pypdf import PdfReader

from edificios import empresa_torre

# ── RUT de los emisores conocidos ──────────────────────────────────────────────
RUT_AGUAS = "618080005"      # Aguas Andinas  61.808.000-5
RUT_ENEL = "968005707"       # Enel           96.800.570-7

# ── Meses en español (abreviados y completos) ──────────────────────────────────
MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7,
    "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}

CAMPOS_OBLIG = ("folio", "fecha_emision", "monto")


def _falta(v):
    """Un campo falta si es None o cadena vacía. OJO: monto 0 es un valor válido
    (hay boletas con TOTAL A PAGAR $0 cubierto por saldo a favor)."""
    return v is None or (isinstance(v, str) and v.strip() == "")


def norm_rut(s):
    """Deja el RUT como dígitos + DV (sin puntos ni guion). K en mayúscula."""
    if not s:
        return ""
    s = re.sub(r"[^0-9kK]", "", str(s)).upper()
    return s


def num_cl(s):
    """'4.860' / '7.232' / '1.055' -> int. None si no parsea."""
    try:
        return int(re.sub(r"[.\s]", "", str(s)).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _mes(tok):
    return MESES.get(tok.strip().lower()[:3])


def texto_pdf(path):
    reader = PdfReader(path)
    return "\n".join((p.extract_text() or "") for p in reader.pages)


# ── Expresiones comunes ────────────────────────────────────────────────────────
RE_RUT = re.compile(r"R\.?U\.?T\.?\s*:?\s*(\d{1,2}\.\d{3}\.\d{3}\s*-\s*[\dkK])", re.I)
# Fecha dd-MMM-aaaa  (13-JUL-2026) — Aguas
RE_FECHA_ABR = re.compile(r"(\d{1,2})\s*-\s*([A-Za-z]{3,4})\s*-\s*(\d{4})")
# Fecha dd MMM aaaa  (03 Ago 2026) — Enel
RE_FECHA_TXT = re.compile(r"(\d{1,2})\s+([A-Za-z]{3,10})\.?\s+(\d{4})")
# Nro de cuenta / cliente: 7 dígitos + guion + DV, sin punto antes (distinto del RUT)
RE_CUENTA = re.compile(r"(?<![\d.\-])(\d{7}\s*-\s*[\dkK])\b")


def _fecha_abr(txt, etiqueta):
    """Busca 'ETIQUETA ... dd-MMM-aaaa' cerca de la etiqueta."""
    m = re.search(etiqueta, txt, re.I)
    if not m:
        return None
    ventana = txt[m.start(): m.start() + 60]
    fm = RE_FECHA_ABR.search(ventana)
    if fm and _mes(fm.group(2)):
        try:
            return datetime(int(fm.group(3)), _mes(fm.group(2)), int(fm.group(1)))
        except ValueError:
            return None
    return None


def _depto_de_archivo(path):
    """El depto proviene del nombre de archivo (la convención del usuario).

    '207.pdf' -> '207';  'gastos comunes 1.pdf' -> 'GASTOS COMUNES 1';
    'caldera alta.pdf' -> 'CALDERA ALTA';
    'BE - 373302601 - Enel - Depto 808 - Periodo ...' -> '808'.
    """
    stem = os.path.splitext(os.path.basename(path))[0].strip()
    # Enel: '... - Depto 808 - ...'
    m = re.search(r"depto\s+(\w+)", stem, re.I)
    if m:
        return m.group(1)
    # Aguas: archivo = solo el número del depto
    if re.fullmatch(r"\d{2,4}", stem):
        return stem
    # Especiales (gastos comunes, calderas, etc.): usar el nombre tal cual
    return stem.upper()


# Depto en la dirección de Aguas: 'MIRADOR AZUL 1484---207 -EDIF.' /
# 'SANTO DOMINGO 1410---2212 -EDIFICIO'. Las unidades especiales (caldera,
# gasto común) NO llevan número tras los guiones ('1410 -CALDERA ALTA'), así
# que esto solo captura deptos numerados.
RE_AGUAS_DEPTO = re.compile(r"-{2,}\s*(\d{2,4})\s*(?=-)")


def _depto_aguas(txt, path):
    """Prefiere el depto de la dirección (robusto ante archivos mal nombrados,
    p.ej. 'pdf_1790097457362.pdf'); si no hay número, usa el nombre de archivo."""
    m = RE_AGUAS_DEPTO.search(txt)
    if m:
        return m.group(1)
    return _depto_de_archivo(path)


def _cliente(txt):
    """Razón social / titular (best-effort)."""
    # Enel: 'Sr. (a) maria paredes'
    m = re.search(r"Sr\.?\s*\(?a?\)?\s+([A-Za-zÁÉÍÓÚÑáéíóúñ ]{3,60})", txt)
    if m:
        return m.group(1).strip().title()
    # Aguas: línea en mayúsculas terminada en SPA / SA / LTDA / etc.
    for ln in txt.splitlines():
        ln = ln.strip()
        if re.search(r"\b(SPA|S\.A\.|SA|LTDA|LIMITADA|EIRL|E\.I\.R\.L\.)\.?$", ln, re.I) \
                and len(ln) >= 6 and sum(c.isdigit() for c in ln) <= 2:
            return ln
    return ""


# ── AGUAS ANDINAS ──────────────────────────────────────────────────────────────
RE_AGUAS_TIPO = re.compile(r"(BOLETA|FACTURA)\s+ELECTR[ÓO]NICA", re.I)
RE_AGUAS_FOLIO = re.compile(
    r"(?:BOLETA|FACTURA)\s+ELECTR[ÓO]NICA\s*N\s*[°ºo]?\s*(\d{3,})", re.I)
RE_AGUAS_MONTO = re.compile(r"TOTAL\s+A\s+PAGAR\s*\$?\s*([\d.]+)", re.I)
RE_AGUAS_CONSUMO = re.compile(r"CONSUMO\s+TOTAL\s+([\d.,]+)\s*m3", re.I)


def _parse_aguas(txt, path):
    tm = RE_AGUAS_TIPO.search(txt)
    tipo = tm.group(1).upper() if tm else ""
    fm = RE_AGUAS_FOLIO.search(txt)
    folio = fm.group(1) if fm else ""
    mm = RE_AGUAS_MONTO.search(txt)
    monto = num_cl(mm.group(1)) if mm else None
    fecha = _fecha_abr(txt, r"FECHA\s+EMISI[ÓO]N")
    # Vencimiento: puede venir como fecha o como 'CORTE EN TRÁMITE'
    venc = _fecha_abr(txt, r"VENCIMIENTO")
    cm = RE_AGUAS_CONSUMO.search(txt)
    consumo = (cm.group(1) + " m3") if cm else ""
    cuenta_m = RE_CUENTA.search(txt)
    n_cuenta = re.sub(r"\s", "", cuenta_m.group(1)) if cuenta_m else ""
    empresa, torre = empresa_torre(txt)
    return {
        "proveedor": "AGUAS ANDINAS", "tipo_doc": tipo, "folio": folio,
        "rut_emisor": RUT_AGUAS, "fecha_emision": fecha,
        "periodo": (None, None), "vencimiento": venc,
        "n_cuenta": n_cuenta, "depto": _depto_aguas(txt, path),
        "empresa": empresa, "torre": torre,
        "cliente": _cliente(txt), "consumo": consumo, "monto": monto,
    }


# ── ENEL ───────────────────────────────────────────────────────────────────────
RE_ENEL_FOLIO = re.compile(r"BOLETA\s+ELECTR[ÓO]NICA\s*N\s*[°ºo]?\s*(\d{3,})", re.I)
RE_ENEL_MONTO = re.compile(r"Total\s+a\s+pagar\s*:?\s*\$?\s*([\d.]+)", re.I)
RE_ENEL_PERIODO = re.compile(
    r"periodo\s+(\d{1,2})\s+([A-Za-z]{3,})\.?\s+(\d{4})\s*-\s*"
    r"(\d{1,2})\s+([A-Za-z]{3,})\.?\s+(\d{4})", re.I)
RE_ENEL_CONSUMO = re.compile(r"([\d.,]+)\s*kWh", re.I)


def _parse_enel(txt, path):
    fm = RE_ENEL_FOLIO.search(txt)
    folio = fm.group(1) if fm else ""
    mm = RE_ENEL_MONTO.search(txt)
    monto = num_cl(mm.group(1)) if mm else None
    # Fecha de emisión
    fecha = None
    me = re.search(r"Fecha\s+de\s+emisi[óo]n\s*:?\s*" + RE_FECHA_TXT.pattern, txt, re.I)
    if me and _mes(me.group(2)):
        try:
            fecha = datetime(int(me.group(3)), _mes(me.group(2)), int(me.group(1)))
        except ValueError:
            fecha = None
    # Vencimiento
    venc = None
    mv = re.search(r"vencimiento\s*" + RE_FECHA_TXT.pattern, txt, re.I)
    if mv and _mes(mv.group(2)):
        try:
            venc = datetime(int(mv.group(3)), _mes(mv.group(2)), int(mv.group(1)))
        except ValueError:
            venc = None
    # Periodo de consumo
    pini = pfin = None
    mp = RE_ENEL_PERIODO.search(txt)
    if mp and _mes(mp.group(2)) and _mes(mp.group(5)):
        try:
            pini = datetime(int(mp.group(3)), _mes(mp.group(2)), int(mp.group(1)))
            pfin = datetime(int(mp.group(6)), _mes(mp.group(5)), int(mp.group(4)))
        except ValueError:
            pini = pfin = None
    cm = RE_ENEL_CONSUMO.search(txt)
    consumo = (cm.group(1) + " kWh") if cm else ""
    cuenta_m = RE_CUENTA.search(txt)
    n_cuenta = re.sub(r"\s", "", cuenta_m.group(1)) if cuenta_m else ""
    return {
        "proveedor": "ENEL", "tipo_doc": "BOLETA", "folio": folio,
        "rut_emisor": RUT_ENEL, "fecha_emision": fecha,
        "periodo": (pini, pfin), "vencimiento": venc,
        "n_cuenta": n_cuenta, "depto": _depto_de_archivo(path),
        "empresa": "", "torre": "",
        "cliente": _cliente(txt), "consumo": consumo, "monto": monto,
    }


# ── Orquestador ────────────────────────────────────────────────────────────────
def _detectar_proveedor(txt):
    t = norm_rut(txt)  # quita todo menos dígitos y K; el RUT emisor aparece íntegro
    tu = txt.upper()
    if RUT_AGUAS in t or "AGUAS ANDINAS" in tu or "61.808.000" in txt:
        return "AGUAS ANDINAS"
    if RUT_ENEL in t or "ENEL" in tu or "96.800.570" in txt:
        return "ENEL"
    return ""


def leer_boleta(path):
    txt = texto_pdf(path)
    prov = _detectar_proveedor(txt)
    if prov == "AGUAS ANDINAS":
        r = _parse_aguas(txt, path)
    elif prov == "ENEL":
        r = _parse_enel(txt, path)
    else:
        r = {"proveedor": "", "tipo_doc": "", "folio": "", "rut_emisor": "",
             "fecha_emision": None, "periodo": (None, None), "vencimiento": None,
             "n_cuenta": "", "depto": _depto_de_archivo(path), "empresa": "",
             "torre": "", "cliente": "", "consumo": "", "monto": None}
    r["metodo"] = "texto"
    faltan = [c for c in CAMPOS_OBLIG if _falta(r.get(c))]
    if not prov:
        r["estado"] = "REVISAR: proveedor no reconocido"
    elif faltan:
        r["estado"] = "REVISAR: faltan " + ", ".join(c.upper() for c in faltan)
    else:
        r["estado"] = "OK"
    r["archivo"] = os.path.basename(path)
    return r
