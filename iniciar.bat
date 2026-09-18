@echo off
REM Arranque con un solo comando en Windows.
setlocal

echo.
echo  === Asesor Laboral de Bolsillo ===
echo.

REM La aplicacion funciona sin ninguna llave: si no hay .env lo creamos desde la
REM plantilla y seguimos. Nunca abortamos por esto.
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo  [i] Se creo un archivo .env a partir de la plantilla.
    echo      La aplicacion respondera desde el corpus normativo incluido.
    echo      Para respuestas redactadas por IA, pon tu ANTHROPIC_API_KEY en .env
    echo      ^(se obtiene en https://console.anthropic.com^).
    echo.
)

if not exist "venv" (
    echo  [1/3] Creando entorno virtual...
    python -m venv venv
)

echo  [2/3] Instalando dependencias...
venv\Scripts\python.exe -m pip install --quiet --upgrade pip
venv\Scripts\python.exe -m pip install --quiet -r requirements.txt

echo  [3/3] Arrancando la aplicacion en http://127.0.0.1:8000
echo.
venv\Scripts\python.exe run.py

endlocal
