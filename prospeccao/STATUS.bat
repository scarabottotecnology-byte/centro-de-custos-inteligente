@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Programas rodando:
docker compose ps
echo.
echo Funil:
docker compose run --rm cli funil
echo.
echo Ultimas mensagens do robo:
docker compose logs --tail 30 worker
echo.
pause
