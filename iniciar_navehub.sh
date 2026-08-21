#!/bin/bash
# Launcher NaveHub — usa venv e substitui o shell (exec) para o dock
# associar a janela ao atalho (StartupWMClass=NaveHub).
cd "$(dirname "$(readlink -f "$0")")" || exit 1

if [ -x "./venv/bin/python" ]; then
  exec ./venv/bin/python main.py
else
  exec python3 main.py
fi
