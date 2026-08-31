#!/usr/bin/env python3
"""
NaveHub - Etapa 5
Carrega configuração e inicia a aplicação.
"""

import json
from pathlib import Path

from ui.app import create_main_window

# Diretórios do usuário
BASE_DIR = Path.home() / ".navehub"
CONFIG_FILE = BASE_DIR / "config.json"


def ensure_dirs():
    """Cria os diretórios necessários."""
    try:
        BASE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Diretório base: {BASE_DIR}")
    except Exception as e:
        print(f"ERRO ao criar diretório: {e}")
        raise


def load_config():
    """Carrega ou cria o arquivo de configuração padrão."""
    default_config = {
        "browser": "google-chrome",          # ← ALTERADO para Chrome normal
        "homepage": "https://site.com",
        "window_width": 500,
        "window_height": 900
    }

    print(f"Procurando config em: {CONFIG_FILE}")

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                config = json.load(f)
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                print("Config carregada do arquivo.")
                return config
        except Exception as e:
            print(f"ERRO ao ler config.json: {e}")

    # Cria o arquivo com os valores padrão
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        print(f"Arquivo config.json CRIADO com sucesso em: {CONFIG_FILE}")
    except Exception as e:
        print(f"ERRO ao criar config.json: {e}")
        raise

    return default_config


def main():
    ensure_dirs()
    config = load_config()
    print(f"Config final: {config}")
    app = create_main_window(config)
    app.run()


if __name__ == "__main__":
    main()
