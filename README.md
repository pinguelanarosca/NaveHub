# NaveHub

## Operação e DevOps

O projeto agora inclui:

- `Dockerfile` para empacotar a aplicação;
- `docker-compose.yml` para execução local e healthcheck;
- GitHub Actions para CI e deploy via SSH;
- scripts locais para healthcheck, logs e rollback.

### Comandos úteis

```bash
python healthcheck.py
bash scripts/logs.sh
bash scripts/rollback.sh <release|tag|backup-path>
```

## Instalação no Linux

Em Debian, Ubuntu e derivados, use o instalador oficial:

```bash
./Instalar-NaveHub.sh
```

Não use `sudo` nesse comando. O instalador solicita a senha do administrador somente quando precisa instalar Python, Tkinter e Chromium. Em seguida o NaveHub cria um ambiente Python próprio, instala o Pillow, configura um navegador compatível e registra o aplicativo:

- no menu de aplicativos;
- na área de trabalho;
- nos favoritos do dock, quando o GNOME permitir.

O instalador é limpo: a primeira abertura não contém contas, perfis, cookies, sessões nem configurações antigas. Crie as contas pelo botão **Nova conta** dentro de cada plataforma.

O programa é instalado em `~/.local/share/navehub`. As contas, cookies e configurações que você criar ficam em `~/.navehub`.
