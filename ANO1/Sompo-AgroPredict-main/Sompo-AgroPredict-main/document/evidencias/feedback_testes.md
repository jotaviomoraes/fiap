# Validação bilíngue — 05/11/2026

- Suíte completa: 97 testes, resultado OK (sentimento_testes.txt).
- Streamlit: título exato, português como padrão independente do idioma da interface, classificação positiva/negativa nos dois idiomas, gráfico exibido, limpeza do resultado na troca de texto/idioma e bloqueio sem modelo selecionado.
- Inferência: correspondência entre palavras e pontos, valores entre 0 e 1, último ponto igual à probabilidade da classificação e compatibilidade com a predição direta. Testados texto vazio, texto curto, limite de palavras e rejeição de artefato do idioma errado.
- Gráfico: limiar 50%, eixo entre 0 e 1, pontos e palavras verificados por testes; renderização inspecionada em leitura_progressiva.png.
- Notebook: células executadas em português e inglês, em CUDA, sem retreinar.
- Treino IMDB: três épocas na RTX 5060 Ti; 22.500 exemplos de treino, 2.500 de validação e teste oficial de 25.000. Acurácia 85,048%; metadados em src/modelo/feedback_bilstm_en.json.
- Pesos portugueses preservados: SHA-256 F24C681C5558D72366A0577C84A1FDD00AA82EF60D4443831886F251353EC300.
- Streamlit reiniciado na porta 8501; healthcheck HTTP 200.

As métricas B2W/IMDB não demonstram desempenho específico em comentários do AgroPredict. Nenhum texto digitado é gravado ou usado automaticamente para retreino.

## Atualização: raio-X e diagnóstico técnico

Suíte atual: **99 testes, resultado OK**. Foram verificadas as probabilidades com remoção individual de palavras, indicação de termos desconhecidos, escape de HTML e os dados do diagnóstico. Os testes Streamlit confirmam raio-X e diagnóstico nos dois idiomas e a permanência do gráfico. O modelo não foi retreinado. O AgroPredict foi reiniciado e respondeu HTTP 200 na porta 8501.
