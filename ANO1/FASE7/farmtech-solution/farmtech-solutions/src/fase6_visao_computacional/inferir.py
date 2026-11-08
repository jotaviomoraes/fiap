"""Detecta pragas em imagens e grava o resultado em CSV e JSON.

Uso (a partir da raiz do projeto):
    python src/fase6_visao_computacional/inferir.py --fonte caminho/da/imagem_ou_pasta

Saídas em resultados/: deteccoes.csv, deteccoes.json e as imagens com as caixas
desenhadas. O JSON é o arquivo previsto para alimentar os alertas na AWS.
"""

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import cv2
from ultralytics import YOLO

from pragas import CLASSES

PASTA_BASE = Path(__file__).resolve().parent
MODELO_PADRAO = PASTA_BASE / "modelos" / "best.pt"
SAIDA_PADRAO = PASTA_BASE / "resultados"
CONFIANCA_PADRAO = 0.25

CAMPOS_CSV = [
    "data_hora",
    "arquivo",
    "classe_id",
    "especie",
    "nome_popular",
    "confianca",
    "x1",
    "y1",
    "x2",
    "y2",
    "acao_corretiva",
]


def detectar(fonte, caminho_modelo, confianca, pasta_saida):
    """Roda o modelo e devolve uma lista com uma detecção por inseto."""
    pasta_imagens = pasta_saida / "imagens"
    pasta_imagens.mkdir(parents=True, exist_ok=True)

    modelo = YOLO(caminho_modelo)
    data_hora = datetime.now().isoformat(timespec="seconds")
    deteccoes = []
    imagens_lidas = 0
    for resultado in modelo.predict(
        source=str(fonte), conf=confianca, stream=True, verbose=False
    ):
        imagens_lidas += 1
        arquivo = Path(resultado.path).name
        cv2.imwrite(str(pasta_imagens / arquivo), resultado.plot())
        for caixa in resultado.boxes:
            classe_id = int(caixa.cls)
            x1, y1, x2, y2 = (round(valor, 1) for valor in caixa.xyxy[0].tolist())
            deteccoes.append(
                {
                    "data_hora": data_hora,
                    "arquivo": arquivo,
                    "classe_id": classe_id,
                    "especie": CLASSES[classe_id]["especie"],
                    "nome_popular": CLASSES[classe_id]["nome_popular"],
                    "confianca": round(float(caixa.conf), 4),
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "acao_corretiva": CLASSES[classe_id]["acao_corretiva"],
                }
            )

    # O Ultralytics ignora imagens corrompidas sem erro, o que pareceria "sem pragas"
    if not imagens_lidas:
        raise SystemExit(f"Nenhuma imagem válida em: {fonte}")
    return deteccoes


def salvar(deteccoes, pasta_saida):
    """Grava as detecções, substituindo o resultado da execução anterior."""
    pasta_saida.mkdir(parents=True, exist_ok=True)
    with open(
        pasta_saida / "deteccoes.csv", "w", newline="", encoding="utf-8-sig"
    ) as saida:
        escritor = csv.DictWriter(saida, fieldnames=CAMPOS_CSV)
        escritor.writeheader()
        escritor.writerows(deteccoes)
    (pasta_saida / "deteccoes.json").write_text(
        json.dumps(deteccoes, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fonte", type=Path, required=True)
    parser.add_argument("--modelo", type=Path, default=MODELO_PADRAO)
    parser.add_argument("--conf", type=float, default=CONFIANCA_PADRAO)
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    args = parser.parse_args()

    if not args.modelo.exists():
        raise SystemExit(f"Modelo não encontrado: {args.modelo}")
    if not args.fonte.exists():
        raise SystemExit(f"Imagem ou pasta não encontrada: {args.fonte}")

    try:
        deteccoes = detectar(args.fonte, args.modelo, args.conf, args.saida)
    except FileNotFoundError:
        raise SystemExit(f"Nenhuma imagem válida em: {args.fonte}")
    salvar(deteccoes, args.saida)
    print(f"{len(deteccoes)} detecção(ões). Resultados em {args.saida}")


if __name__ == "__main__":
    main()
