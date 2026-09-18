@echo off
REM Arranque con un solo comando en Windows.
setlocal

echo.
echo  === Asesor Laboral de Bolsillo ===
echo.

if not exist ".env" (
    echo  [!] No existe el archivo .env
    echo      Copia .env.example como .env y pon tu GEMINI_API_KEY dentro.
    echo      La llave se obtiene gratis en https://aistudio.google.com/apikey
    echo.
    pause
    exit /b 1
)

if not exist "venv\" (
    echo  [1/3] Creando entorno virtual...
    python -m venv venv
)

echo  [2/3] Instalando dependencias...
call venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo  [3/3] Arrancando la aplicacion...
echo.
python run.py

endlocal
