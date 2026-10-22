"""Configuração de testes: DB temporário e ambiente isolado.

Define as variáveis de ambiente ANTES de qualquer import de app.* para que
get_settings() (cacheado) leia o DB temporário.
"""
from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="visiondesk_test_")
os.environ["VISIONDESK_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ["VISIONDESK_PERSIST_FRAMES"] = "false"
# Força VLM "indisponível" nos testes de forma determinística: uma variável de
# ambiente vazia tem precedência sobre o valor do .env real, garantindo que a
# suíte não dependa de uma chave presente no ambiente local.
os.environ["ANTHROPIC_API_KEY"] = ""
# Produção não roda com o atalho de DEV: os testes sobem como produção.
os.environ["VISIONDESK_DEV_LOGIN"] = "false"
os.environ.pop("VISIONDESK_API_KEY", None)
