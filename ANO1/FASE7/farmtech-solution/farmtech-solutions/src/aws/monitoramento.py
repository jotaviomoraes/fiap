import math

from .alertas_aws import enviar_alerta


def ler_valor(dados, campo):
    """Converte a leitura em número. Devolve None se ela for ausente ou inválida."""
    try:
        valor = float(dados[campo])
    except (KeyError, TypeError, ValueError):
        return None
    return None if math.isnan(valor) else valor


def identificar_alertas(dados):
    """
    Aplica as regras de monitoramento a uma leitura,
    sem publicar nada no Amazon SNS.
    """

    alertas = []

    umidade = ler_valor(dados, "umidade")
    ph = ler_valor(dados, "ph")

    # Uma leitura sem valor não pode passar como condição normal
    invalidos = [
        campo for campo, valor in (("umidade", umidade), ("pH", ph)) if valor is None
    ]
    if invalidos:
        alertas.append({
            "tipo": "Falha na leitura do sensor",
            "valor": f"{' e '.join(invalidos)} sem valor válido",
            "acao": "Verificar o funcionamento do sensor e repetir a leitura."
        })

    # Regras de demonstração alinhadas ao módulo de ML
    if umidade is not None and umidade < 40:
        alertas.append({
            "tipo": "Umidade baixa",
            "valor": f"{umidade:g}%",
            "acao": "Verificar a necessidade de irrigação."
        })

    if ph is not None and ph < 5.5:
        alertas.append({
            "tipo": "pH baixo",
            "valor": f"{ph:g}",
            "acao": "Solicitar análise do solo para avaliar correção de acidez."
        })

    elif ph is not None and ph > 7.0:
        alertas.append({
            "tipo": "pH elevado",
            "valor": f"{ph:g}",
            "acao": "Solicitar análise do solo para avaliar correção do pH."
        })

    return alertas


def verificar_sensores(dados, origem="dataset", enviar=False):
    """
    Verifica condições agrícolas e, opcionalmente,
    publica alertas no Amazon SNS.

    enviar=False: apenas simula os alertas.
    enviar=True: publica os alertas no SNS.
    """

    alertas = identificar_alertas(dados)

    resultados = []

    for alerta in alertas:
        print(f"Alerta identificado: {alerta['tipo']}")

        publicado = False

        if enviar:
            publicado = enviar_alerta(
                tipo=f"{alerta['tipo']} ({origem})",
                valor=alerta["valor"],
                acao=alerta["acao"]
            )

        resultados.append({
            **alerta,
            "origem": origem,
            "publicado": publicado
        })

    if not alertas:
        print("Nenhuma condição de alerta identificada.")

    return resultados
