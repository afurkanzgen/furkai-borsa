@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title FurkAI BIST V15.9.6

echo ========================================
echo          FurkAI BIST V15.9.6
echo ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [HATA] Python bulunamadi. Python 3.10+ gerekli.
  pause
  exit /b 1
)

python -c "import cryptography,fastapi,uvicorn,dotenv" >nul 2>nul
if errorlevel 1 (
  echo [1/4] Gerekli paket kuruluyor...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [HATA] Gerekli Python paketleri kurulamadı.
    pause
    exit /b 1
  )
) else (
  echo [1/4] Python paketleri hazir.
)

REM Gercekten secilen portu server.py'ye environment variable olarak aktar.
for /f %%P in ('python -c "import socket;s=socket.socket();s.bind((chr(49)+chr(50)+chr(55)+chr(46)+chr(48)+chr(46)+chr(48)+chr(46)+chr(49),0));print(s.getsockname()[1]);s.close()"') do set "PORT=%%P"
if not defined PORT set "PORT=8799"
set "FURKAI_PORT=%PORT%"
set "PORT=%PORT%"

echo [2/4] Port: %PORT%
echo [3/4] Sunucu baslatiliyor...

REM Tek CMD: server ayni pencerenin arka planinda calisir.
start "FurkAI Server" /b cmd /c "set PORT=%PORT%&&python -m uvicorn api_fast:app --host 127.0.0.1 --port %PORT%"

python wait_server.py %PORT% 30
if errorlevel 1 (
  echo.
  echo [HATA] Sunucu baslatilamadi.
  echo Yukaridaki Python hatasini kontrol edin.
  pause
  exit /b 1
)

echo [4/4] Tarayici aciliyor...
start "" "http://127.0.0.1:%PORT%/"
echo.
echo FurkAI hazir: http://127.0.0.1:%PORT%/
echo Bu pencereyi kapatmayin.
echo.
pause
