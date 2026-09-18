#!/usr/bin/env bash
# Arranque con un solo comando en Linux y macOS.
set -e

echo
echo " === Asesor Laboral de Bolsillo ==="
echo

if [ ! -f ".env" ]; then
  echo " [!] No existe el archivo .env"
  echo "     Copia .env.example como .env y pon tu GEMINI_API_KEY dentro."
  echo "     La llave se obtiene gratis en https://aistudio.google.com/apikey"
  exit 1
fi

if [ ! -d "venv" ]; then
  echo " [1/3] Creando entorno virtual..."
  python3 -m venv venv
fi

echo " [2/3] Instalando dependencias..."
source venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo " [3/3] Arrancando la aplicacion..."
echo
python run.py
