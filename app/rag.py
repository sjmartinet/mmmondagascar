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
        """Devuelve las normas mas parecidas, de mayor a menor puntaje."""
        puntajes = self._indice.get_scores(normalizar(consulta))
        mejores = sorted(
            zip(self.normas, puntajes), key=lambda par: par[1], reverse=True
        )
        return [(n, float(p)) for n, p in mejores[:cuantas] if p > 0]
