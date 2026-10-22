"""
gerar_dataset_v3.py
-------------------
Geracao do dataset simulado v3 do Sompo AgroPredict (Sprint 4).

Diferencas em relacao a v2 (Sprint 2):
- Volume: 3000 linhas (antes 1000), com a mesma logica de cenarios e de
  rotulagem de `gerar_dataset_v2.py` (reaproveitada, nao duplicada).
- Saida BRUTA: simula os problemas reais de coleta que o pipeline de
  qualidade (`src/agropredict/qualidade.py`) precisa tratar antes do treino:
    * valores faltantes (falha de sensor / conexao)
    * numeros gravados como texto com virgula decimal ("12,5")
    * leituras fisicamente impossiveis (picos de sensor)
    * grafias inconsistentes no tipo de operacao e no rotulo
    * duplicatas exatas (retransmissao) e conflitantes
    * linhas sem rotulo

Uso: python gerar_dataset_v3.py
Saida: dataset_v3_bruto.csv (mesma pasta)
"""

from pathlib import Path

import numpy as np
import pandas as pd

import gerar_dataset_v2 as v2

N_LINHAS = 3000
SEED_PROBLEMAS = 7
PASTA = Path(__file__).resolve().parent
FEATURES_NUM = ["umidade_solo", "declividade", "chuva_24h", "temperatura",
                "velocidade", "idade_maquina", "horas_operacao"]


def gerar_limpo(n: int) -> pd.DataFrame:
    df = v2.gerar_features(n)
    df["score_risco"] = df.apply(v2.calcular_score, axis=1)
    df["risco"] = df["score_risco"].apply(v2.classificar)
    for col in FEATURES_NUM:
        df[col] = df[col].round(2)
    return df[FEATURES_NUM + ["status_operacao", "risco"]]


def injetar_problemas(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    bruto = df.astype(object).copy()
    n = len(bruto)

    def amostra(frac: float) -> np.ndarray:
        return rng.choice(n, size=int(n * frac), replace=False)

    # Faltantes: ~2% das celulas numericas
    for idx in amostra(0.10):
        bruto.at[idx, rng.choice(FEATURES_NUM)] = np.nan
    # Algumas linhas muito incompletas (falha prolongada de conexao)
    for idx in amostra(0.005):
        for col in rng.choice(FEATURES_NUM, size=4, replace=False):
            bruto.at[idx, col] = np.nan
    # Numero como texto com virgula decimal
    for idx in amostra(0.02):
        col = rng.choice(FEATURES_NUM)
        if pd.notna(bruto.at[idx, col]):
            bruto.at[idx, col] = f"{float(bruto.at[idx, col]):.2f}".replace(".", ",")
    # Texto nao numerico
    for idx in amostra(0.003):
        bruto.at[idx, rng.choice(FEATURES_NUM)] = rng.choice(["erro", "N/A", "--"])
    # Picos de sensor fisicamente impossiveis
    picos = {"umidade_solo": 180.0, "temperatura": -45.0, "velocidade": 320.0, "horas_operacao": 30.0}
    for idx in amostra(0.01):
        col = rng.choice(list(picos))
        bruto.at[idx, col] = picos[col]
    # Tipo de operacao com grafia inconsistente ou invalida
    variantes = {"Colheita": ["colheita", " Colheita ", "COLHEITA"],
                 "Deslocamento": ["deslocamento", "DESLOCAMENTO "],
                 "Manobra": ["manobra", " MANOBRA"]}
    for idx in amostra(0.05):
        bruto.at[idx, "status_operacao"] = rng.choice(variantes[bruto.at[idx, "status_operacao"]])
    for idx in amostra(0.003):
        bruto.at[idx, "status_operacao"] = rng.choice(["Plantio", "???"])
    # Rotulo com grafia inconsistente ou ausente
    grafias = {"BAIXO": "Baixo", "MEDIO": "Médio", "ALTO": "alto"}
    for idx in amostra(0.02):
        bruto.at[idx, "risco"] = grafias[bruto.at[idx, "risco"]]
    for idx in amostra(0.005):
        bruto.at[idx, "risco"] = np.nan

    # Duplicatas exatas (retransmissao) e conflitantes (mesma entrada, rotulo diferente)
    exatas = bruto.iloc[amostra(0.02)]
    conflitantes = bruto.iloc[amostra(0.004)].copy()
    troca = {"BAIXO": "MEDIO", "MEDIO": "ALTO", "ALTO": "MEDIO"}
    conflitantes["risco"] = conflitantes["risco"].map(lambda r: troca.get(r, "MEDIO"))
    bruto = pd.concat([bruto, exatas, conflitantes], ignore_index=True)

    # Embaralha para que duplicatas nao fiquem agrupadas no fim do arquivo
    return bruto.sample(frac=1.0, random_state=SEED_PROBLEMAS).reset_index(drop=True)


def main():
    print(f"Gerando {N_LINHAS} linhas (logica de rotulagem da v2)...")
    limpo = gerar_limpo(N_LINHAS)
    bruto = injetar_problemas(limpo, np.random.default_rng(SEED_PROBLEMAS))
    destino = PASTA / "dataset_v3_bruto.csv"
    bruto.to_csv(destino, index=False, encoding="utf-8")

    print("\n=== Distribuicao de classes (antes dos problemas) ===")
    print(limpo["risco"].value_counts())
    print(f"\nArquivo salvo: {destino.name} ({len(bruto)} linhas brutas)")
    print("Trate com: python src/modelo/treinar_modelo.py")


if __name__ == "__main__":
    main()
