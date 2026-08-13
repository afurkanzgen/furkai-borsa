@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ==========================================
echo FurkAI V41 - Baslatiliyor...
echo ==========================================
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo HATA: Python 3 bulunamadi.
    pause
    exit /b 1
  )
  set "PY=python"
)
echo Sunucu baslatiliyor...
start "FurkAI V41 Server" cmd /k "%PY% server.py"
echo Sunucu hazir olana kadar bekleniyor...
set /a N=0
:WAIT
set /a N+=1
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:8798/api/health; if($r.StatusCode -eq 200){exit 0}else{exit 1} } catch { exit 1 }" >nul 2>nul
if %errorlevel%==0 goto READY
if %N% GEQ 30 (
  echo.
  echo HATA: Sunucu 60 saniye icinde hazir olmadi.
  echo FurkAI V41 Server penceresindeki hata mesajini kontrol edin.
  pause
  exit /b 2
)
timeout /t 2 /nobreak >nul
goto WAIT
:READY
echo Sunucu HAZIR.
echo Bilgisayar: http://127.0.0.1:8798/
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /R /C:"IPv4 Address" /C:"IPv4 Adres"') do (set "IP=%%A" & goto GOTIP)
:GOTIP
set "IP=%IP: =%"
if not "%IP%"=="" echo Telefon ^(ayni Wi-Fi^): http://%IP%:8798/
start "" http://127.0.0.1:8798/
echo Telefon icin yukaridaki Wi-Fi adresini Safari'ye yaz.
echo Tamam.
exit /b 0
