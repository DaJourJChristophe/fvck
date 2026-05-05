@echo off
set SCRIPT_DIR=%~dp0
python -X dev -X faulthandler bin/start.py %*
