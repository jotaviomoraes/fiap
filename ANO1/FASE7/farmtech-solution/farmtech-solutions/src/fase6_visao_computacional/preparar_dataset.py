"""Divide o AgroInsect em treino, validação e teste no formato da YOLO.

Uso (a partir da raiz do projeto):
    python src/fase6_visao_computacional/preparar_dataset.py

Imagens iguais ou quase iguais ficam sempre no mesmo conjunto. Sem isso, o teste
teria fotos já vistas no treino e as métricas ficariam infladas.
"""

import argparse
import csv
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

from pragas import CLASSES, NOMES_YOLO

PASTA_BASE = Path(__file__).resolve().parent
ORIGEM_PADRAO = PASTA_BASE / "dataset" / "raw"
DESTINO_PADRAO = PASTA_BASE / "dataset" / "yolo"

PROPORCOES = {"train": 0.70, "val": 0.15, "test": 0.15}
LADO_HASH = 16
# Diferença máxima, em bits (de 256), para considerar duas imagens quase iguais.
LIMITE_DUPLICATA = 20


def calcular_dhash(caminho):
    """Resume a imagem em 256 bits que mudam pouco entre fotos parecidas."""
    with Image.open(caminho) as imagem:
        cinza = imagem.convert("L").resize((LADO_HASH + 1, LADO_HASH))
    pixels = list(cinza.getdata())
    valor = 0
    for linha in range(LADO_HASH):
        inicio = linha * (LADO_HASH + 1)
        for coluna in range(LADO_HASH):
            esquerda = pixels[inicio + coluna]
            direita = pixels[inicio + coluna + 1]
            valor = (valor << 1) | (esquerda > direita)
    return valor


def agrupar_duplicatas(imagens):
    """Agrupa as imagens quase iguais usando union-find."""
    hashes = [calcular_dhash(caminho) for caminho in imagens]
    pais = list(range(len(imagens)))

    def raiz(indice):
        while pais[indice] != indice:
            pais[indice] = pais[pais[indice]]
            indice = pais[indice]
        return indice

    for i in range(len(imagens)):
        for j in range(i + 1, len(imagens)):
            if bin(hashes[i] ^ hashes[j]).count("1") <= LIMITE_DUPLICATA:
                pais[raiz(i)] = raiz(j)

    grupos = defaultdict(list)
    for indice, caminho in enumerate(imagens):
        grupos[raiz(indice)].append(caminho)
    return list(grupos.values())


def classe_da_imagem(caminho_rotulo):
    """Devolve a classe da imagem (no AgroInsect, cada imagem tem uma só)."""
    with open(caminho_rotulo, encoding="utf-8") as arquivo:
        return int(arquivo.readline().split()[0])


def dividir_grupos(grupos_por_classe, seed):
    """Divide os grupos de cada classe, mantendo as proporções entre elas."""
    sorteio = random.Random(seed)
    divisao = {}
    for classe in sorted(grupos_por_classe):
        grupos = sorted(grupos_por_classe[classe], key=lambda g: g[0].name)
        sorteio.shuffle(grupos)
        total = sum(len(grupo) for grupo in grupos)
        limite_treino = total * PROPORCOES["train"]
        limite_val = limite_treino + total * PROPORCOES["val"]
        acumulado = 0
        for grupo in grupos:
            if acumulado < limite_treino:
                conjunto = "train"
            elif acumulado < limite_val:
                conjunto = "val"
            else:
                conjunto = "test"
            for caminho in grupo:
                divisao[caminho] = conjunto
            acumulado += len(grupo)
    return divisao


def copiar_para_yolo(divisao, origem, destino):
    """Monta a estrutura de pastas que a YOLO espera."""
    if destino.exists():
        shutil.rmtree(destino)
    for conjunto in PROPORCOES:
        (destino / "images" / conjunto).mkdir(parents=True)
        (destino / "labels" / conjunto).mkdir(parents=True)

    linhas = []
    for imagem, conjunto in sorted(divisao.items()):
        rotulo = origem / "label" / f"{imagem.stem}.txt"
        shutil.copy2(imagem, destino / "images" / conjunto / imagem.name)
        shutil.copy2(rotulo, destino / "labels" / conjunto / rotulo.name)
        linhas.append(
            {
                "arquivo": imagem.name,
                "conjunto": conjunto,
                "classe": classe_da_imagem(rotulo),
            }
        )

    with open(destino / "divisao.csv", "w", newline="", encoding="utf-8") as saida:
        escritor = csv.DictWriter(saida, fieldnames=["arquivo", "conjunto", "classe"])
        escritor.writeheader()
        escritor.writerows(linhas)
    return linhas


def escrever_data_yaml(destino):
    """Gera o data.yaml com o caminho absoluto desta máquina."""
    nomes = "\n".join(f"  {i}: {nome}" for i, nome in enumerate(NOMES_YOLO))
    conteudo = (
        f"path: {destino.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        f"names:\n{nomes}\n"
    )
    (destino / "data.yaml").write_text(conteudo, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--origem", type=Path, default=ORIGEM_PADRAO)
    parser.add_argument("--destino", type=Path, default=DESTINO_PADRAO)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    imagens = sorted((args.origem / "image").glob("*.jpg"))
    if not imagens:
        raise SystemExit(f"Nenhuma imagem encontrada em {args.origem / 'image'}.")

    grupos = agrupar_duplicatas(imagens)
    grupos_por_classe = defaultdict(list)
    for grupo in grupos:
        rotulo = args.origem / "label" / f"{grupo[0].stem}.txt"
        grupos_por_classe[classe_da_imagem(rotulo)].append(grupo)

    divisao = dividir_grupos(grupos_por_classe, args.seed)
    linhas = copiar_para_yolo(divisao, args.origem, args.destino)
    escrever_data_yaml(args.destino)

    repetidas = sum(len(grupo) for grupo in grupos if len(grupo) > 1)
    print(f"Imagens: {len(imagens)} | em grupos de duplicatas: {repetidas}")
    print(f"Conjuntos: {dict(Counter(linha['conjunto'] for linha in linhas))}")
    for classe, dados in CLASSES.items():
        contagem = Counter(
            linha["conjunto"] for linha in linhas if linha["classe"] == classe
        )
        print(f"  {classe} {dados['especie']}: {dict(contagem)}")
    print(f"Pronto: {args.destino / 'data.yaml'}")


if __name__ == "__main__":
    main()
