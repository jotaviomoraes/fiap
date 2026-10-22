"""
agropredict
-----------
Camada de servico do Sompo AgroPredict, independente da interface.

Fluxo de ponta a ponta:

    entrada (Leitura validada)
        -> banco (tabela `leituras`, status PENDENTE)
        -> modelo + regras de dominio (lidos a partir do banco)
        -> saida (tabelas `predicoes` e `alertas`, relatorios)

O dashboard Streamlit, os scripts de simulacao e a ingestao Oracle
consomem este pacote; nenhum deles recalcula score ou recomendacao
por conta propria.
"""
