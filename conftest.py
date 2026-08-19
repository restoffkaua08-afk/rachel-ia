"""Conftest raiz para pytest.

Adiciona RACHEL_CORE/src e RACHEL_PLATFORM/RUNTIME/SRC ao sys.path
para que testes possam importar `rachel_core.*` e módulos runtime
(`cognitive_runtime`, `agent_runtime`, `tools_runtime`, etc.) sem
scripts customizados.

Garante que variáveis de ambiente necessárias pelo runtime_paths
estejam definidas antes de qualquer import.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
RUNTIME_SRC = ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"
CORE_SRC = ROOT / "RACHEL_CORE" / "src"
BRIDGE_SRC = ROOT / "APP" / "bridge"

# Configura RACHEL_RUNTIME_ROOT antes de qualquer import que use runtime_paths
os.environ.setdefault("RACHEL_RUNTIME_ROOT", str(ROOT))
# Não definimos RACHEL_STATE_ROOT por padrão: tests que esperam layout legacy
# (runtime_paths.CONFIG == ROOT/RACHEL_PLATFORM/CONFIG) precisam do modo
# não-portable. Tests que usam o modo portable devem definir explicitamente
# via fixture ou env no início do test.
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
# CI/sem Ollama: usar mock para não falhar tentando conectar a provider remoto.
# Testes que precisam de provider real devem sobrescrever explicitamente.
os.environ.setdefault("RACHEL_MODEL_PROVIDER", "mock")
os.environ.setdefault("RACHEL_MODEL_NAME", "rachel-mock-v1")
os.environ.setdefault("RACHEL_MODEL_BASE_URL", "http://127.0.0.1:11434/v1")
os.environ.setdefault("RACHEL_MODEL_TIMEOUT_SECONDS", "10")

for path in (str(CORE_SRC), str(RUNTIME_SRC), str(BRIDGE_SRC)):
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_state_dir():
    """Sentinel: tests que precisarem de STATE isolated devem usar a fixture
    `temp_state_dir`. Este hook existe apenas como ponto de extensão futuro.
    """
    yield
