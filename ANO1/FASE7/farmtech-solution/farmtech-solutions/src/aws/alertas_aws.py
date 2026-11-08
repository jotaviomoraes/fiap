import os
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Configurações da AWS
REGIAO = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
TOPICO_ARN = os.getenv("FARMTECH_SNS_TOPIC_ARN")


def enviar_alerta(tipo, valor, acao):
    """
    Envia um alerta agrícola utilizando o Amazon SNS.
    """

    if not TOPICO_ARN:
        print("Erro: variável FARMTECH_SNS_TOPIC_ARN não configurada.")
        return False

    assunto = f"FarmTech - Alerta: {tipo}"

    mensagem = f"""
ALERTA FARMTECH SOLUTIONS

Tipo de alerta: {tipo}
Valor registrado: {valor}

Ação corretiva sugerida:
{acao}

Sistema de Monitoramento Agrícola - FarmTech Solutions
"""

    try:
        sns = boto3.client("sns", region_name=REGIAO)

        resposta = sns.publish(
            TopicArn=TOPICO_ARN,
            Subject=assunto,
            Message=mensagem
        )

        print("Alerta publicado no Amazon SNS com sucesso!")
        print("ID da mensagem:", resposta["MessageId"])

        return True

    except (ClientError, BotoCoreError, NoCredentialsError) as erro:
        print("Erro ao publicar alerta:", erro)
        return False
