"""Punto de arranque unico de la aplicacion.

    python run.py

Levanta la interfaz y la API en http://127.0.0.1:8000
"""

import webbrowser

import uvicorn

if __name__ == "__main__":
    print("\n  Asesor Laboral de Bolsillo")
    print("  Abriendo http://127.0.0.1:8000 ...\n")
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except Exception:
        pass
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
