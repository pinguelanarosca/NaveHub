# Debugging

## Tracebacks e logs

Use `tools.debugkit.configure_debug_logging()` no início de sessões de debug
ou em scripts de investigação para obter logs estruturados e traceback rico.

## Processos

Use `tools.debugkit.list_processes()` para ver rapidamente processos, PID,
CPU e RSS em uma sessão local.

## Profiling

Use `tools.debugkit.profile_section()` para medir trechos lentos sem alterar a
aplicação principal.

## Browser debugging

Use `scripts/debug_playwright.mjs <url>` para reproduzir bugs no navegador.
