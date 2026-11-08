# Módulo AWS — FarmTech Solutions

## 1. Objetivo

Este módulo implementa o monitoramento de condições agrícolas e o envio automatizado de alertas por e-mail utilizando o **Amazon Simple Notification Service (SNS)**.

A solução faz parte da Fase 7 do projeto FarmTech Solutions, que integra dados agrícolas, Machine Learning, dashboard e serviços AWS.

O módulo foi desenvolvido para funcionar de forma independente, permitindo sua integração à dashboard Streamlit do projeto.

## 2. Estrutura dos arquivos

```text
src/
├── aws/
│   ├── __init__.py
│   ├── alertas_aws.py
│   ├── alertas_pragas.py
│   ├── alertas_sensores.py
│   ├── monitoramento.py
│   ├── teste_alertas.py
│   └── README.md
│
├── dashboard/
│   ├── servicos.py
│   └── streamlit_app.py
│
└── fase3_banco_oracle/
    └── sensores_agricolas.csv
```

**Descrição dos arquivos:**

- `alertas_aws.py`: realiza a comunicação com o Amazon SNS e publica as mensagens de alerta.
- `monitoramento.py`: define as regras de monitoramento e as ações corretivas.
- `alertas_sensores.py`: lê as leituras dos sensores e gera um alerta por tipo de condição.
- `alertas_pragas.py`: lê as detecções da visão computacional e gera um alerta por praga.
- `teste_alertas.py`: testa as regras com registros do dataset agrícola, sem enviar nada.
- `__init__.py`: permite organizar o módulo como um pacote Python.
- `README.md`: apresenta as instruções de configuração, execução e integração.

## 3. Regras de monitoramento

O módulo utiliza regras demonstrativas para identificar possíveis condições que exigem atenção.

| Condição | Alerta | Ação sugerida |
|---|---|---|
| Umidade inferior a 40% | Umidade baixa | Verificar a necessidade de irrigação |
| pH inferior a 5,5 | pH baixo | Solicitar análise do solo para avaliar correção de acidez |
| pH superior a 7,0 | pH elevado | Solicitar análise do solo para avaliar correção do pH |
| Umidade ou pH ausente ou inválido | Falha na leitura do sensor | Verificar o funcionamento do sensor e repetir a leitura |
| Valores dentro dos limites | Nenhum alerta | Continuar o monitoramento |

**Observação:** os limites são demonstrativos e devem ser ajustados conforme a cultura, as condições agrícolas e a origem dos dados.

As regras são aplicadas às leituras do ESP32 em `src/fase3_banco_oracle/sensores_agricolas.csv`. Nas pragas, a ação corretiva de cada espécie está em `src/fase6_visao_computacional/pragas.py`.

## 4. Instalação das dependências

Na raiz do repositório, execute:

```powershell
python -m pip install -r requirements.txt
```

As principais bibliotecas utilizadas pelo módulo são:

- `boto3`: integração com serviços AWS, incluindo o Amazon SNS.
- `pandas`: leitura e manipulação do dataset agrícola.

Ambas estão declaradas no `requirements.txt` do projeto.

## 5. Configuração do Amazon SNS

Para realizar o envio real dos alertas, é necessário:

1. Possuir acesso a uma conta AWS ou ao AWS Academy Learner Lab.
2. Criar um tópico Standard no Amazon SNS.
3. Adicionar uma assinatura do tipo e-mail.
4. Confirmar a assinatura pelo e-mail recebido.
5. Configurar credenciais AWS válidas.
6. Preencher `FARMTECH_SNS_TOPIC_ARN` no arquivo `.env` da raiz do projeto.

O tópico utilizado durante o desenvolvimento foi:

```text
farmtech-alertas
```

A região utilizada foi `us-east-1`.

### Configuração das variáveis

Copie `.env.example` para `.env` e preencha o ARN completo do tópico existente na conta AWS:

```text
AWS_DEFAULT_REGION=us-east-1
FARMTECH_SNS_TOPIC_ARN=ARN_DO_SEU_TOPICO_SNS
```

O módulo lê o `.env` automaticamente. Variáveis definidas no terminal também funcionam.

**Segurança:** nunca publique credenciais AWS, chaves de acesso ou tokens de sessão no GitHub. Utilize o arquivo local de credenciais AWS ou outro mecanismo seguro de autenticação.

## 6. Integração com a dashboard

A dashboard dispara os alertas pela aba **Serviços**, no grupo **Fase 7 — Alertas na AWS**, com um botão para simular e outro para enviar cada origem.

Os botões executam os mesmos comandos do terminal, a partir da raiz do projeto. Assim, a dashboard não precisa importar este módulo. O botão de envio fica desativado enquanto `FARMTECH_SNS_TOPIC_ARN` não estiver preenchida.

## 7. Ativação dos alertas AWS

### Simulação

```powershell
python -m src.aws.alertas_sensores
python -m src.aws.alertas_pragas
```

Nesse modo:

- Os dados agrícolas são analisados normalmente.
- As condições de alerta são identificadas.
- As ações corretivas são apresentadas.
- Nenhuma mensagem é enviada ao Amazon SNS.

Esse é o modo recomendado durante o desenvolvimento e os testes locais.

### Envio real

```powershell
python -m src.aws.alertas_sensores --enviar
python -m src.aws.alertas_pragas --enviar
```

Nesse modo:

- Os dados agrícolas são analisados.
- As condições de alerta são identificadas.
- As mensagens são publicadas no Amazon SNS.
- O SNS encaminha as notificações aos assinantes confirmados, conforme a configuração do tópico.

Se uma publicação falhar, o comando termina com erro e a dashboard mostra a falha.

Antes de enviar, confirme que as credenciais AWS estão válidas, o tópico SNS existe, a variável `FARMTECH_SNS_TOPIC_ARN` está configurada e a assinatura de e-mail foi confirmada.

No AWS Academy Learner Lab, o laboratório também precisa estar ativo.

### Volume de e-mails

Cada execução envia um e-mail por tipo de alerta, e não um por leitura. Com as 10 leituras atuais dos sensores, são 2 e-mails: pH baixo (2 leituras) e umidade baixa (6 leituras).

O módulo não guarda o que já foi enviado. Cada nova execução com envio gera novos e-mails.

### Confirmação de entrega

`Publicado no SNS: True` indica que o SNS aceitou a mensagem, não que o e-mail chegou. Para conferir a entrega:

- Só os assinantes com status **Confirmado** recebem as mensagens.
- Procure também nas pastas de spam e de promoções.
- O SNS tenta entregar o e-mail por até 6 horas. Depois disso, a mensagem é descartada, pois este tópico não usa fila de mensagens mortas.
- Pragas com confiança abaixo de 50% aparecem na dashboard, mas não geram alerta.
- Os alertas de pragas usam só o resultado da última detecção.

## 8. Execução dos testes

Na raiz do repositório, execute:

```powershell
python -m src.aws.teste_alertas
```

O arquivo de teste utiliza o dataset existente em:

```text
src/dashboard/dataset_agricola.csv
```

Os testes verificam três situações:

1. Identificação de pH baixo.
2. Identificação de umidade baixa.
3. Reconhecimento de condições normais, sem geração de alertas.

**Importante:** mantenha `enviar=False` em todas as chamadas do arquivo `teste_alertas.py`, evitando disparos desnecessários de e-mails.

## 9. Resultados dos testes

As regras foram validadas utilizando um dataset agrícola com 500 registros.

| Cenário | Valores observados | Resultado |
|---|---|---|
| pH baixo | pH 4,81 | 1 alerta identificado |
| Umidade baixa | Umidade 28,8% | 1 alerta identificado |
| Condições normais | Umidade 68,2% e pH 6,84 | Nenhum alerta |

Nas 10 leituras dos sensores, a simulação gera 2 alertas: pH baixo em 2 leituras e umidade baixa em 6 leituras.

Também foi realizado um teste de publicação no Amazon SNS utilizando o projeto AWS original, com evidências da publicação e do e-mail recebido. As evidências 07 a 09 vêm desse projeto, com registros do dataset agrícola.

Após a organização dos arquivos no repositório compartilhado, os testes locais foram executados novamente com sucesso.

## 10. Status da implementação

**Funcionalidades concluídas:**

- Leitura das leituras dos sensores e das detecções de pragas.
- Identificação automática de condições de alerta.
- Geração de recomendações corretivas.
- Integração com Amazon SNS.
- Envio de notificações por e-mail validado no AWS Academy Learner Lab.
- Acionamento controlado pela dashboard e pelo terminal.
- Um alerta por tipo a cada execução, para evitar excesso de e-mails.
- Testes locais executados com sucesso na estrutura do repositório compartilhado.

**Próxima etapa:**

- Executar `python -m src.aws.alertas_sensores --enviar` no Learner Lab e registrar o e-mail recebido.

## Evidências da implementação AWS

As capturas de tela da configuração e dos testes estão disponíveis na pasta [`assets/aws`](../../assets/aws/).

### Configuração do Amazon SNS

- [01 — Tópico SNS FarmTech](../../assets/aws/01_topico_sns_farmtech.png)
- [02 — Assinatura de e-mail confirmada](../../assets/aws/02_assinatura_email_confirmada.png)

### Testes de publicação e recebimento

- [03 — Mensagem publicada no SNS](../../assets/aws/03_mensagem_sns_publicada.png)
- [04 — E-mail de alerta recebido](../../assets/aws/04_email_alerta_recebido.png)
- [05 — Publicação de alerta via Python](../../assets/aws/05_python_sns_sucesso.png)
- [06 — E-mail recebido após execução Python](../../assets/aws/06_email_alerta_python.png)

### Integração com dados agrícolas

- [07 — Teste de integração com sensores](../../assets/aws/07_teste_integracao_sensores.png)
- [08 — Alerta do dataset publicado no SNS](../../assets/aws/08_alerta_dataset_sns_sucesso.png)
- [09 — E-mail de alerta gerado a partir do dataset](../../assets/aws/09_email_alerta_dataset.png)

Essas evidências demonstram a configuração do serviço, a execução dos testes e o recebimento das notificações por e-mail.

## 11. Considerações finais

O módulo AWS permite que o FarmTech Solutions identifique condições agrícolas que exigem atenção e, quando configurado para envio real, publique notificações pelo Amazon SNS.

A implementação separa a lógica de monitoramento da comunicação com a AWS, facilitando testes locais, manutenção e integração com os demais componentes do projeto.

Essa abordagem contribui para a construção de um sistema integrado de monitoramento agrícola, com suporte a alertas e acompanhamento das condições analisadas.