@echo off
rem Content factory dashboard: http://127.0.0.1:8790 (local only). Close this window or press Ctrl+C to stop it.
cd /d "%~dp0"
C:\Python314\python -m factory.dashboard %*
