@echo off
REM Mapeador Tributario PR - clique duas vezes para abrir a interface.
REM Esta janela e o servidor: fecha-la (ou Ctrl+C) encerra a ferramenta.

chcp 65001 >nul 2>&1
title Mapeador Tributario PR
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

echo.
echo   Mapeador de Consultas e Regimes Especiais - PR
echo   ---------------------------------------------
echo   Abrindo no navegador... a janela pode demorar alguns segundos.
echo   Mantenha ESTA janela aberta enquanto usar a ferramenta.
echo.

REM Procura um Python utilizavel: o launcher "py" primeiro, depois "python".
set "PY="
py -V >nul 2>&1 && set "PY=py"
if not defined PY (
    python -V >nul 2>&1 && set "PY=python"
)

if not defined PY (
    echo   [ERRO] Python nao encontrado.
    echo.
    echo   Instale o Python 3.10 ou superior em https://www.python.org/downloads/
    echo   e marque a opcao "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

%PY% iniciar.py
set "ERR=%ERRORLEVEL%"

if not "%ERR%"=="0" (
    echo.
    echo   [ERRO] A ferramenta encerrou com o codigo %ERR%.
    echo   Leia a mensagem acima: normalmente diz o que falta instalar.
    echo.
    pause
)

exit /b %ERR%
