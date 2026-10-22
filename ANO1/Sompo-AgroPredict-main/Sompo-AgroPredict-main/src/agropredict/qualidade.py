"""
qualidade.py
------------
Tratamento de inconsistencias antes do consumo pelo modelo.

`limpar_dataset` recebe dados brutos (como chegam da coleta) e aplica,
em ordem, etapas deterministicas e auditaveis:

  1. numeros em texto ("12,5") convertidos; valores nao numericos -> faltante
  2. tipo de operacao padronizado ("  colheita " -> "Colheita"); desconhecido -> faltante
  3. leituras fisicamente impossiveis (ex.: umidade 180%) -> faltante
  4. rotulo padronizado ("Médio" -> "MEDIO"); linhas sem rotulo valido removidas
  5. duplicatas exatas (retransmissao) removidas, mantendo a primeira
  6. duplicatas conflitantes (mesma entrada, rotulos diferentes) removidas
  7. linhas com mais de LIMITE_FALTANTES variaveis faltantes removidas

Os faltantes restantes NAO sao preenchidos aqui: a imputacao (mediana)
fica dentro do pipeline do modelo e e ajustada so no conjunto de treino,
evitando vazamento de informacao do teste.
"""

from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from .entrada import FAIXAS_VALIDAS, FEATURES, FEATURES_NUMERICAS, STATUS_VALIDOS

CLASSES = ("BAIXO", "MEDIO", "ALTO")
LIMITE_FALTANTES = 2


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


_STATUS_POR_CHAVE = {s.lower(): s for s in STATUS_VALIDOS}


def normalizar_status(valor) -> str | float:
    if not isinstance(valor, str):
        return np.nan
    return _STATUS_POR_CHAVE.get(_sem_acento(valor).strip().lower(), np.nan)


def normalizar_classe(valor) -> str | float:
    if not isinstance(valor, str):
        return np.nan
    chave = _sem_acento(valor).strip().upper()
    return chave if chave in CLASSES else np.nan


def converter_numero(valor) -> float:
    """Aceita 12.5, "12.5" e "12,5"; qualquer outra coisa vira NaN."""
    if isinstance(valor, str):
        valor = valor.strip().replace(",", ".")
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return np.nan
    return numero if np.isfinite(numero) else np.nan


@dataclass
class RelatorioQualidade:
    linhas_entrada: int
    linhas_saida: int = 0
    etapas: list[dict] = field(default_factory=list)
    faltantes_restantes: dict[str, int] = field(default_factory=dict)

    def registrar(self, etapa: str, afetados: int, acao: str) -> None:
        self.etapas.append({"etapa": etapa, "afetados": int(afetados), "acao": acao})

    def como_dict(self) -> dict:
        return asdict(self)

    def como_markdown(self) -> str:
        linhas = [
            f"Linhas recebidas: **{self.linhas_entrada}** · linhas aptas para o modelo: **{self.linhas_saida}**",
            "",
            "| Etapa | Registros afetados | Tratamento |",
            "|---|---:|---|",
            *[f"| {e['etapa']} | {e['afetados']} | {e['acao']} |" for e in self.etapas],
        ]
        restantes = sum(self.faltantes_restantes.values())
        linhas += ["", f"Valores faltantes restantes, imputados no pipeline pela mediana do treino: **{restantes}**"]
        return "\n".join(linhas)


def limpar_dataset(bruto: pd.DataFrame, coluna_alvo: str = "risco") -> tuple[pd.DataFrame, RelatorioQualidade]:
    df = bruto.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    faltando = [c for c in FEATURES + [coluna_alvo] if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas obrigatorias ausentes: {faltando}")
    df = df[FEATURES + [coluna_alvo]]
    rel = RelatorioQualidade(linhas_entrada=len(df))

    # 1. Conversao numerica
    texto_decimal, nao_numericos = 0, 0
    for coluna in FEATURES_NUMERICAS:
        original = df[coluna]
        convertido = original.map(converter_numero)
        # Ao ler um CSV, a coluna inteira vira texto se uma celula tiver virgula;
        # so conta como problema o valor que usava virgula decimal.
        com_virgula = original.map(lambda v: isinstance(v, str) and "," in v)
        texto_decimal += int((com_virgula & convertido.notna()).sum())
        nao_numericos += int((original.notna() & convertido.isna()).sum())
        df[coluna] = convertido.astype(float)
    rel.registrar("Número gravado como texto (ex.: \"12,5\")", texto_decimal, "convertido para número")
    rel.registrar("Valor não numérico", nao_numericos, "marcado como faltante")

    # 2. Tipo de operacao
    status_original = df["status_operacao"]
    df["status_operacao"] = status_original.map(normalizar_status)
    reescritos = int((status_original.notna() & df["status_operacao"].notna()
                      & (status_original != df["status_operacao"])).sum())
    invalidos = int((status_original.notna() & df["status_operacao"].isna()).sum())
    rel.registrar("Tipo de operação com grafia inconsistente", reescritos, "padronizado")
    rel.registrar("Tipo de operação desconhecido", invalidos, "marcado como faltante")

    # 3. Faixa fisica
    fora_da_faixa = 0
    for coluna, (minimo, maximo) in FAIXAS_VALIDAS.items():
        mascara = df[coluna].notna() & ~df[coluna].between(minimo, maximo)
        fora_da_faixa += int(mascara.sum())
        df.loc[mascara, coluna] = np.nan
    rel.registrar("Leitura fisicamente impossível (sensor)", fora_da_faixa, "marcada como faltante")

    # 4. Rotulo
    alvo_original = df[coluna_alvo]
    df[coluna_alvo] = alvo_original.map(normalizar_classe)
    rotulos_reescritos = int((alvo_original.notna() & df[coluna_alvo].notna()
                              & (alvo_original != df[coluna_alvo])).sum())
    sem_rotulo = int(df[coluna_alvo].isna().sum())
    rel.registrar("Rótulo com grafia inconsistente", rotulos_reescritos, "padronizado")
    rel.registrar("Sem rótulo válido", sem_rotulo, "linha removida")
    df = df[df[coluna_alvo].notna()]

    # 5. Duplicatas exatas
    duplicadas = df.duplicated(keep="first")
    rel.registrar("Duplicata exata (retransmissão)", int(duplicadas.sum()), "removida, mantida a 1ª ocorrência")
    df = df[~duplicadas]

    # 6. Duplicatas conflitantes
    conflito = df.duplicated(subset=FEATURES, keep=False)
    rel.registrar("Mesma entrada com rótulos diferentes", int(conflito.sum()), "todas as ocorrências removidas")
    df = df[~conflito]

    # 7. Excesso de faltantes
    excesso = df[FEATURES].isna().sum(axis=1) > LIMITE_FALTANTES
    rel.registrar(f"Mais de {LIMITE_FALTANTES} variáveis faltantes", int(excesso.sum()), "linha removida")
    df = df[~excesso].reset_index(drop=True)

    rel.linhas_saida = len(df)
    rel.faltantes_restantes = {c: int(n) for c, n in df[FEATURES].isna().sum().items() if n}
    return df, rel
