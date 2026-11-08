"""Gera alertas a partir das leituras dos sensores (Fases 2 e 3).

Uso (a partir da raiz do projeto):
    python -m src.aws.alertas_sensores            # apenas simula
    python -m src.aws.alertas_sensores --enviar   # publica no Amazon SNS

Lê as leituras do ESP32 em sensores_agricolas.csv e cria um alerta por tipo de
condição, com a ação corretiva definida pelo grupo em monitoramento.py.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from .alertas_aws import enviar_alerta
from .monitoramento import identificar_alertas

ARQUIVO_SENSORES = (
    Path(__file__).resolve().parents[1]
    / "fase3_banco_oracle"
    / "sensores_agricolas.csv"
)
MAX_VALORES_NO_ALERTA = 5


def agrupar_por_alerta(leituras):
    """Reúne as leituras de cada condição em um único alerta."""
    grupos = {}
    for leitura in leituras:
        for alerta in identificar_alertas(leitura):
            grupo = grupos.setdefault(
                alerta["tipo"], {"acao": alerta["acao"], "valores": []}
            )
            grupo["valores"].append(alerta["valor"])
    return grupos


def verificar_leituras(leituras, enviar=False):
    """Avalia as leituras e, opcionalmente, publica os alertas no Amazon SNS.

    enviar=False: apenas simula os alertas.
    enviar=True: publica os alertas no SNS.
    """
    resultados = []
    grupos = agrupar_por_alerta(leituras)
    for tipo, grupo in grupos.items():
        valores = grupo["valores"]
        valor = (
            f"{len(valores)} de {len(leituras)} leituras, "
            f"valores: {', '.join(valores[:MAX_VALORES_NO_ALERTA])}"
        )
        print(f"Alerta identificado: {tipo}")

        publicado = False
        if enviar:
            publicado = enviar_alerta(
                tipo=f"{tipo} (sensores)", valor=valor, acao=grupo["acao"]
            )

        resultados.append(
            {
                "tipo": tipo,
                "valor": valor,
                "acao": grupo["acao"],
                "origem": "sensores",
                "publicado": publicado,
            }
        )

    if not grupos:
        print("Nenhuma condição de alerta identificada.")
    return resultados


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--arquivo", type=Path, default=ARQUIVO_SENSORES)
    parser.add_argument(
        "--enviar", action="store_true", help="publica os alertas no Amazon SNS"
    )
    args = parser.parse_args()

    print("=== FARMTECH SOLUTIONS ===")
    print("Alertas dos sensores\n")

    if not args.arquivo.exists():
        print(f"Arquivo de leituras não encontrado: {args.arquivo}")
        sys.exit(1)

    try:
        dados = pd.read_csv(args.arquivo)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
        print(f"Arquivo de leituras inválido: {args.arquivo}")
        sys.exit(1)

    faltando = {"umidade", "ph"} - set(dados.columns)
    if faltando:
        print(f"Colunas ausentes em {args.arquivo}: {', '.join(sorted(faltando))}")
        sys.exit(1)

    leituras = dados.to_dict("records")
    print(f"Leituras avaliadas: {len(leituras)}")
    alertas = verificar_leituras(leituras, args.enviar)
    print(f"\nQuantidade de alertas: {len(alertas)}")

    for alerta in alertas:
        print(f"\nTipo: {alerta['tipo']}")
        print(f"Valor: {alerta['valor']}")
        print(f"Ação: {alerta['acao']}")
        print(f"Publicado no SNS: {alerta['publicado']}")

    if args.enviar and not all(alerta["publicado"] for alerta in alertas):
        sys.exit(1)


if __name__ == "__main__":
    main()
