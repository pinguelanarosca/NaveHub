# NaveHub

## Versão 1.9.0

As plataformas 8U, 777, 365GG e 93H vêm com os perfis padrão da instalação atual. Cada perfil recebe um diretório de navegador próprio, sem cookies ou sessões copiadas; faça login ao abrir a conta pela primeira vez.

A categoria **Outras** também usa um perfil isolado para cada conta criada. Perfis de uma instalação anterior na categoria **Legalizadas** são migrados para **Outras**.

As contas isoladas de 8U, 777, 365GG e 93H têm controles de **Retrato/Paisagem** integrados.
Pressione **Alt+Shift+O** na janela da conta para mostrar os botões e pressione novamente para ocultá-los.
O painel começa oculto. Ocultar o painel conserva a orientação escolhida.
Clicar novamente no modo ativo restaura a orientação e as dimensões anteriores da janela.

Após atualizar, reabra o NaveHub e as janelas das contas.

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

Em uma instalação nova, o aplicativo cria os perfis padrão de 8U, 777, 365GG e 93H. Esses perfis começam sem cookies, sessões ou credenciais. A categoria **Outras** começa vazia; crie nela contas pelo botão **Nova conta**.

O programa é instalado em `~/.local/share/navehub`. As contas, cookies e configurações que você criar ficam em `~/.navehub`.
