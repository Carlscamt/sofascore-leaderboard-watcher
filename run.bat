@echo off
echo Starting Sofascore Monitor...
cd /d "%~dp0.."
python sofascore_monitor/main.py
pause
