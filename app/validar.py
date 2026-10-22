"""Corre el parser sobre todas las boletas de muestra y arma una tabla de revisión."""
import io
import os
import sys
import glob

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssbb_parser import leer_boleta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETAS = [
    ("AGUAS tipo 1", os.path.join(BASE, "Aguas Andinas", "1", "0-. Boletas")),
    ("AGUAS tipo 2", os.path.join(BASE, "Aguas Andinas", "2", "Boletas")),
    ("ENEL", os.path.join(BASE, "Enel")),
]


def f(d):
    return d.strftime("%d-%m-%Y") if d else ""


def per(p):
    i, fi = p
    return (f(i) + "→" + f(fi)) if i else ""


total = ok = rev = 0
for nombre, carpeta in CARPETAS:
    pdfs = sorted(glob.glob(os.path.join(carpeta, "*.pdf")))
    print("\n" + "=" * 110)
    print(f"{nombre}  ({len(pdfs)} PDFs)  — {carpeta}")
    print("=" * 110)
    print(f"{'archivo':<16}{'prov':<8}{'tipo':<8}{'folio':<11}{'fecha':<12}"
          f"{'venc':<12}{'cuenta':<12}{'depto':<10}{'monto':>9}  {'consumo':<9} estado")
    for p in pdfs:
        r = leer_boleta(p)
        total += 1
        if r["estado"] == "OK":
            ok += 1
        else:
            rev += 1
        print(f"{r['archivo'][:15]:<16}{r['proveedor'][:7]:<8}{r['tipo_doc'][:7]:<8}"
              f"{str(r['folio'])[:10]:<11}{f(r['fecha_emision']):<12}{f(r['vencimiento']):<12}"
              f"{r['n_cuenta'][:11]:<12}{str(r['depto'])[:9]:<10}"
              f"{(str(r['monto']) if r['monto'] is not None else '-'):>9}  "
              f"{r['consumo'][:8]:<9} {r['estado']}")

print("\n" + "-" * 60)
print(f"TOTAL: {total}   OK: {ok}   REVISAR: {rev}")
