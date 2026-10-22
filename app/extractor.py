"""Orquestador: carpeta de boletas (+ capturas) -> Excel del formato elegido.

Uso CLI:
    python extractor.py <formato> <carpeta_boletas> [carpeta_capturas] [salida.xlsx]
    formato: unidades | consumo | rendicion
"""
import os
import re
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssbb_parser import leer_boleta
from captura_ocr import verificar_captura
from salidas import ESCRITORES
from edificios import es_numerico, clave_match

IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def _clave(nombre):
    """Clave de empate boleta↔captura (número inicial o unidad especial normalizada)."""
    return clave_match(nombre)


def _indexar_capturas(carpeta):
    idx = {}
    if carpeta and os.path.isdir(carpeta):
        for p in sorted(glob.glob(os.path.join(carpeta, "*"))):
            if p.lower().endswith(IMG_EXT):
                idx.setdefault(_clave(p), p)
    return idx


def _tokens(s):
    """Palabras significativas (>=2 letras/dígitos) en mayúsculas."""
    return [t for t in re.split(r"[^A-Z0-9]+", str(s).upper()) if len(t) >= 2]


def _score(a, b):
    """Nº de tokens de 'a' que calzan con alguno de 'b' (igual o prefijo de >=4)."""
    n = 0
    for x in a:
        if any(x == y or (len(x) >= 4 and len(y) >= 4 and (x.startswith(y) or y.startswith(x)))
               for y in b):
            n += 1
    return n


def _asignar_capturas(filas, idx):
    """{archivo_boleta: ruta_captura}. 1) empate EXACTO por clave (número o nombre
    normalizado); 2) FUZZY por tokens para unidades especiales con nombres distintos
    (p. ej. 'GC SECTOR NORTE' <-> 'GC SECT NORTE', 'quinchop.15' <-> 'P-15 QUINCHO'),
    evitando asignaciones ambiguas o a deptos numéricos."""
    asign, usadas = {}, set()
    for f in filas:
        for k in (clave_match(f.get("archivo", "")), clave_match(f.get("depto", ""))):
            if k in idx and idx[k] not in usadas:
                asign[f["archivo"]] = idx[k]; usadas.add(idx[k]); break
    for f in filas:
        if f.get("archivo") in asign or es_numerico(f.get("depto")):
            continue
        bt = _tokens(clave_match(f.get("depto", "")) or f.get("archivo", ""))
        mejor_v, mejor_sc, empate = None, 0, False
        for k, v in idx.items():
            if v in usadas:
                continue
            sc = _score(bt, _tokens(k))
            if sc > mejor_sc:
                mejor_v, mejor_sc, empate = v, sc, False
            elif sc == mejor_sc and sc > 0:
                empate = True
        if mejor_v and mejor_sc >= 2 and not empate:
            asign[f["archivo"]] = mejor_v; usadas.add(mejor_v)
    return asign


def _orden(f):
    d = str(f.get("depto", ""))
    return (0, int(d)) if es_numerico(d) else (1, 0, d.upper())


def procesar_carpeta(boletas_dir, capturas_dir=None, con_captura=True, progreso=None):
    """Lee todas las boletas de la carpeta y las reconcilia con sus capturas.
    `progreso(i, n, nombre)` es un callback opcional para la UI."""
    pdfs = sorted(glob.glob(os.path.join(boletas_dir, "*.pdf")))
    idx = _indexar_capturas(capturas_dir) if con_captura else {}
    # 1) Leer todas las boletas.
    filas = []
    for p in pdfs:
        try:
            f = leer_boleta(p)
        except Exception as e:                       # noqa: BLE001
            f = {"archivo": os.path.basename(p), "proveedor": "", "tipo_doc": "",
                 "folio": "", "fecha_emision": None, "periodo": (None, None),
                 "vencimiento": None, "n_cuenta": "", "depto": "", "cliente": "",
                 "consumo": "", "monto": None, "metodo": "error",
                 "estado": f"ERROR: {e}"}
        filas.append(f)
    # 2) Asignar capturas (exacto + fuzzy).
    asign = _asignar_capturas(filas, idx) if con_captura else {}
    # 3) OCR + reconciliación (la parte lenta: aquí va el progreso).
    for i, f in enumerate(filas):
        if progreso:
            progreso(i, len(filas), f.get("archivo", ""))
        f["monto_captura"] = None
        f["estado_reconc"] = "SIN CAPTURA"
        if not con_captura:
            f["monto_captura"] = f.get("monto")
            continue
        cap = asign.get(f.get("archivo"))
        if cap:
            m = f.get("monto")
            if m == 0:
                # Boleta en $0 (sin deuda): no hay monto que cruzar, no es diferencia.
                f["estado_reconc"] = "OK"
                f["monto_captura"] = 0
            else:
                est, mc = verificar_captura(cap, m)
                f["estado_reconc"] = est
                f["monto_captura"] = m if est == "OK" else mc
    filas.sort(key=_orden)
    return filas


def generar(formato, filas, ruta):
    ESCRITORES[formato](filas, ruta)
    return ruta


def _resumen(filas):
    ok = sum(1 for f in filas if f.get("estado") == "OK")
    dif = sum(1 for f in filas if f.get("estado_reconc") == "DIFERENCIA")
    sincap = sum(1 for f in filas if f.get("estado_reconc") == "SIN CAPTURA")
    return ok, dif, sincap


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    formato = sys.argv[1]
    boletas = sys.argv[2]
    capturas = sys.argv[3] if len(sys.argv) > 3 else None
    salida = sys.argv[4] if len(sys.argv) > 4 else os.path.join(boletas, f"salida_{formato}.xlsx")
    if formato not in ESCRITORES:
        print("Formato inválido:", formato, "-> usar:", ", ".join(ESCRITORES))
        return
    filas = procesar_carpeta(boletas, capturas,
                             progreso=lambda i, n, nom: print(f"  {i+1}/{n}  {nom}"))
    generar(formato, filas, salida)
    ok, dif, sincap = _resumen(filas)
    print(f"\nListo: {len(filas)} boletas  |  lectura OK={ok}  "
          f"dif. captura={dif}  sin captura={sincap}")
    print("Excel:", salida)


if __name__ == "__main__":
    main()
