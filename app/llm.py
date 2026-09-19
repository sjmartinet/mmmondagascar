"""Generacion de la respuesta legal a partir de las normas recuperadas.

Dos modos, y la aplicacion elige sola:

  CON INTERNET  -> Claude redacta la respuesta usando UNICAMENTE los fragmentos
                   que le entregamos del corpus. Mas natural y mejor razonada.
  SIN INTERNET  -> respuesta deterministica construida directamente desde el
                   corpus. Menos elocuente, pero cita las mismas normas, con los
                   mismos articulos y los mismos fragmentos. Nunca inventa nada,
                   porque no hay modelo que pueda inventar.

El modelo jamas responde de memoria: solo puede citar lo recuperado. Y si el
corpus no devuelve ninguna coincidencia, declaramos el caso fuera de dominio sin
llegar siquiera a llamar al modelo.
"""

from __future__ import annotations

import json
import os
import re

import anthropic

from .rag import Norma, normalizar

MODELO = os.getenv("CLAUDE_MODEL", "claude-opus-5")

INSTRUCCION = """Eres un orientador en DERECHO LABORAL COLOMBIANO que le habla a una
persona sin formacion juridica y sin dinero para pagar un abogado.

REGLAS QUE NO PUEDES ROMPER:
1. Solo puedes citar normas que aparezcan en los FRAGMENTOS que te entrego. Si una
   norma no esta en los fragmentos, NO la menciones. Nunca inventes un numero de
   articulo, una ley ni una sentencia.
2. Si el caso NO es de derecho laboral colombiano (por ejemplo: estafas, compraventa,
   arriendos, familia, transito, penal, consumidor, salud), pon fuera_de_dominio en
   true, di a que area pertenece y a que entidad debe acudir. No intentes responderlo.
3. Habla claro y directo, como una persona real. Nada de latinajos ni frases de
   abogado. Frases cortas. Trata a la persona de tu.
4. Nunca pidas ni uses datos sensibles: cedula, direccion, telefono, correo.
5. Si los fragmentos no alcanzan para responder bien, dilo con confianza "baja" en
   lugar de rellenar.

Responde UNICAMENTE con un objeto JSON valido, sin texto antes ni despues:

{
  "fuera_de_dominio": false,
  "area_detectada": "derecho laboral",
  "resumen": "Que es lo que te esta pasando, en terminos legales. 2 a 4 frases.",
  "normas": [
    {
      "cita": "Codigo Sustantivo del Trabajo, articulo 64",
      "por_que": "Una frase explicando por que esta norma aplica a TU caso.",
      "fragmento": "El trozo textual del fragmento que respalda lo anterior.",
      "fuente": "La URL que viene en el fragmento."
    }
  ],
  "pasos": [
    "Paso concreto y accionable, empezando por un verbo.",
    "Otro paso. Entre 3 y 5 pasos en total."
  ],
  "confianza": "alta",
  "mensaje_hablado": "Lo mismo, resumido en 2 o 3 frases naturales, como si se lo dijeras en voz alta. Sin numeros de articulo largos."
}

Si fuera_de_dominio es true: deja normas vacio, pon en resumen la explicacion de por
que no puedes ayudar, y en pasos a que entidad debe acudir."""


# --------------------------------------------------------------------------- #
# Respuestas deterministicas (funcionan sin internet y sin ninguna llave)
# --------------------------------------------------------------------------- #

PASOS_GENERICOS = [
    "Reune tus pruebas: contrato, desprendibles de pago, correos, mensajes y "
    "nombres de companeros que hayan presenciado los hechos.",
    "Presenta un reclamo por escrito a tu empleador y quedate con una copia "
    "firmada o con el correo enviado. Ese reclamo interrumpe la prescripcion.",
    "Si no responden o la respuesta no te satisface, acude a la Inspeccion de "
    "Trabajo del Ministerio de Trabajo de tu ciudad. La atencion es gratuita.",
    "Puedes pedir asesoria gratuita en los consultorios juridicos de las "
    "universidades o en la Defensoria del Pueblo.",
]

SALUDOS = {
    "hola", "holi", "buenas", "hey", "ey", "saludos", "buendia", "quien eres",
    "que tal", "como estas", "como va", "ayuda", "hello", "hi", "buenos dias",
    "buenas tardes", "buenas noches", "buen dia", "que haces", "quien sos",
    "necesito ayuda", "me puedes ayudar", "puedes ayudarme", "hola que tal",
}

# Preguntas sobre el propio asistente. No son casos legales y no deben tratarse
# como fuera de dominio: preguntar "en que te especializas" es de lo primero que
# hace cualquiera que abre la herramienta.
META = (
    "especializa", "especialidad", "que puedes hacer", "que sabes",
    "que temas", "de que temas", "en que me puedes ayudar", "que normas",
    "para que sirves", "que haces", "quien eres", "como funcionas",
    "que me puedes decir", "cuales son tus temas", "que cubres",
    "en que ayudas", "que tipo de casos", "sobre que puedes",
)


# Charla que no es ni un caso legal ni una pregunta sobre la herramienta.
# Mandar a la Fiscalia a quien pregunta que dia es hoy queda ridiculo.
CHARLA = (
    "que dia es hoy", "que hora es", "que fecha es", "que fecha", "como te llamas",
    "cuantos anos tienes", "cuantos anos", "cuentame un chiste", "que tiempo hace",
    "hace calor", "hace frio", "como esta el clima", "quien gano", "como vas",
    "estas ahi", "eres humano", "eres una persona", "eres un robot",
    "te quiero", "gracias", "muchas gracias", "adios", "chao", "buenas noches",
)


def es_charla(consulta: str) -> bool:
    texto = " ".join(normalizar(consulta))
    return any(" ".join(normalizar(c)) in texto for c in CHARLA)


def es_pregunta_meta(consulta: str) -> bool:
    texto = " ".join(normalizar(consulta))
    return any(" ".join(normalizar(m)) in texto for m in META)


def respuesta_capacidades(normas: list[Norma]) -> dict:
    """Lista lo que el asistente cubre, leido del corpus real.

    Se genera desde /corpus en vez de escribirse a mano: si manana se anade o se
    quita una norma, esta respuesta se mantiene cierta sola.
    """
    temas = []
    for n in normas:
        t = n.tema.split("(")[0].strip().rstrip(".")
        if t and t not in temas:
            temas.append(t)

    return {
        "fuera_de_dominio": False,
        "saludo": True,
        "area_detectada": "derecho laboral",
        "resumen": (
            f"Me especializo en DERECHO LABORAL COLOMBIANO, y solo en eso. "
            f"Tengo cargadas {len(normas)} normas del Codigo Sustantivo del Trabajo "
            "y leyes relacionadas, y solo puedo responderte citandolas. Si tu caso "
            "es de otra area te lo digo, en vez de inventarme una respuesta."
        ),
        "normas": [],
        "pasos": temas,
        "confianza": "alta",
        "mensaje_hablado": (
            "Me especializo en derecho laboral colombiano. Puedo ayudarte con "
            "despidos y liquidaciones, acoso laboral, vacaciones, primas y "
            "cesantias, horas extras y jornada, embarazo y licencias, accidentes "
            "de trabajo y contratos. Cuentame tu caso."
        ),
        "modo": "deterministico",
    }


BIENVENIDA = {
    "fuera_de_dominio": False,
    "saludo": True,
    "area_detectada": "derecho laboral",
    "resumen": (
        "Soy Lexian. Te oriento sobre derecho laboral colombiano: despidos, "
        "liquidaciones, acoso en el trabajo, vacaciones, primas y cesantias. "
        "Cuentame que te paso con tus propias palabras, como se lo contarias a un "
        "amigo, y te digo que dice la ley y que puedes hacer."
    ),
    "normas": [],
    "pasos": [
        "Escribe que paso, cuando y quien estuvo involucrado.",
        "Si lo sabes, dime cuanto tiempo llevabas trabajando alli.",
        "No necesito tu cedula, ni tu telefono, ni tu direccion.",
    ],
    "confianza": "alta",
    "mensaje_hablado": (
        "Soy Lexian, tu asesor laboral. Cuentame que te paso en el trabajo "
        "con tus propias palabras y te digo que dice la ley."
    ),
    "modo": "deterministico",
}

DEMASIADO_CORTO = {
    "fuera_de_dominio": False,
    "saludo": True,
    "area_detectada": "derecho laboral",
    "resumen": (
        "Necesito un poco mas de detalle para poder ayudarte bien. Cuentame que "
        "paso exactamente: si te despidieron, si no te han pagado algo, si tu jefe "
        "te trata mal, o lo que sea que te este ocurriendo en el trabajo."
    ),
    "normas": [],
    "pasos": [
        "Describe la situacion en una o dos frases completas.",
        "Menciona cuanto tiempo llevabas en el trabajo, si viene al caso.",
    ],
    "confianza": "alta",
    "mensaje_hablado": (
        "Necesito un poco mas de detalle para ayudarte bien. Cuentame que paso "
        "exactamente en tu trabajo."
    ),
    "modo": "deterministico",
}

# Vocabulario que delata que la consulta SI es laboral, aunque el corpus no la
# cubra. Sin esto, preguntar por un sindicato recibia la respuesta de "acude a la
# Superintendencia de Industria y Comercio", que es un consejo equivocado.
VOCABULARIO_LABORAL = {
    "trabajo", "trabajar", "trabajador", "trabajadora", "trabajando", "laboral",
    "empleo", "empleado", "empleada", "empleador", "jefe", "patron", "empresa",
    "contrato", "contratado", "contratar", "salario", "sueldo", "nomina",
    "prestaciones", "liquidacion", "despido", "despidieron", "despedir",
    "renuncia", "renunciar", "renuncie", "oficina", "turno", "jornada",
    "horario", "sindicato", "huelga", "pension", "pensionar", "jubilacion",
    "cesantias", "vacaciones", "prima", "incapacidad", "arl", "eps",
    "cotizar", "cotizacion", "aportes", "companeros", "supervisor", "gerente",
    "contratista", "honorarios", "practicante", "aprendiz", "obrero",
    # Terminos que aparecen en consultas laborales aunque no nombren "trabajo":
    "licencia", "licencias", "certificado", "incapacidad", "incapacitado",
    "dotacion", "primas", "domingo", "domingos", "festivo", "festivos",
    "extras", "suplementario", "recargo", "subsidio", "auxilio", "embarazo",
    "embarazada", "maternidad", "paternidad", "lactancia", "indemnizacion",
    "reintegro", "acoso", "renuncio", "despedido", "despedida", "cesantia",
    "vacacion", "descanso", "salarial", "empleadora", "patronal",
}


# Senales inequivocas de OTRA area del derecho. Mandan sobre el vocabulario
# laboral: "me robaron en el trabajo" lleva la palabra "trabajo", pero un robo es
# un delito y remitir a esa persona al Ministerio de Trabajo es mandarla al sitio
# equivocado. Donde hay delito, la puerta es la Fiscalia.
OTRAS_AREAS = {
    "robaron", "robo", "robar", "robaste", "hurto", "hurtaron", "ladron",
    "estafa", "estafaron", "estafador", "delito", "penal", "fiscalia",
    "divorcio", "divorciar", "divorciarme", "custodia", "alimentos",
    "arriendo", "arrendador", "arrendatario", "inquilino", "deposito",
    "vecino", "vecinos", "choque", "chocaron", "transito", "comparendo",
    "herencia", "sucesion", "notaria", "escritura", "predial",
    "negligencia",
}


def hay_senal_de_otra_area(consulta: str) -> bool:
    return bool(set(normalizar(consulta)) & OTRAS_AREAS)


def es_tema_laboral(consulta: str) -> bool:
    terminos = set(normalizar(consulta))
    if terminos & OTRAS_AREAS:
        return False
    return bool(terminos & VOCABULARIO_LABORAL)


FUERA_DEL_CORPUS = {
    "fuera_de_dominio": False,
    "saludo": True,
    "area_detectada": "derecho laboral, pero fuera de mi corpus",
    "resumen": (
        "Tu caso SI es de derecho laboral, pero no esta entre las normas que tengo "
        "cargadas, asi que no puedo citarte el articulo exacto. Prefiero decirtelo "
        "antes que darte una respuesta que podria estar equivocada."
    ),
    "normas": [],
    "pasos": [
        "Acude al Ministerio de Trabajo: la orientacion es gratuita y puedes pedir "
        "cita en www.mintrabajo.gov.co o en la Inspeccion de Trabajo de tu ciudad.",
        "Los consultorios juridicos de las universidades atienden casos laborales "
        "sin costo.",
        "Si ademas ocurrio un delito (un robo, una agresion), denuncialo aparte "
        "ante la Fiscalia: son dos tramites distintos.",
        "Si quieres, reformula tu consulta: manejo despidos y liquidaciones, acoso "
        "laboral, vacaciones, primas y cesantias, horas extras y jornada, embarazo "
        "y licencias, accidentes de trabajo, contratos y periodo de prueba.",
    ],
    "confianza": "baja",
    "mensaje_hablado": (
        "Tu caso si es laboral, pero no esta entre las normas que tengo cargadas. "
        "Prefiero decirtelo antes que equivocarme. Te recomiendo acudir al "
        "Ministerio de Trabajo, donde la orientacion es gratuita."
    ),
    "modo": "deterministico",
}

FUERA_DE_DOMINIO = {
    "fuera_de_dominio": True,
    "area_detectada": "fuera del derecho laboral",
    "resumen": (
        "Tu caso no parece ser de derecho laboral colombiano, que es lo unico que "
        "yo manejo. Prefiero decirtelo antes que darte una respuesta que podria "
        "estar equivocada."
    ),
    "normas": [],
    "pasos": [
        "Si es un problema de compras, garantias o estafas de consumo: acude a la "
        "Superintendencia de Industria y Comercio (SIC).",
        "Si te robaron, te agredieron o crees que hubo un delito: denuncialo ante "
        "la Fiscalia General de la Nacion o en la estacion de policia mas cercana.",
        "Para otros temas civiles o de familia: busca el consultorio juridico "
        "gratuito de una universidad cercana o la Defensoria del Pueblo.",
    ],
    "confianza": "alta",
    "mensaje_hablado": (
        "Lo siento, ese caso se sale de lo mio. Yo solo manejo derecho laboral "
        "colombiano y prefiero decirtelo antes que inventarte una respuesta. "
        "Te recomiendo acudir a la entidad que te indico en pantalla."
    ),
    "modo": "deterministico",
}


def respuesta_sin_conexion(resultados: list[tuple[Norma, float]]) -> dict:
    """Arma la respuesta solo con el corpus, sin llamar a ningun modelo."""
    if not resultados:
        return dict(FUERA_DE_DOMINIO)  # el enrutado ya ocurrio en responder()

    principal = resultados[0][0]
    relevantes = [n for n, _ in resultados[:4]]

    return {
        "fuera_de_dominio": False,
        "area_detectada": "derecho laboral",
        "resumen": (
            f"Segun lo que me cuentas, tu caso se relaciona principalmente con "
            f"{principal.tema.lower()}."
            + (
                " Tambien pueden aplicarte: "
                + "; ".join(n.tema.lower() for n in relevantes[1:])
                + "."
                if len(relevantes) > 1
                else ""
            )
            + " Te muestro el texto exacto de cada norma para que lo compruebes "
            "tu mismo."
        ),
        "normas": [
            {
                "cita": n.cita,
                "por_que": n.tema,
                "fragmento": n.fragmento(420),
                "fuente": n.fuente,
            }
            for n in relevantes
        ],
        "pasos": PASOS_GENERICOS,
        "confianza": "media",
        "mensaje_hablado": (
            f"Tu caso tiene que ver con {principal.tema.lower()}. "
            f"La norma principal que te respalda es {principal.cita}. "
            "En pantalla te dejo el texto exacto y los pasos que puedes seguir."
        ),
        "modo": "sin_conexion",
    }


# --------------------------------------------------------------------------- #
# Respuesta con Claude
# --------------------------------------------------------------------------- #


def _contexto(resultados: list[tuple[Norma, float]]) -> str:
    partes = []
    for norma, puntaje in resultados:
        partes.append(
            f"--- FRAGMENTO (relevancia {puntaje:.1f}) ---\n"
            f"CITA: {norma.cita}\n"
            f"TEMA: {norma.tema}\n"
            f"FUENTE: {norma.fuente}\n"
            f"TEXTO:\n{norma.fragmento(900)}"
        )
    return "\n\n".join(partes)


def _extraer_json(bruto: str) -> dict:
    texto = re.sub(r"^```(?:json)?|```$", "", bruto.strip(), flags=re.MULTILINE).strip()
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fin == -1:
        raise ValueError("La respuesta no contenia un objeto JSON")
    return json.loads(texto[inicio : fin + 1])


def _pedir_a_claude(peticion: str) -> str:
    # Sin reintentos y con un tope de 25 s: si no hay internet o la llave no
    # sirve, queremos caer al modo sin conexion de inmediato, no dejar a la
    # persona mirando un indicador de carga durante medio minuto.
    cliente = anthropic.Anthropic(timeout=25.0, max_retries=0)
    comunes = dict(
        model=MODELO,
        max_tokens=2000,
        system=INSTRUCCION,
        messages=[{"role": "user", "content": peticion}],
    )
    # Esfuerzo bajo: la conversacion tiene que sentirse inmediata. Si la version
    # del SDK no admite el parametro, repetimos sin el en vez de fallar.
    try:
        respuesta = cliente.messages.create(**comunes, output_config={"effort": "low"})
    except TypeError:
        respuesta = cliente.messages.create(**comunes)

    return "".join(b.text for b in respuesta.content if b.type == "text")


def responder(consulta: str, resultados: list[tuple[Norma, float]]) -> dict:
    """Devuelve la respuesta estructurada. Nunca lanza por fallo de red."""

    limpio = consulta.strip().lower().strip("!?.,¿¡ ")
    palabras = normalizar(consulta)      # solo terminos con carga semantica
    crudas = len(consulta.split())       # palabras tal cual las escribio la persona

    # Un saludo NO es un caso fuera de dominio: es alguien que acaba de llegar.
    # Confundir las dos cosas hace que la herramienta parezca rota.
    if limpio in SALUDOS or es_charla(consulta):
        return dict(BIENVENIDA)

    # Un robo, una estafa o un divorcio no son asuntos laborales aunque ocurran
    # en el trabajo. Esto se decide ANTES de mirar el corpus, porque si no la
    # busqueda encuentra coincidencias casuales ("empresa", "jefe") y acaba
    # citando una norma laboral para un delito.
    if hay_senal_de_otra_area(consulta):
        return dict(FUERA_DE_DOMINIO)

    # Pedimos mas detalle SOLO cuando de verdad no hay un relato: una o dos
    # palabras sueltas, o texto sin ningun termino reconocible ("asdasd").
    # Una frase completa como "me robaron en el metro" SI es un relato, aunque
    # tenga pocas palabras con carga: eso es un caso fuera de dominio, y hay que
    # decirlo, no pedir mas detalle.
    if not resultados and crudas < 4 and len(palabras) < 3:
        return dict(BIENVENIDA if crudas <= 1 else DEMASIADO_CORTO)

    # Ya con contenido suficiente: si el corpus no devuelve nada, el caso esta
    # fuera de dominio, y eso lo sabemos con certeza sin llamar al modelo.
    if not resultados:
        # Distinguir "esto no es laboral" de "es laboral pero no lo tengo" importa:
        # mandar a alguien con un problema sindical a la Superintendencia de
        # Industria y Comercio es darle un consejo equivocado.
        return dict(FUERA_DEL_CORPUS if es_tema_laboral(consulta) else FUERA_DE_DOMINIO)

    peticion = (
        f"CONSULTA DE LA PERSONA:\n{consulta}\n\n"
        f"FRAGMENTOS DEL CORPUS NORMATIVO:\n{_contexto(resultados)}"
    )

    try:
        datos = _extraer_json(_pedir_a_claude(peticion))
    except Exception as error:  # noqa: BLE001
        # Sin internet, sin llave o con la API caida seguimos respondiendo.
        print(f"[llm] usando el modo sin conexion: {type(error).__name__}: {error}")
        return respuesta_sin_conexion(resultados)

    # Blindaje: aunque el modelo se desvie del formato, la interfaz no se rompe.
    datos.setdefault("fuera_de_dominio", False)
    datos.setdefault("area_detectada", "derecho laboral")
    datos.setdefault("resumen", "")
    datos.setdefault("normas", [])
    datos.setdefault("pasos", [])
    datos.setdefault("confianza", "media")
    datos.setdefault("saludo", False)
    datos.setdefault("mensaje_hablado", datos.get("resumen", ""))
    datos["modo"] = "con_ia"

    if datos["fuera_de_dominio"]:
        datos["normas"] = []

    return datos
