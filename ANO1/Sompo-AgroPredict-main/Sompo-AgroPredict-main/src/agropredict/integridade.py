"""
integridade.py
--------------
Hash SHA-256 de cada leitura, calculado na gravacao e conferido antes de
o modelo usar a leitura. Qualquer alteracao posterior na linha do banco
(valor, equipamento, horario ou operador) faz o hash nao conferir e a
leitura e marcada como ERRO em vez de gerar uma predicao.

O mesmo hash identifica retransmissoes: uma leitura identica (mesmo
equipamento, horario, operador e valores) e rejeitada como duplicata.
"""

from __future__ import annotations

import hashlib

from .entrada import FEATURES_NUMERICAS, Leitura


def hash_leitura(leitura: Leitura, id_equipamento: int, data_hora: str, usuario: str) -> str:
    partes = [str(int(id_equipamento)), data_hora, usuario]
    partes += [f"{campo}={float(getattr(leitura, campo))!r}" for campo in FEATURES_NUMERICAS]
    partes.append(f"status_operacao={leitura.status_operacao}")
    return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()
