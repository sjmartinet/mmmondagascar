"""Ejecuta el set de evaluacion contra la aplicacion y muestra los resultados.

    python evaluar.py

Comprueba dos cosas por cada caso:
  1. Si la aplicacion acierta al declarar (o no) que el caso esta fuera de dominio.
  2. Si cita las normas que deberia citar.

La deteccion de fuera de dominio se verifica SIN gastar API cuando el corpus no
devuelve ninguna coincidencia, porque en ese caso ya es deterministica.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app.llm import responder  # noqa: E402
from app.rag import BuscadorNormativo  # noqa: E402

RAIZ = Path(__file__).resolve().parent
VERDE, ROJO, GRIS, FIN = "\033[92m", "\033[91m", "\033[90m", "\033[0m"


def main() -> int:
    casos = json.loads((RAIZ / "eval_cases.json").read_text(encoding="utf-8"))["casos"]
    buscador = BuscadorNormativo()

    print(f"\n  SET DE EVALUACION — {len(casos)} casos\n  {'=' * 60}\n")
    aciertos = 0

    for caso in casos:
        print(f"  [{caso['id']}] {caso['consulta']}")
        resultados = buscador.buscar(caso["consulta"], cuantas=6)

        try:
            datos = responder(caso["consulta"], resultados)
        except RuntimeError as error:
            print(f"  {ROJO}Configuracion incompleta:{FIN} {error}\n")
            return 1
        except Exception as error:  # noqa: BLE001
            print(f"  {ROJO}FALLO{FIN} al consultar el modelo: {error}\n")
            continue

        fallos = []

        if bool(datos.get("fuera_de_dominio")) != caso["espera_fuera_de_dominio"]:
            fallos.append(
                f"fuera_de_dominio={datos.get('fuera_de_dominio')} "
                f"(se esperaba {caso['espera_fuera_de_dominio']})"
            )

        citas = " ".join(n.get("cita", "") for n in datos.get("normas", []))
        for esperada in caso["normas_esperadas"]:
            if esperada not in citas:
                fallos.append(f"no cito la norma {esperada}")

        texto = (datos.get("resumen", "") + " " + " ".join(datos.get("pasos", []))).lower()
        for palabra in caso["debe_mencionar"]:
            if palabra not in texto and palabra not in citas.lower():
                fallos.append(f"no menciono '{palabra}'")

        if fallos:
            print(f"  {ROJO}FALLA{FIN} -> {'; '.join(fallos)}")
        else:
            aciertos += 1
            print(f"  {VERDE}PASA{FIN}")

        print(f"  {GRIS}{datos.get('resumen', '')[:150]}{FIN}\n")

    print(f"  {'=' * 60}")
    print(f"  RESULTADO: {aciertos}/{len(casos)} casos correctos\n")
    return 0 if aciertos == len(casos) else 1


if __name__ == "__main__":
    sys.exit(main())
