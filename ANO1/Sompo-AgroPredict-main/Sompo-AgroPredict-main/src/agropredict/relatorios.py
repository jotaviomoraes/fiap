"""
relatorios.py
-------------
Consultas analiticas sobre o SQLite (view `vw_predicoes`), usadas pelas
paginas do dashboard e reutilizaveis fora dele.

Mapeamento com as User Stories:
  resumo, ranking_equipamentos, historico_equipamento,
  score_por_hora, tendencia_diaria, fatores_risco   -> US-02 (gestor)
  listar_alertas                                    -> US-01/US-02
  aderencia_operadores, forense, auditoria_predicao,
  comportamento_produtor                            -> US-03 (analista)
  manutencao                                        -> tecnico de manutencao
  qualidade_dados, rejeicoes                        -> rastreabilidade da coleta
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import pandas as pd

from .persistencia import RepositorioSQLite

# Dimensoes permitidas para agrupamento (whitelist evita SQL dinamico inseguro)
DIMENSOES = {
    "regiao": "regiao",
    "status_operacao": "status_operacao",
    "equipamento": "equipamento",
    "tipo_equipamento": "tipo_equipamento",
    "fazenda": "fazenda",
}

# Criterio de prioridade de manutencao (explicito para o tecnico):
#   ALTA  -> 3+ alertas mecanicos no periodo, ou 1+ alerta mecanico ALTO
#   MEDIA -> 1-2 alertas mecanicos no periodo
#   BAIXA -> nenhum alerta mecanico
LIMIAR_MANUTENCAO_ALTA = 3

# Score de comportamento preventivo do produtor (CA-03.2), de 0 a 100:
#   50% aderencia aos alertas respondidos
#   30% proporcao de operacoes em risco BAIXO
#   20% tendencia: compara o score medio da 1a e da 2a metade do periodo;
#       cada ponto de queda do score vale +5 (50 = estavel, limitado a 0-100)
PESOS_COMPORTAMENTO = {"aderencia": 0.5, "baixo": 0.3, "tendencia": 0.2}
MINIMO_PREDICOES_COMPORTAMENTO = 30
FAIXAS_COMPORTAMENTO = ((80, "Excelente"), (60, "Bom"), (40, "Atenção"), (0, "Crítico"))


@dataclass
class Filtros:
    data_inicio: date | None = None
    data_fim: date | None = None
    regioes: list[str] = field(default_factory=list)
    equipamentos: list[int] = field(default_factory=list)
    status_operacao: list[str] = field(default_factory=list)
    usuario: str | None = None  # restringe ao proprio operador

    def where(self, alias: str = "") -> tuple[str, list]:
        p = f"{alias}." if alias else ""
        clausulas, params = [], []
        if self.data_inicio:
            clausulas.append(f"{p}data_hora >= ?")
            params.append(f"{self.data_inicio.isoformat()} 00:00:00")
        if self.data_fim:
            clausulas.append(f"{p}data_hora < ?")
            params.append(f"{(self.data_fim + timedelta(days=1)).isoformat()} 00:00:00")
        for coluna, valores in (
            ("regiao", self.regioes),
            ("id_equipamento", self.equipamentos),
            ("status_operacao", self.status_operacao),
        ):
            if valores:
                clausulas.append(f"{p}{coluna} IN ({','.join('?' * len(valores))})")
                params.extend(valores)
        if self.usuario:
            clausulas.append(f"{p}usuario = ?")
            params.append(self.usuario)
        return (" WHERE " + " AND ".join(clausulas)) if clausulas else "", params


class Relatorios:
    def __init__(self, repo: RepositorioSQLite):
        self.repo = repo

    # ------------------------------------------------------------------
    # US-02 — gestor de frota
    # ------------------------------------------------------------------
    def resumo(self, f: Filtros) -> dict:
        where, params = f.where()
        df = self.repo.consultar(
            f"""SELECT COUNT(*) AS total,
                       SUM(classe_risco = 'BAIXO') AS baixo,
                       SUM(classe_risco = 'MEDIO') AS medio,
                       SUM(classe_risco = 'ALTO')  AS alto,
                       ROUND(AVG(score_risco), 1)  AS score_medio,
                       ROUND(MAX(score_risco), 1)  AS score_maximo,
                       COALESCE(SUM(acao_tomada = 'PENDENTE'), 0) AS alertas_pendentes,
                       COUNT(DISTINCT id_equipamento) AS equipamentos
                FROM vw_predicoes {where}""",
            params,
        )
        linha = df.iloc[0].to_dict()
        return {k: (0 if pd.isna(v) else v) for k, v in linha.items()}

    def ranking_equipamentos(self, f: Filtros) -> pd.DataFrame:
        where, params = f.where()
        return self.repo.consultar(
            f"""SELECT id_equipamento, equipamento, tipo_equipamento, modelo, fabricante, regiao,
                       COUNT(*)                     AS operacoes,
                       ROUND(AVG(score_risco), 1)   AS score_medio,
                       ROUND(MAX(score_risco), 1)   AS score_maximo,
                       SUM(classe_risco = 'ALTO')   AS qtd_alto,
                       COALESCE(SUM(acao_tomada = 'PENDENTE'), 0) AS alertas_pendentes
                FROM vw_predicoes {where}
                GROUP BY id_equipamento
                ORDER BY score_medio DESC, qtd_alto DESC""",
            params,
        )

    def historico_equipamento(self, id_equipamento: int, f: Filtros, limite: int = 500) -> pd.DataFrame:
        where, params = Filtros(
            f.data_inicio, f.data_fim, f.regioes, [id_equipamento], f.status_operacao, f.usuario
        ).where()
        return self.repo.consultar(
            f"""SELECT id_predicao, data_hora, usuario, status_operacao,
                       umidade_solo, declividade, chuva_24h, temperatura, velocidade,
                       horas_operacao, classe_risco, score_risco, recomendacao, acao_tomada
                FROM vw_predicoes {where}
                ORDER BY data_hora DESC LIMIT ?""",
            [*params, limite],
        )

    def score_por_hora(self, f: Filtros) -> pd.DataFrame:
        """Score medio por hora do dia: revela padroes temporais (CA-02.3)."""
        where, params = f.where()
        return self.repo.consultar(
            f"""SELECT CAST(strftime('%H', data_hora) AS INTEGER) AS hora,
                       ROUND(AVG(score_risco), 1) AS score_medio,
                       COUNT(*) AS operacoes
                FROM vw_predicoes {where}
                GROUP BY hora ORDER BY hora""",
            params,
        )

    def tendencia_diaria(self, f: Filtros, dimensao: str) -> pd.DataFrame:
        """Score medio por dia, uma coluna por valor da dimensao escolhida."""
        coluna = DIMENSOES[dimensao]
        where, params = f.where()
        df = self.repo.consultar(
            f"""SELECT date(data_hora) AS dia, {coluna} AS grupo, ROUND(AVG(score_risco), 1) AS score_medio
                FROM vw_predicoes {where}
                GROUP BY dia, grupo ORDER BY dia""",
            params,
        )
        if df.empty:
            return df
        return df.pivot(index="dia", columns="grupo", values="score_medio")

    def resumo_por_dimensao(self, f: Filtros, dimensao: str) -> pd.DataFrame:
        coluna = DIMENSOES[dimensao]
        where, params = f.where()
        return self.repo.consultar(
            f"""SELECT {coluna} AS grupo,
                       COUNT(*) AS operacoes,
                       ROUND(AVG(score_risco), 1) AS score_medio,
                       ROUND(100.0 * SUM(classe_risco = 'ALTO') / COUNT(*), 1) AS pct_alto,
                       ROUND(100.0 * SUM(classe_risco = 'MEDIO') / COUNT(*), 1) AS pct_medio
                FROM vw_predicoes {where}
                GROUP BY grupo ORDER BY score_medio DESC""",
            params,
        )

    def fatores_risco(self, f: Filtros) -> tuple[pd.DataFrame, pd.DataFrame]:
        """(cenarios por recomendacao, frequencia de cada variavel em alerta) em MEDIO/ALTO."""
        where, params = f.where()
        filtro_risco = ("AND" if where else "WHERE") + " classe_risco IN ('MEDIO', 'ALTO')"
        cenarios = self.repo.consultar(
            f"""SELECT recomendacao AS cenario,
                       SUM(classe_risco = 'MEDIO') AS medio,
                       SUM(classe_risco = 'ALTO')  AS alto,
                       COUNT(*) AS total
                FROM vw_predicoes {where} {filtro_risco}
                GROUP BY recomendacao ORDER BY total DESC""",
            params,
        )
        brutos = self.repo.consultar(
            f"SELECT variaveis_alerta FROM vw_predicoes {where} {filtro_risco}", params
        )
        variaveis = (
            brutos["variaveis_alerta"].dropna().str.split(",").explode()
            .value_counts().rename_axis("variavel").reset_index(name="ocorrencias")
        )
        return cenarios, variaveis

    # ------------------------------------------------------------------
    # Alertas
    # ------------------------------------------------------------------
    def listar_alertas(self, f: Filtros, acoes: list[str] | None = None, niveis: list[str] | None = None,
                       categorias: list[str] | None = None, limite: int = 500) -> pd.DataFrame:
        where, params = f.where("v")
        extras = []
        for coluna, valores in (("a.acao_tomada", acoes), ("a.nivel", niveis), ("a.categoria", categorias)):
            if valores:
                extras.append(f"{coluna} IN ({','.join('?' * len(valores))})")
                params.extend(valores)
        if extras:
            where = (where + " AND " if where else " WHERE ") + " AND ".join(extras)
        return self.repo.consultar(
            f"""SELECT a.id_alerta, a.data_emissao, a.nivel, a.categoria, v.equipamento, v.regiao,
                       v.usuario AS operador, v.status_operacao, v.score_risco, a.mensagem,
                       v.motivo_override, a.acao_tomada, a.data_acao, a.usuario_acao, a.observacao,
                       v.id_predicao
                FROM alertas a
                JOIN vw_predicoes v ON v.id_predicao = a.id_predicao
                {where}
                ORDER BY a.data_emissao DESC LIMIT ?""",
            [*params, limite],
        )

    # ------------------------------------------------------------------
    # US-03 — analista Sompo
    # ------------------------------------------------------------------
    def aderencia_operadores(self, f: Filtros) -> pd.DataFrame:
        """Taxa de aderencia = respeitados / respondidos (pendentes ficam de fora)."""
        where, params = f.where("v")
        return self.repo.consultar(
            f"""SELECT v.usuario AS operador,
                       COUNT(*) AS alertas,
                       SUM(a.acao_tomada = 'RESPEITOU') AS respeitados,
                       SUM(a.acao_tomada = 'IGNOROU')   AS ignorados,
                       SUM(a.acao_tomada = 'PENDENTE')  AS pendentes,
                       ROUND(100.0 * SUM(a.acao_tomada = 'RESPEITOU')
                             / NULLIF(SUM(a.acao_tomada != 'PENDENTE'), 0), 1) AS aderencia_pct
                FROM alertas a
                JOIN vw_predicoes v ON v.id_predicao = a.id_predicao
                {where}
                GROUP BY v.usuario
                ORDER BY aderencia_pct ASC""",
            params,
        )

    def forense(self, id_equipamento: int, momento: datetime, janela_horas: float = 2.0) -> pd.DataFrame:
        """Todas as predicoes do equipamento na janela anterior ao sinistro (CA-03.3)."""
        inicio = (momento - timedelta(hours=janela_horas)).isoformat(sep=" ", timespec="seconds")
        fim = momento.isoformat(sep=" ", timespec="seconds")
        return self.repo.consultar(
            """SELECT id_predicao, data_hora, usuario, status_operacao,
                      umidade_solo, declividade, chuva_24h, temperatura, velocidade, horas_operacao,
                      classe_risco, score_risco, recomendacao, nivel_alerta, acao_tomada
               FROM vw_predicoes
               WHERE id_equipamento = ? AND data_hora BETWEEN ? AND ?
               ORDER BY data_hora""",
            [id_equipamento, inicio, fim],
        )

    def auditoria_predicao(self, id_predicao: int) -> dict | None:
        """Entradas, fontes, probabilidades, decisao e versao do modelo (CA-03.4)."""
        df = self.repo.consultar("SELECT * FROM vw_predicoes WHERE id_predicao = ?", [id_predicao])
        if df.empty:
            return None
        registro = df.iloc[0].to_dict()
        alerta = self.repo.consultar(
            "SELECT data_emissao, nivel, categoria, acao_tomada, data_acao, usuario_acao, observacao "
            "FROM alertas WHERE id_predicao = ?",
            [id_predicao],
        )
        registro["alerta"] = alerta.iloc[0].to_dict() if not alerta.empty else None
        registro["explicacao"] = json.loads(registro["explicacao"]) if registro.get("explicacao") else []
        return registro

    def comportamento_produtor(self, f: Filtros) -> pd.DataFrame:
        """Score de comportamento preventivo por fazenda (produtor segurado), CA-03.2."""
        where, params = f.where()
        df = self.repo.consultar(
            f"SELECT fazenda, regiao, data_hora, classe_risco, score_risco, acao_tomada FROM vw_predicoes {where}",
            params,
        )
        colunas = ["fazenda", "regiao", "predicoes", "aderencia_pct", "pct_baixo", "tendencia_pts",
                   "score_comportamento", "faixa"]
        if df.empty:
            return pd.DataFrame(columns=colunas)

        linhas = []
        for (fazenda, regiao), grupo in df.sort_values("data_hora").groupby(["fazenda", "regiao"]):
            respondidos = grupo["acao_tomada"].isin(["RESPEITOU", "IGNOROU"])
            aderencia = (100.0 * (grupo["acao_tomada"] == "RESPEITOU").sum() / respondidos.sum()
                         if respondidos.any() else 100.0)
            pct_baixo = 100.0 * (grupo["classe_risco"] == "BAIXO").mean()
            metade = len(grupo) // 2
            queda = grupo["score_risco"].iloc[:metade].mean() - grupo["score_risco"].iloc[metade:].mean()                 if metade else 0.0
            tendencia = min(100.0, max(0.0, 50.0 + 5.0 * queda))
            suficiente = len(grupo) >= MINIMO_PREDICOES_COMPORTAMENTO
            score = (PESOS_COMPORTAMENTO["aderencia"] * aderencia + PESOS_COMPORTAMENTO["baixo"] * pct_baixo
                     + PESOS_COMPORTAMENTO["tendencia"] * tendencia)
            faixa = next(nome for limite, nome in FAIXAS_COMPORTAMENTO if score >= limite)                 if suficiente else "Dados insuficientes"
            linhas.append([fazenda, regiao, len(grupo), round(aderencia, 1), round(pct_baixo, 1),
                           round(tendencia, 1), round(score, 1) if suficiente else None, faixa])
        return pd.DataFrame(linhas, columns=colunas).sort_values(
            "score_comportamento", ascending=False, na_position="last").reset_index(drop=True)

    # ------------------------------------------------------------------
    # Tecnico de manutencao
    # ------------------------------------------------------------------
    def manutencao(self, f: Filtros) -> pd.DataFrame:
        where, params = f.where("v")
        df = self.repo.consultar(
            f"""SELECT v.id_equipamento, v.equipamento, v.tipo_equipamento, v.modelo, v.regiao,
                       MAX(v.idade_maquina)                      AS idade_anos,
                       ROUND(AVG(v.horas_operacao), 1)           AS horas_medias,
                       COUNT(*)                                  AS operacoes,
                       COALESCE(SUM(v.categoria_alerta = 'mecanico'), 0)      AS alertas_mecanicos,
                       COALESCE(SUM(v.categoria_alerta = 'mecanico' AND v.nivel_alerta = 'ALTO'), 0) AS mecanicos_alto,
                       MAX(CASE WHEN v.categoria_alerta = 'mecanico' THEN v.data_hora END) AS ultimo_alerta_mecanico
                FROM vw_predicoes v {where}
                GROUP BY v.id_equipamento""",
            params,
        )
        if df.empty:
            return df

        def prioridade(linha) -> str:
            if linha["alertas_mecanicos"] >= LIMIAR_MANUTENCAO_ALTA or linha["mecanicos_alto"] >= 1:
                return "ALTA"
            if linha["alertas_mecanicos"] >= 1:
                return "MEDIA"
            return "BAIXA"

        df["prioridade"] = df.apply(prioridade, axis=1)
        ordem = {"ALTA": 0, "MEDIA": 1, "BAIXA": 2}
        return df.sort_values(
            ["prioridade", "alertas_mecanicos"], key=lambda s: s.map(ordem) if s.name == "prioridade" else -s
        ).reset_index(drop=True)

    # ------------------------------------------------------------------
    # Qualidade e rastreabilidade da coleta
    # ------------------------------------------------------------------
    def qualidade_dados(self, f: Filtros) -> dict:
        """Indicadores de confiabilidade da coleta no periodo."""
        where_l, params_l = f.where("l")
        where_l = where_l.replace("l.regiao", "e.regiao")
        base = f"""FROM leituras l JOIN equipamentos e ON e.id_equipamento = l.id_equipamento {where_l}"""
        status = self.repo.consultar(
            f"SELECT l.status_processamento AS status, COUNT(*) AS leituras {base} GROUP BY 1", params_l)
        fontes = self.repo.consultar(
            f"""SELECT fonte, SUM(manual) AS manuais, COUNT(*) AS total FROM (
                    SELECT 'umidade' AS fonte, l.fonte_umidade = 'manual' AS manual {base}
                    UNION ALL SELECT 'clima', l.fonte_clima = 'manual' {base}
                    UNION ALL SELECT 'velocidade', l.fonte_velocidade = 'manual' {base}
                    UNION ALL SELECT 'horas', l.fonte_horas = 'manual' {base}
                    UNION ALL SELECT 'idade', l.fonte_idade = 'manual' {base}
                ) GROUP BY fonte""",
            params_l * 5,
        )
        fontes["pct_manual"] = (100.0 * fontes["manuais"].fillna(0) / fontes["total"]).round(1)
        integridade = self.repo.consultar(
            f"""SELECT COUNT(*) AS total,
                       SUM(l.hash_entrada IS NOT NULL) AS com_hash,
                       SUM(l.status_processamento = 'PROCESSADA'
                           AND NOT EXISTS (SELECT 1 FROM predicoes p WHERE p.id_leitura = l.id_leitura))
                           AS processadas_sem_predicao
                {base}""",
            params_l,
        ).iloc[0].fillna(0).astype(int).to_dict()
        rejeicoes = self.rejeicoes(f, limite=None)
        return {
            "status": status,
            "fontes": fontes,
            "integridade": integridade,
            "rejeicoes_por_tipo": rejeicoes.groupby("tipo").size().to_dict() if not rejeicoes.empty else {},
        }

    def rejeicoes(self, f: Filtros, limite: int | None = 200) -> pd.DataFrame:
        clausulas, params = [], []
        if f.data_inicio:
            clausulas.append("data_hora >= ?")
            params.append(f"{f.data_inicio.isoformat()} 00:00:00")
        if f.data_fim:
            clausulas.append("data_hora < ?")
            params.append(f"{(f.data_fim + timedelta(days=1)).isoformat()} 00:00:00")
        if f.usuario:
            clausulas.append("usuario = ?")
            params.append(f.usuario)
        where = (" WHERE " + " AND ".join(clausulas)) if clausulas else ""
        sufixo = " LIMIT ?" if limite else ""
        return self.repo.consultar(
            f"""SELECT id_rejeicao, data_hora, origem, usuario, id_equipamento, tipo, motivo, dados
                FROM rejeicoes {where} ORDER BY id_rejeicao DESC{sufixo}""",
            params + ([limite] if limite else []),
        )

    def log_acessos(self, limite: int = 200) -> pd.DataFrame:
        return self.repo.consultar(
            "SELECT data_hora, usuario, perfil, evento, sucesso FROM log_acessos ORDER BY id DESC LIMIT ?",
            [limite],
        )
