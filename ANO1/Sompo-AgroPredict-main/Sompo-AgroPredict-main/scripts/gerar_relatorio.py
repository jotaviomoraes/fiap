"""
gerar_relatorio.py
------------------
Gera o relatorio consolidado de risco da frota em Markdown, a partir do
banco SQLite, usando as mesmas consultas do dashboard
(`agropredict.relatorios`): tendencias por equipamento, regiao e tipo de
operacao, fatores de risco, alertas, aderencia, comportamento do
produtor, manutencao e qualidade da coleta.

O relatorio e salvo em data/ (runtime, nao versionado), ao lado do banco.

Uso (a partir da raiz do repositorio):
    python scripts/gerar_relatorio.py                       # ultimos 14 dias
    python scripts/gerar_relatorio.py --dias 30 --saida relatorio.md
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from agropredict.config import DATA_DIR  # noqa: E402
from agropredict.markdown import tabela_markdown  # noqa: E402
from agropredict.persistencia import RepositorioSQLite  # noqa: E402
from agropredict.regras import ALERTA, CATEGORIA_POR_VARIAVEL, MAXIMO  # noqa: E402
from agropredict.relatorios import Filtros, Relatorios  # noqa: E402

SAIDA_PADRAO = DATA_DIR / "relatorio_frota.md"


def _pct(parte, total) -> str:
    return f"{100 * parte / total:.1f}%" if total else "—"


def gerar(relatorios: Relatorios, filtros: Filtros) -> str:
    r = relatorios
    resumo = r.resumo(filtros)
    total = int(resumo["total"])
    if not total:
        return "# Relatório de risco da frota\n\n_Sem predições no período. Rode `python scripts/simular_frota.py`._\n"

    ranking = r.ranking_equipamentos(filtros).drop(columns=["id_equipamento"])
    cenarios, variaveis = r.fatores_risco(filtros)
    alertas = r.listar_alertas(filtros, limite=100000)
    pendentes_alto = alertas[(alertas["acao_tomada"] == "PENDENTE") & (alertas["nivel"] == "ALTO")]
    q = r.qualidade_dados(filtros)

    def renomear(df: pd.DataFrame, nome: str) -> pd.DataFrame:
        return df.rename(columns={"grupo": nome, "operacoes": "operações", "score_medio": "score médio",
                                  "pct_alto": "% ALTO", "pct_medio": "% MÉDIO"})

    tendencia = r.tendencia_diaria(filtros, "regiao")
    partes = [
        "# Relatório de risco da frota",
        "",
        f"> Gerado por `scripts/gerar_relatorio.py` em {datetime.now():%d/%m/%Y %H:%M} · período "
        f"{filtros.data_inicio:%d/%m/%Y} a {filtros.data_fim:%d/%m/%Y} · fonte: SQLite (`vw_predicoes`). "
        "Dados da frota fictícia de demonstração.",
        "",
        "## 1. Resumo do período (gestor — CA-02.1)",
        "",
        f"- **{total}** operações avaliadas em **{int(resumo['equipamentos'])}** equipamentos",
        f"- Distribuição: 🟢 BAIXO {int(resumo['baixo'])} ({_pct(resumo['baixo'], total)}) · "
        f"🟡 MÉDIO {int(resumo['medio'])} ({_pct(resumo['medio'], total)}) · "
        f"🔴 ALTO {int(resumo['alto'])} ({_pct(resumo['alto'], total)})",
        f"- Score médio **{resumo['score_medio']:.1f}** · score máximo **{resumo['score_maximo']:.1f}**",
        f"- Alertas pendentes de resposta: **{int(resumo['alertas_pendentes'])}** "
        f"(dos quais **{len(pendentes_alto)}** de nível ALTO)",
        "",
        "## 2. Ranking de equipamentos por risco (CA-02.2)",
        "",
        tabela_markdown(ranking.rename(columns={
            "equipamento": "equipamento", "tipo_equipamento": "tipo", "operacoes": "operações",
            "score_medio": "score médio", "score_maximo": "score máx.", "qtd_alto": "ALTO",
            "alertas_pendentes": "pendentes"})),
        "",
        "## 3. Tendências de risco",
        "",
        "### Por região",
        "",
        tabela_markdown(renomear(r.resumo_por_dimensao(filtros, "regiao"), "região")),
        "",
        "Score médio diário por região:",
        "",
        tabela_markdown(tendencia.reset_index().rename(columns={"dia": "dia"})) if not tendencia.empty else "_Sem dados._",
        "",
        "### Por tipo de operação",
        "",
        tabela_markdown(renomear(r.resumo_por_dimensao(filtros, "status_operacao"), "tipo de operação")),
        "",
        "### Por tipo de equipamento",
        "",
        tabela_markdown(renomear(r.resumo_por_dimensao(filtros, "tipo_equipamento"), "tipo de equipamento")),
        "",
        "### Por hora do dia (padrões temporais — CA-02.3)",
        "",
        tabela_markdown(r.score_por_hora(filtros).rename(columns={"score_medio": "score médio",
                                                                   "operacoes": "operações"})),
        "",
        "## 4. Fatores de risco predominantes (CA-02.4)",
        "",
        tabela_markdown(cenarios),
        "",
        "Variáveis acima do limiar de alerta nas predições MÉDIO/ALTO:",
        "",
        tabela_markdown(variaveis),
        "",
        "## 5. Alertas e critérios",
        "",
        "Critério: classe final MÉDIO → alerta MÉDIO; classe final ALTO → alerta ALTO. Qualquer variável no "
        "limite máximo força ALTO (override).",
        "",
        tabela_markdown(pd.DataFrame([
            {"variável": v, "alerta (>)": ALERTA[v], "máximo / override (≥)": MAXIMO.get(v, "—"),
             "categoria": CATEGORIA_POR_VARIAVEL[v]} for v in ALERTA])),
        "",
        tabela_markdown(alertas.groupby(["nivel", "categoria", "acao_tomada"]).size()
                        .reset_index(name="alertas").rename(columns={"nivel": "nível", "acao_tomada": "situação"})),
        "",
        "## 6. Analista Sompo (US-03)",
        "",
        "### Aderência dos operadores aos alertas (CA-03.1)",
        "",
        tabela_markdown(r.aderencia_operadores(filtros)),
        "",
        "### Comportamento preventivo por produtor (CA-03.2)",
        "",
        "Score = 50% aderência + 30% operações em BAIXO + 20% tendência (50 = estável).",
        "",
        tabela_markdown(r.comportamento_produtor(filtros)),
        "",
        "## 7. Manutenção preventiva (técnico)",
        "",
        tabela_markdown(r.manutencao(filtros).drop(columns=["id_equipamento"], errors="ignore")),
        "",
        "## 8. Qualidade e rastreabilidade da coleta",
        "",
        tabela_markdown(q["status"]),
        "",
        f"Integridade: {q['integridade']['com_hash']} de {q['integridade']['total']} leituras com hash SHA-256; "
        f"{q['integridade']['processadas_sem_predicao']} processada(s) sem predição. "
        f"Entradas recusadas: {q['rejeicoes_por_tipo'] or 'nenhuma'}.",
        "",
        tabela_markdown(q["fontes"]),
    ]
    return "\n".join(partes) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Relatório consolidado de risco da frota")
    parser.add_argument("--dias", type=int, default=14)
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    args = parser.parse_args()

    hoje = date.today()
    filtros = Filtros(data_inicio=hoje - timedelta(days=args.dias - 1), data_fim=hoje)
    texto = gerar(Relatorios(RepositorioSQLite()), filtros)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(texto, encoding="utf-8")
    print(f"[OK] Relatório salvo em {args.saida}")


if __name__ == "__main__":
    main()
