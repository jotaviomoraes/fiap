"""
criar_schema_oracle.py
----------------------
Cria (de forma nao destrutiva) as tabelas, indices e a view `vw_predicoes`
no Oracle Autonomous Database configurado em `config/.env`.

Pode ser executado quantas vezes for preciso: objetos existentes sao
mantidos e os equipamentos da demonstracao sao inseridos apenas se
ainda nao existirem. Nenhum dado e apagado.

Uso, a partir da raiz do repositorio:
    python scripts/criar_schema_oracle.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agropredict.config import config_oracle  # noqa: E402
from agropredict.repositorio_oracle import RepositorioOracle, configurado  # noqa: E402


def main() -> None:
    config = config_oracle()
    if not configurado(config):
        sys.exit("[ERRO] Defina ORACLE_USER, ORACLE_PASSWORD e ORACLE_DSN em config/.env.")
    print(f"[INFO] Conectando em {config['dsn']} como {config['user']} (modo Thin)...")
    repo = RepositorioOracle(config, criar_schema=True)
    print("[OK] Schema verificado/criado sem remover dados existentes.")
    print(f"[OK] Equipamentos cadastrados: {repo.contar('equipamentos')}")
    print(f"[OK] Leituras: {repo.contar('leituras')} · predições: {repo.contar('predicoes')} "
          f"· alertas: {repo.contar('alertas')}")


if __name__ == "__main__":
    main()
