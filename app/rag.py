"""Recuperacion de normas sobre el corpus local.

Usamos BM25 en lugar de embeddings a proposito: con menos de 30 documentos la
busqueda lexica es igual de precisa, no consume cuota de ninguna API, no exige
descargar modelos y funciona sin conexion. Eso mantiene el arranque del proyecto
en una maquina limpia a una sola instruccion.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"

# Palabras sin carga semantica en consultas en espanol.
VACIAS = {
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las", "por",
    "un", "para", "con", "no", "una", "su", "al", "lo", "como", "mas", "pero",
    "sus", "le", "ya", "o", "este", "si", "porque", "esta", "entre", "cuando",
    "muy", "sin", "sobre", "tambien", "me", "hasta", "hay", "donde", "quien",
    "desde", "todo", "nos", "durante", "todos", "uno", "les", "ni", "contra",
    "ese", "eso", "ante", "ellos", "e", "esto", "mi", "antes", "algunos",
    "que", "unos", "yo", "otro", "otras", "otra", "el", "tanto", "esa", "estos",
    "mucho", "quienes", "nada", "muchos", "cual", "sea", "poco", "ella", "estar",
    "haber", "estas", "estaba", "estamos", "algunas", "algo", "nosotros", "es",
}


def normalizar(texto: str) -> list[str]:
    """Minusculas, sin tildes, solo palabras utiles."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )
    palabras = re.findall(r"[a-z0-9]+", sin_tildes)
    return [p for p in palabras if len(p) > 2 and p not in VACIAS]


@dataclass
class Norma:
    """Un documento del corpus, ya separado en sus campos."""

    archivo: str
    norma: str
    articulo: str
    tema: str
    fuente: str
    texto: str

    @property
    def claves(self) -> str:
        """La linea PALABRAS CLAVE: como la gente describe el problema."""
        partes = self.texto.split("PALABRAS CLAVE:")
        return partes[1] if len(partes) > 1 else ""

    @property
    def cita(self) -> str:
        return f"{self.norma}, articulo {self.articulo}" if self.articulo else self.norma

    def fragmento(self, maximo: int = 420) -> str:
        """Trozo del texto legal que se le muestra al usuario como prueba."""
        cuerpo = self.texto.split("PALABRAS CLAVE:")[0].strip()
        cuerpo = "\n".join(
            l for l in cuerpo.splitlines()
            if not l.startswith(("NORMA:", "ARTICULO:", "TEMA:", "FUENTE:"))
        ).strip()
        if len(cuerpo) <= maximo:
            return cuerpo
        return cuerpo[:maximo].rsplit(" ", 1)[0] + "..."


def _campo(texto: str, etiqueta: str) -> str:
    coincidencia = re.search(rf"^{etiqueta}:\s*(.+)$", texto, re.MULTILINE)
    return coincidencia.group(1).strip() if coincidencia else ""


class BuscadorNormativo:
    """Indice BM25 sobre los documentos de /corpus."""

    def __init__(self, directorio: Path = CORPUS_DIR) -> None:
        self.directorio = directorio
        self.normas: list[Norma] = []
        self._cargar()
        if not self.normas:
            raise RuntimeError(
                f"No se encontro ningun documento en {directorio}. "
                "El corpus normativo es obligatorio para que la aplicacion funcione."
            )
        self._indice = BM25Okapi([self._tokens(n) for n in self.normas])

        # Campos curados de cada norma y frecuencia documental de cada termino.
        # Una palabra que aparece en media biblioteca ("dia", "trabajo") no
        # prueba nada: "que dia es hoy" enganchaba con "dias festivos" y salia
        # respondido con el recargo dominical. Exigimos al menos un termino
        # DISCRIMINANTE, o sea poco frecuente en el corpus.
        self._curado = [
            set(normalizar(n.tema)) | set(normalizar(n.claves)) for n in self.normas
        ]
        self._frecuencia: dict[str, int] = {}
        for campos in self._curado:
            for termino in campos:
                self._frecuencia[termino] = self._frecuencia.get(termino, 0) + 1
        self._tope_comun = max(2, int(len(self.normas) * 0.4))

    # Palabras que aparecen en el texto legal pero no dicen nada del caso de la
    # persona: unidades de tiempo y genericos. Coinciden por casualidad
    # ("que DIA es hoy" con "DIAS festivos"), asi que nunca pueden ser la unica
    # prueba de que una norma es relevante.
    DEBILES = {
        "dia", "dias", "hoy", "ayer", "manana", "ano", "anos", "mes", "meses",
        "hora", "horas", "semana", "semanas", "tiempo", "fecha", "momento",
        "trabajo", "trabajar", "laboral", "laborales", "persona", "personas",
        "cosa", "cosas", "caso", "casos", "vez", "veces", "parte", "partes",
        "casa", "casas", "hogar", "lugar", "sitio", "empresa", "empresas",
    }

    @staticmethod
    def _tokens(norma: "Norma") -> list[str]:
        """Texto indexable con los campos ponderados.

        Sin esto, una palabra suelta en el cuerpo de un articulo pesa lo mismo
        que la palabra que define su tema: "vacaciones" aparece de pasada en
        media docena de normas, y la busqueda devolvia la equivocada. Repetir el
        tema y las palabras clave los hace pesar mas, que es como la gente
        realmente formula su consulta.
        """
        cuerpo = normalizar(norma.texto)
        tema = normalizar(norma.tema) * 3
        claves = normalizar(norma.claves) * 2
        return tema + claves + cuerpo

    def _cargar(self) -> None:
        for ruta in sorted(self.directorio.glob("*.txt")):
            texto = ruta.read_text(encoding="utf-8")
            self.normas.append(
                Norma(
                    archivo=ruta.name,
                    norma=_campo(texto, "NORMA"),
                    articulo=_campo(texto, "ARTICULO"),
                    tema=_campo(texto, "TEMA"),
                    fuente=_campo(texto, "FUENTE"),
                    texto=texto,
                )
            )

    def buscar(self, consulta: str, cuantas: int = 4) -> list[tuple[Norma, float]]:
        """Devuelve las normas mas parecidas, de mayor a menor puntaje.

        Una norma solo se acepta si la consulta coincide con su TEMA o con sus
        PALABRAS CLAVE. Sin este filtro, una palabra suelta del cuerpo bastaba
        para dar un falso positivo: "no me DEJA dormir" enganchaba con "no DEJA
        de serlo" del articulo 23, y un problema con el vecino acababa
        respondido con derecho laboral. Los campos curados dicen de que trata la
        norma; el cuerpo es texto legal lleno de conectores.
        """
        terminos = set(normalizar(consulta))
        if not terminos:
            return []

        puntajes = self._indice.get_scores(list(terminos))
        mejores = sorted(
            zip(self.normas, puntajes), key=lambda par: par[1], reverse=True
        )

        # En consultas largas exigimos DOS coincidencias en los campos curados.
        # Con una sola bastaba para que "Me despidieron... de trabajo" arrastrara
        # la ley de accidentes de trabajo, que comparte la palabra "trabajo" y
        # nada mas. En consultas cortas ("vacaciones") una coincidencia es todo
        # lo que puede haber, asi que ahi basta con una.
        minimo = 2 if len(terminos) >= 4 else 1

        indice_por_norma = {id(n): i for i, n in enumerate(self.normas)}

        aceptadas: list[tuple[Norma, float]] = []
        for norma, puntaje in mejores:
            if puntaje <= 0:
                continue
            curado = self._curado[indice_por_norma[id(norma)]]
            comunes = terminos & curado
            if len(comunes) < minimo:
                continue
            # Al menos una coincidencia tiene que ser poco frecuente Y con
            # significado propio. Sin las dos condiciones, cualquier consulta con
            # la palabra "dia" o "trabajo" enganchaba con alguna norma.
            fuertes = [
                t for t in comunes
                if t not in self.DEBILES
                and self._frecuencia.get(t, 0) <= self._tope_comun
            ]
            if not fuertes:
                continue
            aceptadas.append((norma, float(puntaje)))
            if len(aceptadas) == cuantas:
                break
        return aceptadas
