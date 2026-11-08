"""Gera alertas a partir das pragas detectadas pela visão computacional (Fase 6).

Uso (a partir da raiz do projeto):
    python -m src.aws.alertas_pragas            # apenas simula
    python -m src.aws.alertas_pragas --enviar   # publica no Amazon SNS

Lê o deteccoes.json gerado por inferir.py e cria um alerta por praga, com a ação
corretiva definida pelo grupo em src/fase6_visao_computacional/pragas.py.
"""

import argparse
import json
import sys
from pathlib import Path

from .alertas_aws import enviar_alerta

ARQUIVO_DETECCOES = (
    Path(__file__).resolve().parents[1]
    / "fase6_visao_computacional"
    / "resultados"
    / "deteccoes.json"
)
# Um alerta aciona pessoas em campo, então exige mais certeza que a detecção (0,25).
CONFIANCA_MINIMA = 0.50
MAX_IMAGENS_NO_ALERTA = 5


def agrupar_por_praga(deteccoes, confianca_minima=CONFIANCA_MINIMA):
    """Reúne as detecções confiáveis de cada praga em um único alerta."""
    grupos = {}
    for deteccao in deteccoes:
        if deteccao["confianca"] < confianca_minima:
            continue
        grupo = grupos.setdefault(
            deteccao["especie"],
            {
                "nome_popular": deteccao["nome_popular"],
                "acao": deteccao["acao_corretiva"],
                "quantidade": 0,
                "confianca": 0.0,
                "imagens": set(),
            },
        )
        grupo["quantidade"] += 1
        grupo["confianca"] = max(grupo["confianca"], deteccao["confianca"])
        grupo["imagens"].add(deteccao["arquivo"])
    return grupos


def verificar_pragas(deteccoes, confianca_minima=CONFIANCA_MINIMA, enviar=False):
    """Identifica as pragas e, opcionalmente, publica os alertas no Amazon SNS.

    enviar=False: apenas simula os alertas.
    enviar=True: publica os alertas no SNS.
    """
    resultados = []
    grupos = agrupar_por_praga(deteccoes, confianca_minima)
    for especie, grupo in grupos.items():
        imagens = sorted(grupo["imagens"])[:MAX_IMAGENS_NO_ALERTA]
        # O assunto do e-mail no SNS só aceita ASCII: não use acentos aqui.
        tipo = f"Praga detectada: {grupo['nome_popular']}"
        quantidade = grupo["quantidade"]
        valor = (
            f"{especie}: {quantidade} {'detecção' if quantidade == 1 else 'detecções'}, "
            f"confiança máxima de {grupo['confianca']:.0%}, "
            f"imagens: {', '.join(imagens)}"
        )
        print(f"Alerta identificado: {tipo}")

        publicado = False
        if enviar:
            publicado = enviar_alerta(tipo=tipo, valor=valor, acao=grupo["acao"])

        resultados.append(
            {
                "tipo": tipo,
                "valor": valor,
                "acao": grupo["acao"],
                "origem": "visao_computacional",
                "publicado": publicado,
            }
        )

    if not grupos:
        print(f"Nenhuma praga detectada com confiança de {confianca_minima:.0%} ou mais.")
    return resultados


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--arquivo", type=Path, default=ARQUIVO_DETECCOES)
    parser.add_argument("--confianca", type=float, default=CONFIANCA_MINIMA)
    parser.add_argument(
        "--enviar", action="store_true", help="publica os alertas no Amazon SNS"
    )
    args = parser.parse_args()

    print("=== FARMTECH SOLUTIONS ===")
    print("Alertas da visão computacional\n")

    if not args.arquivo.exists():
        print("Nenhuma detecção encontrada. Rode a detecção de pragas antes.")
        sys.exit(1)

    try:
        deteccoes = json.loads(args.arquivo.read_text(encoding="utf-8"))
        print(f"Detecções lidas: {len(deteccoes)}")
        alertas = verificar_pragas(deteccoes, args.confianca, args.enviar)
    except (KeyError, TypeError, ValueError):
        print(f"Arquivo de detecções inválido: {args.arquivo}")
        sys.exit(1)

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
