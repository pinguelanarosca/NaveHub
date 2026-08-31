"""Helpers leves para debugging, profiling e inspeção local.

O módulo não altera o aplicativo principal. Ele só centraliza utilitários
úteis para investigação de bugs e troubleshooting durante o desenvolvimento.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import psutil
import structlog
from rich.console import Console
from rich.traceback import install as install_rich_traceback

console = Console(stderr=True)


def configure_debug_logging(level: int = logging.INFO) -> None:
    """Configura logging estruturado com saída amigável para debug."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        stream=sys.stderr,
    )
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
    install_rich_traceback(show_locals=True, suppress=[Path.cwd()])


def format_exception(exc: BaseException) -> str:
    """Retorna traceback bonito para análise manual ou logs."""
    console = Console(stderr=False, record=True, width=120)
    console.print_exception(show_locals=True)
    return console.export_text()


def list_processes(limit: int = 20) -> list[dict[str, object]]:
    """Lista processos relevantes para inspeção rápida."""
    rows: list[dict[str, object]] = []
    for proc in psutil.process_iter(attrs=["pid", "name", "status", "cpu_percent", "memory_info"]):
        info = proc.info
        memory = info.get("memory_info")
        rss = getattr(memory, "rss", None) if memory is not None else None
        rows.append(
            {
                "pid": info.get("pid"),
                "name": info.get("name"),
                "status": info.get("status"),
                "cpu_percent": info.get("cpu_percent"),
                "rss": rss,
            }
        )
        if len(rows) >= limit:
            break
    return rows


@dataclass
class ProfileResult:
    total_seconds: float
    top_stats: str


@contextmanager
def profile_section(label: str = "profile") -> Iterator[None]:
    """Context manager simples para medir trechos críticos."""
    from pyinstrument import Profiler

    profiler = Profiler()
    profiler.start()
    try:
        yield
    finally:
        profiler.stop()
        console.rule(f"[bold]Profiling: {label}")
        console.print(profiler.output_text(unicode=True, color=True))

