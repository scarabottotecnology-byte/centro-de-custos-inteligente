@echo off
chcp 65001 >nul
cd /d "%~dp0"
docker compose stop
echo.
echo Robo pausado. Para voltar, rode o INICIAR.bat.
pause
