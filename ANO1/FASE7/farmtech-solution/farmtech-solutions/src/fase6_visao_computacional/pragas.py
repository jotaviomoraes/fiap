"""Classes do dataset AgroInsect e as ações corretivas definidas pelo grupo.

O AgroInsect não traz um arquivo com os nomes das classes. A correspondência
abaixo foi conferida visualmente, olhando uma amostra de imagens de cada ID.
"""

CLASSES = {
    0: {
        "especie": "Diabrotica speciosa",
        "nome_popular": "Vaquinha",
        "acao_corretiva": (
            "Vistoriar folhas e raízes no talhão, registrar a contagem de "
            "insetos e acionar o agrônomo se houver desfolha."
        ),
    },
    1: {
        "especie": "Dalbulus maidis",
        "nome_popular": "Cigarrinha-do-milho",
        "acao_corretiva": (
            "Priorizar a vistoria das plantas jovens de milho, verificar "
            "sintomas de enfezamento e acionar o agrônomo."
        ),
    },
    2: {
        "especie": "Diceraeus spp.",
        "nome_popular": "Percevejo-barriga-verde",
        "acao_corretiva": (
            "Vistoriar plântulas e palhada no talhão, registrar a contagem "
            "de insetos e acionar o agrônomo."
        ),
    },
    3: {
        "especie": "Spodoptera frugiperda",
        "nome_popular": "Mariposa da lagarta-do-cartucho",
        "acao_corretiva": (
            "A classe foi treinada principalmente com mariposas adultas; "
            "a detecção não confirma a presença de lagartas. "
            "Inspecionar o cartucho das plantas em busca de ovos e lagartas "
            "e acionar o agrônomo se houver folhas raspadas."
        ),
    },
}

NOMES_YOLO = [CLASSES[indice]["especie"] for indice in sorted(CLASSES)]
