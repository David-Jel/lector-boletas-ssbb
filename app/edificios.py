"""Configuración por edificio / formato de salida (editable).

Hay dos formatos de Excel de destino:
  aguas     -> Aguas Andinas, formato único tipo "Viento Sur" (hoja "Hoja1").
               Sirve para TODOS los edificios; EMPRESA y TORRE salen de abajo.
  rendicion -> Enel / Aguas, formato Rendición SC-020 ("para pegar").

Para agregar un edificio nuevo, añade una entrada a EDIFICIOS_AGUAS con una
palabra clave de su dirección, su EMPRESA y su TORRE.
"""
import os
import re

CONFIG = {
    "aguas": {
        "descripcion": "Aguas – Consumo (formato Viento Sur, todos los edificios)",
        "hoja": "Hoja1",
    },
    "rendicion": {
        "descripcion": "Rendición Servicios Básicos SC-020",
        "hoja": "para pegar",
    },
}

# Edificios de Aguas: palabra clave en la dirección de la boleta -> EMPRESA y TORRE.
# La torre también se intenta leer de la dirección ("EDIFICIO TORRE 3"); si no
# aparece (p. ej. en calderas/gastos comunes), se usa la torre de este config.
EDIFICIOS_AGUAS = [
    {"kw": "SANTO DOMINGO 1410",     "empresa": "VIENTO SUR", "torre": 3},
    {"kw": "MIRADOR AZUL",           "empresa": "BROOKLYN",   "torre": ""},
    {"kw": "CLUB DE CAMPO 194",      "empresa": "BOLDO",      "torre": 3},
    {"kw": "PRESIDENTE RIESCO 6007", "empresa": "NATIVO",     "torre": ""},
]

# Código contable por proveedor (hoja "para pegar" de la rendición).
CODIGO_CONTABLE = {
    "ENEL": "4-2-03-001  Luz",
    "AGUAS ANDINAS": "4-2-03-002  Agua",
}
SERVICIO = {"ENEL": "Luz", "AGUAS ANDINAS": "Agua"}

_RE_TORRE = re.compile(r"TORRE\s+([0-9A-Za-z]+)", re.I)
_RE_EDIF = re.compile(r"EDIFICIO\s+(\d+)", re.I)   # p. ej. 'EDIFICIO 3 BOLDO'


def empresa_torre(texto):
    """Devuelve (empresa, torre) para una boleta de Aguas según su dirección.
    Si el edificio no está en el config, empresa queda en blanco (se completa a
    mano) y la torre se toma de la dirección si aparece."""
    # Normaliza espacios: la dirección suele traer doble espacio
    # ("SANTO DOMINGO  1410") que rompería un match con un solo espacio.
    tu = re.sub(r"\s+", " ", texto.upper())
    torre_dir = ""
    m = _RE_TORRE.search(texto) or _RE_EDIF.search(texto)
    if m:
        torre_dir = m.group(1)
    for e in EDIFICIOS_AGUAS:
        if re.sub(r"\s+", " ", e["kw"].upper()) in tu:
            return e["empresa"], (torre_dir or e["torre"])
    return "", torre_dir


def partir_cuenta(n_cuenta):
    """'2788555-1' -> ('2788555-1', '2788555', '1'). Tolera cuenta sin guion."""
    n_cuenta = (n_cuenta or "").strip()
    m = re.match(r"(\d+)\s*-\s*([\dkK])", n_cuenta)
    if m:
        return n_cuenta, m.group(1), m.group(2)
    return n_cuenta, n_cuenta, ""


def es_numerico(depto):
    return bool(re.fullmatch(r"\d{2,5}", str(depto).strip()))


def normaliza_especial(s):
    """Nombre canónico de una unidad especial, tolerando variantes de escritura:
    guiones/puntos como separadores ('CALD-ALTA PRESION' -> 'CALD ALTA PRESION'),
    y 'GASTOS COMUNES 1' / 'GASTO COMUNES 3' / 'GGCC 1' -> 'GASTO COMUN N'."""
    s = re.sub(r"[-.]", " ", str(s).upper())
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"GASTOS?\s+COMUNE?S?", "GASTO COMUN", s)
    s = re.sub(r"\bGGCC\b", "GASTO COMUN", s)
    return re.sub(r"\s+", " ", s).strip()


def depto_consumo(depto):
    """Etiqueta de la columna DEPTO: número tal cual, o la unidad especial
    canónica ('CALDERA ALTA', 'GASTO COMUN 1')."""
    d = str(depto).strip()
    return d if es_numerico(d) else normaliza_especial(d)


_EXT_ARCHIVO = (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp")


def clave_match(texto):
    """Clave para emparejar boleta <-> captura: el número inicial del nombre, o
    el nombre de la unidad especial normalizado. Así 'gastos comunes 1.pdf',
    'GASTO COMUN 1.png' y el depto 'GASTOS COMUNES 1' caen en la misma clave.
    Solo quita extensiones reales de archivo: 'QUINCHOP.15' conserva el '.15'."""
    s = os.path.basename(str(texto)).strip()
    base, ext = os.path.splitext(s)
    if ext.lower() in _EXT_ARCHIVO:
        s = base
    m = re.match(r"(\d+)", s)
    return m.group(1) if m else normaliza_especial(s)
