# o que achou dessa aplicacao ?

A página Análise de sentimento oferece **Português / Inglês**, começando em português independentemente do idioma da interface. Digite um texto e clique em Analisar sentimento. A rede retorna BOM se P(positivo) > 50%; caso contrário, RUIM. As duas probabilidades são exibidas.

O último elemento da análise é o gráfico do notebook RNN: probabilidade de positivo após cada palavra, linha pontilhada em 50%, área verde acima e vermelha abaixo. Os prefixos são calculados em lotes de até 64 e o último ponto é o valor usado na decisão final. Até 40 palavras, o eixo mostra as palavras; acima disso, mostra sua contagem.

## Modelos

- Português: arquivo feedback_bilstm.pt preservado, BiLSTM B2W, vocabulário 20.000 e até 119 palavras mais o token inicial. Acurácia B2W: 92,36%.
- Inglês: feedback_bilstm_en.pt, mesma arquitetura BiLSTM, vocabulário IMDB 10.000 e até 199 palavras mais o token inicial. Treino CUDA com 22.500 exemplos, validação 2.500 e teste oficial separado de 25.000. Melhor perda de validação em três épocas; acurácia no teste IMDB: 85,05%.

O inglês usa a preparação do notebook: deslocamento de índices em 3, início 1, desconhecido 2 e regex inglesa com apóstrofos. Português preserva sua tokenização com acentos. Cada artefato inclui seu idioma, vocabulário, configuração e metadados; carregar um artefato no idioma incorreto é rejeitado.

As métricas se referem a avaliações de produtos/filmes e não validam especificamente comentários sobre o AgroPredict. Não há tradução automática, notas manuais, gravação de textos ou retreino pela interface. As probabilidades não são confiança calibrada.

## Execução

Use scripts/run_dashboard.ps1. O notebook adaptado é src/modelo/feedback_projeto.ipynb e permite escolher IDIOMA como pt ou en.

Variáveis opcionais: FEEDBACK_MODELO aponta para os pesos portugueses; FEEDBACK_MODELO_EN aponta para os ingleses. Se o modelo selecionado estiver indisponível, a análise é desabilitada sem substituição por outro idioma. Alterar o texto ou idioma limpa o resultado anterior.

O Streamlit carrega os pesos em cache, com CUDA quando disponível e CPU como alternativa. O treino ocorre somente offline. Para reproduzir o inglês: python scripts/treinar_feedback_ingles.py. O script português continua disponível em scripts/treinar_feedback.py. Dependências em config/requirements-feedback.txt.

## Raio-X das palavras e diagnóstico técnico

O raio-X segue a aplicação RNN original: para cada palavra, remove apenas aquela ocorrência e calcula novamente a probabilidade de positivo. A influência é P(texto) menos P(texto sem a palavra). As remoções são inferidas em lotes de até 64, preservando a ordem das palavras restantes e o mesmo limite de leitura do modelo.

O destaque é verde quando favorece BOM, vermelho quando favorece RUIM e neutro quando a influência é pequena, com limiar max(0,02; 0,15 × maior influência absoluta). Palavras fora do vocabulário ficam sublinhadas. As palavras são escapadas antes de compor o HTML. A influência é contextual e não uma importância causal universal.

O diagnóstico mostra nome e versão do modelo, acurácia no teste de origem B2W/IMDB, probabilidade bruta de positivo, palavras lidas e total recebido, quantidade de desconhecidas (<UNK>), dispositivo de execução e as três palavras com maior influência absoluta, incluindo o sinal da diferença de probabilidade.

O gráfico de leitura progressiva continua sendo o último elemento do resultado. Não há retreino nem gravação dos textos. O notebook adaptado também inclui o raio-X e o diagnóstico usando as mesmas funções da página.
