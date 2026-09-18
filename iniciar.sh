#!/usr/bin/env bash
# Arranque con un solo comando en Linux y macOS.
set -e

echo
echo " === Asesor Laboral de Bolsillo ==="
echo

# La aplicacion funciona sin ninguna llave: si no hay .env lo creamos desde la
# plantilla y seguimos. Nunca abortamos por esto.
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo " [i] Se creo un archivo .env a partir de la plantilla."
  echo "     La aplicacion respondera desde el corpus normativo."
  echo "     Para respuestas redactadas por IA, pon tu ANTHROPIC_API_KEY en .env"
  echo "     (se obtiene en https://console.anthropic.com)."
  echo
fi

if [ ! -d "venv" ]; then
  echo " [1/3] Creando entorno virtual..."
  python3 -m venv venv
fi

echo " [2/3] Instalando dependencias..."
source venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo " [3/3] Arrancando la aplicacion en http://127.0.0.1:8000"
echo
python run.py
