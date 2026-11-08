import pandas as pd
from .monitoramento import verificar_sensores
from pathlib import Path

CAMINHO_DATASET = Path(__file__).resolve().parents[1] / "dashboard" / "dataset_agricola.csv"

df = pd.read_csv(CAMINHO_DATASET)

print("=== FARMTECH SOLUTIONS ===")
print("Monitoramento com dados do dataset\n")

print(f"Total de registros: {len(df)}")

# Selecionar um registro com condição de alerta
registros_criticos = df[
    (df["umidade"] < 40) |
    (df["ph"] < 5.5) |
    (df["ph"] > 7.0)
]

if registros_criticos.empty:
    print("Nenhum registro com condição de alerta encontrado.")
else:
    sensores = registros_criticos.iloc[0].to_dict()

    print(f"Cultura: {sensores['cultura']}")
    print(f"Umidade: {sensores['umidade']}%")
    print(f"pH: {sensores['ph']}")

    alertas = verificar_sensores(
        dados=sensores,
        origem="dataset",
        enviar=False
    )

    print(f"\nQuantidade de alertas: {len(alertas)}")

    for alerta in alertas:
        print(f"\nTipo: {alerta['tipo']}")
        print(f"Valor: {alerta['valor']}")
        print(f"Ação: {alerta['acao']}")
        print(f"Publicado no SNS: {alerta['publicado']}")


# Teste adicional: umidade baixa
print("\n=== TESTE DE UMIDADE BAIXA ===")

dados_umidade = df[df["umidade"] < 40]

if not dados_umidade.empty:
    sensores = dados_umidade.iloc[0].to_dict()

    print(f"Umidade: {sensores['umidade']}%")

    alertas = verificar_sensores(
        dados=sensores,
        origem="dataset",
        enviar=False
    )

    print(f"Quantidade de alertas: {len(alertas)}")
else:
    print("Nenhum registro com umidade abaixo de 40%.")


# Teste adicional: condições normais
print("\n=== TESTE DE CONDIÇÕES NORMAIS ===")

dados_normais = df[
    (df["umidade"] >= 40) &
    (df["ph"] >= 5.5) &
    (df["ph"] <= 7.0)
]

if not dados_normais.empty:
    sensores = dados_normais.iloc[0].to_dict()

    print(f"Umidade: {sensores['umidade']}%")
    print(f"pH: {sensores['ph']}")

    alertas = verificar_sensores(
        dados=sensores,
        origem="dataset",
        enviar=False
    )

    print(f"Quantidade de alertas: {len(alertas)}")
else:
    print("Nenhum registro dentro dos limites encontrados.")
