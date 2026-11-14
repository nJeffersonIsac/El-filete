@echo off
chcp 65001 >nul
title El Filete POS - Servidor
echo.
echo ============================================================
echo   RESTAURANTE EL FILETE - SISTEMA POS (Version Final AED)
echo ============================================================
echo.

cd /d "%~dp0"

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado. Instala Python 3.9+
    pause
    exit /b 1
)

REM Instalar dependencias si no existen
echo Verificando dependencias...
python -c "import flask, flask_cors" >nul 2>&1
if errorlevel 1 (
    echo Instalando Flask y Flask-CORS...
    pip install flask flask-cors
)

REM Inicializar base de datos si no existe
if not exist "ElFilete.db" (
    echo.
    echo [!] Base de datos no encontrada. Inicializando...
    python init_db.py --force
    echo.
)

echo.
echo [OK] Iniciando servidor en http://localhost:5000
echo.
echo Usuarios de prueba:
echo   admin   / admin123
echo   cajero1 / cajero123
echo   mesero1 / mesero123
echo.
echo Presiona Ctrl+C para detener el servidor.
echo ============================================================
echo.

start "" "http://localhost:5000"
python server.py

pause
