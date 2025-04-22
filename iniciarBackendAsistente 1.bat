@echo off
REM Abre una nueva ventana de consola, activa el entorno y corre Flask
start "Servidor Flask - SEDI" cmd /k "cd backend-asistente && call ..\venv\Scripts\activate && python main_app.py"
