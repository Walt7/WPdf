@echo off
cd /d %~dp0
python -m wpdf %*
if errorlevel 1 pause
