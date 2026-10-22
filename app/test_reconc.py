"""Prueba la reconciliación PDF vs captura. Empata boleta y captura por depto."""
import io, os, sys, glob, re, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssbb_parser import leer_boleta
from captura_ocr import verificar_captura

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def clave(nombre):
    """Clave de empate: dígitos iniciales si los hay, si no el nombre en mayúsculas."""
    stem = os.path.splitext(os.path.basename(nombre))[0].strip()
    m = re.match(r"(\d+)", stem)
    return m.group(1) if m else stem.upper()


def indexar_capturas(carpeta):
    idx = {}
    for p in glob.glob(os.path.join(carpeta, "*")):
        if p.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            idx.setdefault(clave(p), p)
    return idx


def probar(nombre, boletas_dir, capturas_dir, limite=None):
    pdfs = sorted(glob.glob(os.path.join(boletas_dir, "*.pdf")))
    if limite:
        pdfs = pdfs[:limite]
    caps = indexar_capturas(capturas_dir)
    print("\n" + "=" * 80)
    print(f"{nombre}  ({len(pdfs)} boletas, {len(caps)} capturas)")
    print("=" * 80)
    print(f"{'depto':<12}{'monto_pdf':>10}{'monto_cap':>10}  resultado")
    ok = dif = sincap = 0
    t0 = time.time()
    for p in pdfs:
        r = leer_boleta(p)
        depto = str(r["depto"])
        cap = caps.get(clave(p)) or caps.get(depto)
        if not cap:
            sincap += 1
            print(f"{depto[:11]:<12}{str(r['monto']):>10}{'—':>10}  SIN CAPTURA")
            continue
        est, mc = verificar_captura(cap, r["monto"])
        if est == "OK":
            ok += 1
            print(f"{depto[:11]:<12}{str(r['monto']):>10}{str(mc):>10}  OK")
        elif est == "SIN_OCR":
            dif += 1
            print(f"{depto[:11]:<12}{str(r['monto']):>10}{'?':>10}  OCR SIN TEXTO")
        else:
            dif += 1
            print(f"{depto[:11]:<12}{str(r['monto']):>10}{str(mc):>10}  <-- DIFERENCIA")
    print(f"\n{nombre}: OK={ok}  DIF/FALLO={dif}  SIN CAPTURA={sincap}  "
          f"({time.time()-t0:.0f}s, {(time.time()-t0)/max(len(pdfs),1):.1f}s/boleta)")


probar("AGUAS tipo 2", os.path.join(BASE, "Aguas Andinas", "2", "Boletas"),
       os.path.join(BASE, "Aguas Andinas", "2", "Capturas"))
probar("AGUAS tipo 1 (muestra)", os.path.join(BASE, "Aguas Andinas", "1", "0-. Boletas"),
       os.path.join(BASE, "Aguas Andinas", "1", "1-. Capturas"), limite=15)
