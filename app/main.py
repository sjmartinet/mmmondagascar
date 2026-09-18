"""API y servidor de la aplicacion.

Un solo proceso sirve la interfaz y la API: no hay CORS que configurar ni un
segundo servicio que levantar. El jurado ejecuta un comando y ya.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db
from .llm import responder
from .rag import BuscadorNormativo

load_dotenv()

RAIZ = Path(__file__).resolve().parent.parent
ESTATICOS = RAIZ / "static"

DOMINIO = "Derecho laboral colombiano"
AVISO_LEGAL = (
    "Esta herramienta ofrece orientacion general sobre derecho laboral colombiano. "
    "No sustituye la asesoria de un abogado ni constituye representacion legal."
)

app = FastAPI(title="Asesor Laboral de Bolsillo", docs_url="/api/docs")

# El indice se construye una sola vez al arrancar, no en cada consulta.
buscador = BuscadorNormativo()
db.iniciar()


class Consulta(BaseModel):
    texto: str = Field(min_length=1, max_length=4000)


@app.get("/api/salud")
def salud() -> dict:
    """Permite comprobar de un vistazo que todo esta en su sitio."""
    return {
        "estado": "ok",
        "dominio": DOMINIO,
        "normas_indexadas": len(buscador.normas),
        "llave_claude": bool(os.getenv("ANTHROPIC_API_KEY", "").strip()),
        "voz_disponible": bool(os.getenv("FISH_API_KEY", "").strip()),
        "modo_sin_conexion": "disponible",
        "aviso_legal": AVISO_LEGAL,
    }


@app.post("/api/consulta")
def consultar(consulta: Consulta) -> JSONResponse:
    texto = consulta.texto.strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Escribe tu caso para poder ayudarte.")

    resultados = buscador.buscar(texto, cuantas=6)

    try:
        datos = responder(texto, resultados)
    except RuntimeError as error:
        # Falta de configuracion: el mensaje debe decirle al usuario que hacer.
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001 - nunca filtramos la traza al cliente
        print(f"[error] fallo generando la respuesta: {error}")
        raise HTTPException(
            status_code=502,
            detail="No pude consultar el modelo de lenguaje. Revisa tu conexion y vuelve a intentarlo.",
        ) from error

    datos["aviso_legal"] = AVISO_LEGAL
    datos["normas_consultadas"] = [
        {"cita": n.cita, "tema": n.tema, "relevancia": round(p, 2)}
        for n, p in resultados
    ]

    db.guardar(texto, datos)
    return JSONResponse(datos)


@app.get("/api/historial")
def ver_historial() -> dict:
    return {"consultas": db.historial()}


class TextoVoz(BaseModel):
    texto: str = Field(min_length=1, max_length=1200)


@app.post("/api/voz")
async def voz(peticion: TextoVoz) -> Response:
    """Convierte la respuesta en audio con Fish Audio.

    Es opcional a proposito: si no hay llave configurada devolvemos 204 y la
    interfaz sigue funcionando con subtitulos. Asi la app nunca deja de arrancar
    en la maquina de quien la evalua.
    """
    llave = os.getenv("FISH_API_KEY", "").strip()
    voz_id = os.getenv("FISH_VOICE_ID", "").strip()
    if not llave or not voz_id:
        return Response(status_code=204)

    try:
        async with httpx.AsyncClient(timeout=30) as cliente:
            respuesta = await cliente.post(
                "https://api.fish.audio/v1/tts",
                headers={
                    "Authorization": f"Bearer {llave}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": peticion.texto,
                    "reference_id": voz_id,
                    "format": "mp3",
                    "latency": "balanced",
                },
            )
        if respuesta.status_code != 200:
            print(f"[voz] Fish Audio respondio {respuesta.status_code}")
            return Response(status_code=204)
        return Response(content=respuesta.content, media_type="audio/mpeg")
    except Exception as error:  # noqa: BLE001
        print(f"[voz] no se pudo generar el audio: {error}")
        return Response(status_code=204)


@app.get("/")
def inicio() -> FileResponse:
    return FileResponse(ESTATICOS / "index.html")


app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")
