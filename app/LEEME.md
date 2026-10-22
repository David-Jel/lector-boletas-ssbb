# Lector de boletas de Servicios Básicos — LAR Group

Lee PDFs de boletas de **Aguas Andinas** (boleta y factura) y **Enel**, y genera
los Excel de destino. Cruza el monto del PDF con el de la captura del portal.

## Cómo correr la app (local)

1. Python 3.12–3.14 (en este equipo: `py`).
2. Instalar librerías:
   ```
   py -m pip install -r requirements.txt
   ```
3. Tesseract con idioma español (solo para leer el monto de las capturas):
   ya instalado en `C:\Users\djeldres\AppData\Local\Programs\Tesseract-OCR`.
   Sin Tesseract la app igual funciona; solo no reconcilia las capturas.
4. Levantar la app:
   ```
   py -m streamlit run app/app.py
   ```
   Se abre en el navegador (http://localhost:8501 o el puerto que indique).

## Uso

1. Elegir el **formato de salida**:
   - **Rendición SC-020 (Enel)** — hoja "para pegar".
   - **Consumo Aguas (Viento Sur)** — hoja "Hoja1".
   - **Unidades Aguas (Brooklyn)** — hoja "Unidades".
2. Subir las **boletas (PDF)** y, para Aguas, las **capturas** del portal (opcional).
3. **Procesar** → revisar la tabla (montos en rojo/aviso = revisar).
4. **Descargar Excel**.

El **depto** se toma de la dirección de la boleta (o del nombre de archivo). La
boleta PDF es la fuente confiable del monto; la captura solo sirve para cruzar.

## Archivos

- `ssbb_parser.py` — lectura de las boletas (texto PDF).
- `captura_ocr.py` — OCR de las capturas (reconciliación por presencia del monto).
- `edificios.py` — configuración por edificio/formato (editable).
- `salidas.py` — los 3 escritores de Excel.
- `extractor.py` — orquestador + CLI (`py extractor.py <formato> <carpeta_boletas> [capturas] [salida.xlsx]`).
- `app.py` — interfaz Streamlit.
- `validar.py` — prueba de lectura sobre carpetas de muestra (diagnóstico).
