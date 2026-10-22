"""
oracle.py
---------
Replicacao opcional no Oracle XE (schema em src/sql/schema.sql).

Os parametros sao montados a partir da mesma `Avaliacao` gravada no
SQLite, portanto score, classe, probabilidades e versao do modelo sao
identicos nas duas persistencias.
"""

from __future__ import annotations

import logging

from .avaliacao import Avaliacao
from .entrada import Leitura

logger = logging.getLogger("agropredict.oracle")

SQL_INSERIR_PREDICAO = """
    INSERT INTO predicoes (
        id_predicao, id_equipamento, id_operador,
        umidade_solo, declividade, chuva_24h, temperatura,
        velocidade, idade_maquina, horas_operacao, status_operacao,
        score_risco, classe_risco, recomendacao,
        prob_baixo, prob_medio, prob_alto, versao_modelo
    ) VALUES (
        seq_predicao.NEXTVAL, :equip, :oper,
        :umid, :decl, :chuva, :temp,
        :vel, :idade, :horas, :status,
        :score, :classe, :reco,
        :pb, :pm, :pa, :versao
    )
    RETURNING id_predicao INTO :id_out
"""

SQL_INSERIR_ALERTA = """
    INSERT INTO alertas (id_alerta, id_predicao, nivel, categoria)
    VALUES (seq_alerta.NEXTVAL, :id_pred, :nivel, :categoria)
"""


def configurado(config: dict | None) -> bool:
    return bool(config) and all(config.get(k) for k in ("user", "password", "dsn"))


def parametros_predicao(leitura: Leitura, avaliacao: Avaliacao, id_equipamento: int, id_operador: int) -> dict:
    return {
        "equip": id_equipamento,
        "oper": id_operador,
        "umid": leitura.umidade_solo,
        "decl": leitura.declividade,
        "chuva": leitura.chuva_24h,
        "temp": leitura.temperatura,
        "vel": leitura.velocidade,
        "idade": leitura.idade_maquina,
        "horas": leitura.horas_operacao,
        "status": leitura.status_operacao,
        "score": avaliacao.score_risco,
        "classe": avaliacao.classe_risco,
        "reco": avaliacao.recomendacao,
        "pb": avaliacao.prob("BAIXO"),
        "pm": avaliacao.prob("MEDIO"),
        "pa": avaliacao.prob("ALTO"),
        "versao": avaliacao.versao_modelo,
    }


def inserir(cur, leitura: Leitura, avaliacao: Avaliacao, id_equipamento: int, id_operador: int,
            numero_oracle) -> int:
    """Insere predicao (e alerta, se houver) usando um cursor ja aberto."""
    id_out = cur.var(numero_oracle)
    params = parametros_predicao(leitura, avaliacao, id_equipamento, id_operador)
    cur.execute(SQL_INSERIR_PREDICAO, {**params, "id_out": id_out})
    id_predicao = int(id_out.getvalue()[0])
    if avaliacao.gera_alerta:
        cur.execute(SQL_INSERIR_ALERTA, {
            "id_pred": id_predicao,
            "nivel": avaliacao.classe_risco,
            "categoria": avaliacao.categoria_alerta,
        })
    return id_predicao


def replicar(config: dict, leitura: Leitura, avaliacao: Avaliacao, id_equipamento: int,
             id_operador: int = 1) -> bool:
    """Melhor esforco: retorna False (sem lancar excecao) se o Oracle falhar."""
    if not configurado(config):
        return False

    conn = None
    try:
        import oracledb

        conn = oracledb.connect(**config)
        cur = conn.cursor()
        inserir(cur, leitura, avaliacao, id_equipamento, id_operador, oracledb.NUMBER)
        conn.commit()
        cur.close()
        return True
    except Exception as exc:
        logger.warning("Replicacao Oracle falhou: %s", exc)
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
