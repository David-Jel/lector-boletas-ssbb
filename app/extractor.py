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


def _buscar_captura(idx, pdf_path, depto):
    return idx.get(clave_match(pdf_path)) or idx.get(clave_match(depto))


def _orden(f):
    d = str(f.get("depto", ""))
    return (0, int(d)) if es_numerico(d) else (1, 0, d.upper())


def procesar_carpeta(boletas_dir, capturas_dir=None, con_captura=True, progreso=None):
    """Lee todas las boletas de la carpeta y las reconcilia con sus capturas.
    `progreso(i, n, nombre)` es un callback opcional para la UI."""
    pdfs = sorted(glob.glob(os.path.join(boletas_dir, "*.pdf")))
    idx = _indexar_capturas(capturas_dir) if con_captura else {}
    filas = []
    for i, p in enumerate(pdfs):
        if progreso:
            progreso(i, len(pdfs), os.path.basename(p))
        try:
            f = leer_boleta(p)
        except Exception as e:                       # noqa: BLE001
            f = {"archivo": os.path.basename(p), "proveedor": "", "tipo_doc": "",
                 "folio": "", "fecha_emision": None, "periodo": (None, None),
                 "vencimiento": None, "n_cuenta": "", "depto": "", "cliente": "",
                 "consumo": "", "monto": None, "metodo": "error",
                 "estado": f"ERROR: {e}"}
        # Reconciliación con la captura
        f["monto_captura"] = None
        f["estado_reconc"] = "SIN CAPTURA"
        if con_captura:
            cap = _buscar_captura(idx, p, f.get("depto"))
            if cap:
                est, mc = verificar_captura(cap, f.get("monto"))
                f["estado_reconc"] = est
                f["monto_captura"] = mc if mc is not None else f.get("monto")
                if est == "OK":
                    f["monto_captura"] = f.get("monto")
        else:
            f["monto_captura"] = f.get("monto")
        filas.append(f)
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
