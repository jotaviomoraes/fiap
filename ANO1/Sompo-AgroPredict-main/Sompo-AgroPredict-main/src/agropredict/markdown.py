"""Formatacao de tabelas Markdown para os relatorios e evidencias gerados pelos scripts."""

from __future__ import annotations

import pandas as pd


def tabela_markdown(df: pd.DataFrame, max_linhas: int | None = None) -> str:
    if df is None or df.empty:
        return "_Sem dados._"
    dados = df.head(max_linhas) if max_linhas else df

    def celula(valor) -> str:
        if isinstance(valor, float):
            return "—" if pd.isna(valor) else f"{valor:,.2f}".rstrip("0").rstrip(".").replace(",", " ")
        if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
            return "—"
        return str(valor).replace("|", "\\|").replace("\n", " ")

    cabecalho = "| " + " | ".join(str(c) for c in dados.columns) + " |"
    separador = "|" + "|".join("---:" if pd.api.types.is_numeric_dtype(dados[c]) else "---" for c in dados.columns) + "|"
    linhas = ["| " + " | ".join(celula(v) for v in linha) + " |" for linha in dados.itertuples(index=False)]
    rodape = [f"", f"_… {len(df) - len(dados)} linha(s) omitida(s)._"] if len(dados) < len(df) else []
    return "\n".join([cabecalho, separador, *linhas, *rodape])
