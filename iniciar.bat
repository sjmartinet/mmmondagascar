@echo off
REM Arranque con un solo comando en Windows.
REM Uso:  .\iniciar.bat     (o doble clic sobre el archivo)

cd /d "%~dp0"

echo.
echo  ===========================================
echo   Asesor Laboral de Bolsillo - Mondagascar
echo  ===========================================
echo.

REM ---------- 1. Buscar Python ----------
REM Probamos "py -3" primero: es el lanzador oficial de Windows y evita el alias
REM de la Microsoft Store, que es la causa mas comun de "no se reconoce python".
set PY=
py -3 --version >nul 2>&1
if %errorlevel%==0 set PY=py -3
if "%PY%"=="" (
    python --version >nul 2>&1
    if %errorlevel%==0 set PY=python
)

if "%PY%"=="" (
    echo  [ERROR] No se encontro Python en este equipo.
    echo.
    echo   Instalalo desde https://www.python.org/downloads/
    echo   IMPORTANTE: marca la casilla "Add python.exe to PATH" al instalar.
    echo   Despues cierra esta ventana, abre una nueva y vuelve a ejecutar.
    echo.
    pause
    exit /b 1
)

echo  Python encontrado:
%PY% --version
echo.

REM ---------- 2. Variables de entorno ----------
REM La aplicacion funciona sin ninguna llave: si no hay .env lo creamos desde la
REM plantilla y seguimos. Nunca abortamos por esto.
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo  [i] Se creo el archivo .env a partir de la plantilla.
    echo      La aplicacion respondera desde el corpus normativo incluido.
    echo.
)

REM ---------- 3. Entorno virtual ----------
if not exist "venv\Scripts\python.exe" (
    echo  [1/3] Creando entorno virtual...
    %PY% -m venv venv
) else (
    echo  [1/3] El entorno virtual ya existe.
)

if not exist "venv\Scripts\python.exe" (
    echo.
    echo  [ERROR] No se pudo crear el entorno virtual.
    echo   Ejecuta manualmente para ver el detalle:  %PY% -m venv venv
    echo.
    pause
    exit /b 1
)

REM ---------- 4. Dependencias ----------
echo  [2/3] Instalando dependencias ^(puede tardar un minuto^)...
"venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
"venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo.
    echo  [ERROR] Fallo la instalacion de dependencias.
    echo   Revisa tu conexion a internet y vuelve a intentarlo.
    echo.
    pause
    exit /b 1
)

REM ---------- 5. Arrancar ----------
echo  [3/3] Arrancando...
echo.
echo   Abre en tu navegador:  http://127.0.0.1:8000
echo   Para detener la aplicacion pulsa Ctrl+C
echo.
"venv\Scripts\python.exe" run.py

echo.
echo  La aplicacion se detuvo.
pause
