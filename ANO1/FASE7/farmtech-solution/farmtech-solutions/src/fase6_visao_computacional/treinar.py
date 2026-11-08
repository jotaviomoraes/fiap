"""Treina a YOLOv5s com o AgroInsect e avalia o melhor modelo no conjunto de teste.

Uso (a partir da raiz do projeto):
    python src/fase6_visao_computacional/treinar.py

O pacote Ultralytics carrega o modelo pedido, yolov5s.pt, como yolov5su.pt, a
versão atual da YOLOv5s. O batch padrão é 8. Use 16 somente quando houver
pelo menos 6 GB livres na GPU e memória de sistema suficiente. O padrão de
--workers é 0, o valor do treino validado, que evita subprocessos no Windows.
"""

import argparse
import json
import shutil
from pathlib import Path

from ultralytics import YOLO

PASTA_BASE = Path(__file__).resolve().parent
DATA_YAML = PASTA_BASE / "dataset" / "yolo" / "data.yaml"
PASTA_MODELOS = PASTA_BASE / "modelos"
PASTA_RUNS = PASTA_BASE / "runs"


def avaliar_teste(modelo, data_yaml, imgsz, batch, workers=0):
    """Calcula as métricas no conjunto de teste, geral e por classe."""
    metricas = modelo.val(
        data=str(data_yaml),
        split="test",
        imgsz=imgsz,
        batch=batch,
        workers=workers,
        project=str(PASTA_RUNS),
        name="teste",
        exist_ok=True,
    )
    por_classe = {}
    for posicao, indice in enumerate(metricas.box.ap_class_index):
        por_classe[modelo.names[int(indice)]] = {
            "precision": round(float(metricas.box.p[posicao]), 4),
            "recall": round(float(metricas.box.r[posicao]), 4),
            "map50": round(float(metricas.box.ap50[posicao]), 4),
            "map50_95": round(float(metricas.box.ap[posicao]), 4),
        }
    return {
        "precision": round(float(metricas.box.mp), 4),
        "recall": round(float(metricas.box.mr), 4),
        "map50": round(float(metricas.box.map50), 4),
        "map50_95": round(float(metricas.box.map), 4),
        "por_classe": por_classe,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=DATA_YAML)
    parser.add_argument("--modelo", default="yolov5s.pt")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=90)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not args.data.exists():
        raise SystemExit("data.yaml não encontrado. Rode preparar_dataset.py antes.")

    PASTA_MODELOS.mkdir(exist_ok=True)
    modelo = YOLO(args.modelo)
    resultado = modelo.train(
        data=str(args.data),
        imgsz=args.imgsz,
        batch=args.batch,
        epochs=args.epochs,
        patience=args.patience,
        workers=args.workers,
        seed=args.seed,
        project=str(PASTA_RUNS),
        name="agroinsect",
        exist_ok=True,
    )

    melhor = PASTA_MODELOS / "best.pt"
    shutil.copy2(Path(resultado.save_dir) / "weights" / "best.pt", melhor)

    metricas = avaliar_teste(
        YOLO(melhor), args.data, args.imgsz, args.batch, args.workers
    )
    caminho_metricas = PASTA_MODELOS / "metricas_teste.json"
    caminho_metricas.write_text(
        json.dumps(metricas, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Modelo salvo em {melhor}")
    print(json.dumps(metricas, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
