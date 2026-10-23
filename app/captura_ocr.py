"""OCR de las capturas (pantallazos del portal) para reconciliar el monto.

El usuario guarda, junto a cada boleta PDF, un pantallazo del portal que muestra
el monto a pagar. Este módulo lee ese monto desde la imagen para cruzarlo con el
de la boleta y detectar descargas equivocadas (p. ej. el PDF de otro mes).

Enfoque: el monto de la BOLETA (PDF) es la fuente confiable. Sobre la captura se
hace OCR y se VERIFICA que ese monto aparezca en el texto; es mucho más robusto
que intentar "elegir" el monto correcto entre los varios que muestra el portal
(saldo anterior, último pago, subsidio…).

API:
    verificar_captura(path, monto_pdf) -> (estado, monto_captura)
        estado: "OK" | "DIFERENCIA" | "SIN_OCR"
    leer_montos_captura(path) -> (lista_montos, texto_ocr)
"""
import os
import re
import sys

_TESS_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Programs\Tesseract-OCR\tesseract.exe"),
]


def _tess_cmd():
    """Ruta a tesseract.exe: bundle de PyInstaller, luego instalaciones del sistema."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        b = os.path.join(meipass, "tesseract", "tesseract.exe")
        if os.path.isfile(b):
            os.environ.setdefault("TESSDATA_PREFIX", os.path.join(meipass, "tesseract"))
            os.environ["PATH"] = os.path.join(meipass, "tesseract") + os.pathsep + os.environ.get("PATH", "")
            return b
    for p in _TESS_PATHS:
        p = os.path.expandvars(p)
        if os.path.isfile(p):
            return p
    return None


_CMD = _tess_cmd()

# Monto CLP: "$4.860", "$ 2.290", "9.670". Exige separador de miles o 3+ dígitos.
RE_MONTO = re.compile(r"\$?\s*(\d{1,3}(?:\.\d{3})+|\d{3,7})")
# Palabras que marcan montos que NO son el total vigente a pagar.
_EXCLUIR = ("último", "ultimo", "anterior", "saldo", "subsidio", "histórico",
            "historico", "convenio", "vencer")


def _num(s):
    try:
        return int(re.sub(r"[.\s]", "", s))
    except ValueError:
        return None


_CFGS = ("--psm 6", "--psm 11", "--psm 3")


def _prep(path):
    """Imagen preprocesada (gris, upscale, autocontraste) o None."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    try:
        img = Image.open(path).convert("L")
    except Exception:
        return None
    if img.width < 2000:
        f = 2000 / img.width
        img = img.resize((int(img.width * f), int(img.height * f)))
    return ImageOps.autocontrast(img)


def _ocr_pass(img, cfg):
    """Una pasada de OCR con una config. Prueba 'spa' y cae a sin idioma."""
    try:
        import pytesseract
    except ImportError:
        return ""
    if _CMD:
        pytesseract.pytesseract.tesseract_cmd = _CMD
    try:
        return pytesseract.image_to_string(img, lang="spa", config=cfg)
    except Exception:
        try:
            return pytesseract.image_to_string(img, config=cfg)
        except Exception:
            return ""


def _ocr(path, img=None):
    """OCR robusto: varios modos de segmentación concatenados."""
    img = img or _prep(path)
    if img is None:
        return ""
    return "\n".join(_ocr_pass(img, cfg) for cfg in _CFGS)


def leer_montos_captura(path, texto=None):
    """Devuelve (lista de montos priorizados, texto_ocr). El primero de la lista
    es el mejor candidato a 'total a pagar'."""
    if texto is None:
        texto = _ocr(path)
    if not texto.strip():
        return [], texto
    preferidos, otros = [], []
    for ln in texto.splitlines():
        low = ln.lower()
        excl = any(k in low for k in _EXCLUIR)
        for m in RE_MONTO.finditer(ln):
            v = _num(m.group(1))
            if v is None or v < 100:
                continue
            if excl:
                otros.append(v)
            elif any(k in low for k in ("total", "pagar", "deuda", "vigente")):
                preferidos.insert(0, v)
            else:
                preferidos.append(v)
    orden = preferidos + otros
    # quitar duplicados conservando orden
    vistos, out = set(), []
    for v in orden:
        if v not in vistos:
            vistos.add(v); out.append(v)
    return out, texto


# Monto del titular del portal (arriba a la derecha): "$4.480", "$0".
# El "$" suele leerse como "S" y "$0" como "SO" (S + letra O).
_RE_TITULAR = re.compile(r"[\$S]\s?(\d{1,3}(?:\.\d{3})*|\d+|[Oo])")


def _monto_titular(path):
    """Lee el monto grande del titular del portal (la deuda vigente/vencida, que
    va arriba a la derecha de la captura). Es texto grande y limpio, así que se
    recorta esa zona y se OCR-ea aparte: así se recuperan montos que el OCR de la
    imagen completa pierde ('$4.480' -> '480') o confunde con la fecha ('$0' ->
    '2026'). Devuelve el monto (int, 0 incluido) o None si no lo encuentra."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        img = Image.open(path).convert("L")
    except Exception:
        return None
    crop = img.crop((int(img.width * 0.45), 0, img.width, int(img.height * 0.42)))
    if crop.width < 2200:
        f = 2200 / crop.width
        crop = crop.resize((int(crop.width * f), int(crop.height * f)))
    # Umbral: oscurece el texto gris claro del '$0' (deuda vigente al día) y, de
    # paso, limpia el fondo para los montos normales.
    crop = crop.point(lambda p: 0 if p < 190 else 255)
    # Varias segmentaciones; se elige el match con MÁS dígitos: una pasada puede
    # leer '$55 580' (separador perdido -> '55') y otra '$55.580' (completo).
    mejor, mejor_dig = None, -1
    for cfg in ("--psm 4", "--psm 6", "--psm 11"):
        for m in _RE_TITULAR.finditer(_ocr_pass(crop, cfg)):
            g = m.group(1)
            if g in ("O", "o"):
                val, ndig = 0, 0
            else:
                val, ndig = _num(g), len(re.sub(r"\D", "", g))
            if val is not None and ndig > mejor_dig:
                mejor, mejor_dig = val, ndig
    return mejor


def _aparece(monto_pdf, texto):
    """¿El monto del PDF aparece en el texto OCR? Tolera separadores de miles
    (punto o espacio) entre cualquier grupo de dígitos, incluidos millones:
    '2.503.780', '9 670', '76.530', etc."""
    if monto_pdf is None or int(monto_pdf) < 100:
        return False
    objetivo = str(int(monto_pdf))
    patron = r"(?<!\d)" + r"[.\s]?".join(objetivo) + r"(?!\d)"
    return re.search(patron, texto) is not None


def verificar_captura(path, monto_pdf):
    """Cruza el monto del PDF contra la captura.

    - "OK": el monto del PDF aparece en el texto OCR (coinciden).
    - "DIFERENCIA": no aparece; se devuelve el mejor candidato leído (o None).
    - "SIN_OCR": no se pudo leer nada (sin Tesseract o imagen ilegible).

    Hace OCR por pasadas y corta apenas encuentra el monto esperado (rápido en
    el caso normal); solo si no aparece recurre a todos los modos.
    """
    img = _prep(path)
    if img is None:
        return "SIN_OCR", None
    acum = ""
    for cfg in _CFGS:
        acum += "\n" + _ocr_pass(img, cfg)
        if _aparece(monto_pdf, acum):
            return "OK", monto_pdf
    if not acum.strip():
        return "SIN_OCR", None
    # Hay diferencia: el monto a mostrar es el titular del portal. Se lee de la
    # zona del titular (más fiable); si no se encuentra, se cae al OCR general.
    tit = _monto_titular(path)
    if tit is not None:
        return "DIFERENCIA", tit
    montos, _ = leer_montos_captura(path, texto=acum)
    return "DIFERENCIA", (montos[0] if montos else None)
