@echo off
setlocal
cd /d "%~dp0.."
py -3 python\cli.py reserve-once
