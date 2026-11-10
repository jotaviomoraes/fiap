'Textos do diagnóstico técnico em português, inglês e espanhol.'

CATALOGO_RAIO_X = [('Escala de 80% a 100%, com linhas a cada 5 pontos percentuais, incluindo as métricas da regressão logística.',
  'Scale from 80% to 100%, with gridlines every 5 percentage points, including logistic regression metrics.',
  'Escala del 80% al 100%, con líneas cada 5 puntos porcentuales, incluidas las métricas de regresión '
  'logística.'),
 ('Série', 'Series', 'Serie'),
 ('Métrica', 'Metric', 'Métrica'),
 ('As linhas conectam categorias para facilitar a comparação; não representam evolução temporal. Passe o '
  'mouse sobre os pontos para consultar os valores.',
  'Lines connect categories to aid comparison; they do not represent change over time. Hover over the points '
  'to see values.',
  'Las líneas conectan categorías para facilitar la comparación; no representan evolución temporal. Pase el '
  'cursor sobre los puntos para consultar los valores.'),
 ('Raio X', 'Model diagnostics', 'Diagnóstico de modelos'),
 ('🔬 Raio X dos modelos', '🔬 Model diagnostics', '🔬 Diagnóstico de modelos'),
 ('Regressão Logística (baseline)', 'Logistic Regression (baseline)', 'Regresión logística (baseline)'),
 ('Comparação dos candidatos de risco', 'Risk candidate comparison', 'Comparación de candidatos de riesgo'),
 ('Recall ALTO (%)', 'HIGH recall (%)', 'Recall ALTO (%)'),
 ('Acurácia', 'Accuracy', 'Exactitud'),
 ('Validação cruzada (%)', 'Cross-validation (%)', 'Validación cruzada (%)'),
 ('Mesma base, divisão estratificada e validação cruzada de 5 partes no treino. Quanto maior, melhor; estas '
  'linhas não são resultados de teste.',
  'Same dataset, stratified split and 5-fold cross-validation on training data. Higher is better; these '
  'lines are not test results.',
  'Misma base, división estratificada y validación cruzada de 5 partes en entrenamiento. Mayor es mejor; '
  'estas líneas no son resultados de prueba.'),
 ('{modelo} venceu: F1 macro de {f1} na validação cruzada, com recall de ALTO de {recall}. O critério exige '
  'recall de ALTO ≥ 95% e, entre os elegíveis, o maior F1 macro.',
  '{modelo} won: cross-validation macro F1 of {f1}, with HIGH recall of {recall}. The criterion requires '
  'HIGH recall ≥ 95% and the highest macro F1 among eligible candidates.',
  '{modelo} ganó: F1 macro de {f1} en validación cruzada, con recall ALTO de {recall}. El criterio exige '
  'recall ALTO ≥ 95% y el mayor F1 macro entre los elegibles.'),
 ('{modelo} não atingiu o recall mínimo de ALTO: {recall}.',
  '{modelo} did not reach the minimum HIGH recall: {recall}.',
  '{modelo} no alcanzó el recall mínimo de ALTO: {recall}.'),
 ('O modelo final passou por remoção de variável após a seleção. Por isso suas métricas diferem das do '
  'candidato Gradient Boosting.',
  'A feature was removed from the final model after selection. Its metrics therefore differ from those of '
  'the Gradient Boosting candidate.',
  'Se eliminó una variable del modelo final después de la selección. Por eso sus métricas difieren de las '
  'del candidato Gradient Boosting.'),
 ('Diagnóstico das métricas salvas no treinamento. Esta página lê apenas JSON; não treina nem executa os '
  'modelos.',
  'Diagnostics from metrics saved during training. This page only reads JSON; it does not train or run '
  'models.',
  'Diagnóstico de las métricas guardadas durante entrenamiento. Esta página solo lee JSON; no entrena ni '
  'ejecuta modelos.'),
 ('Todos os modelos avaliados fazem classificação. R², MAE e RMSE de regressão não se aplicam. O score de '
  'risco de 0 a 100 é derivado de probabilidades e regras, sem avaliação de regressão registrada.',
  'All evaluated models perform classification. Regression R², MAE and RMSE do not apply. The 0–100 risk '
  'score is derived from probabilities and rules, with no recorded regression evaluation.',
  'Todos los modelos evaluados hacen clasificación. R², MAE y RMSE de regresión no aplican. El score de '
  'riesgo de 0 a 100 deriva de probabilidades y reglas, sin evaluación de regresión registrada.'),
 ('Métricas indisponíveis: {arquivo}',
  'Metrics unavailable: {arquivo}',
  'Métricas no disponibles: {arquivo}'),
 ('Limites desta avaliação', 'Evaluation limitations', 'Límites de esta evaluación'),
 ('O risco foi avaliado em dados sintéticos. O conjunto de teste também orientou a decisão de calibração; '
  'não é uma validação externa independente. O artefato final foi retreinado com todos os dados: as métricas '
  'exibidas são as registradas antes desse retreino.',
  'Risk was evaluated on synthetic data. The test set also informed the calibration decision; this is not '
  'independent external validation. The final artifact was refitted on all data: displayed metrics were '
  'recorded before that refit.',
  'El riesgo se evaluó con datos sintéticos. El conjunto de prueba también orientó la calibración; no es '
  'validación externa independiente. El artefacto final se reentrenó con todos los datos: las métricas '
  'mostradas se registraron antes de ese reentrenamiento.'),
 ('Não há medições registradas de latência, memória ou desempenho em produção para comparar os modelos.',
  'No recorded latency, memory or production performance measurements are available to compare models.',
  'No hay mediciones registradas de latencia, memoria ni rendimiento en producción para comparar modelos.'),
 ('Como interpretar as métricas', 'How to interpret the metrics', 'Cómo interpretar las métricas'),
 ('Acurácia: fração total de acertos. Acurácia balanceada: média do recall das classes. F1 macro: média do '
  'equilíbrio entre precisão e recall de cada classe, com o mesmo peso para todas.',
  'Accuracy: overall fraction of correct predictions. Balanced accuracy: mean class recall. Macro F1: mean '
  'balance of precision and recall for each class, giving every class equal weight.',
  'Exactitud: fracción total de aciertos. Exactitud balanceada: media del recall de las clases. F1 macro: '
  'media del equilibrio entre precisión y recall de cada clase, con igual peso para todas.'),
 ('Precisão: entre as previsões de uma classe, quantas estavam corretas. Recall: entre os casos reais '
  'daquela classe, quantos foram encontrados. Recall de ALTO evita deixar passar situações de risco elevado.',
  'Precision: how many predictions of a class were correct. Recall: how many actual cases of that class were '
  'found. HIGH recall helps avoid missing high-risk situations.',
  'Precisión: cuántas predicciones de una clase fueron correctas. Recall: cuántos casos reales de esa clase '
  'se encontraron. El recall ALTO ayuda a no omitir situaciones de riesgo elevado.'),
 ('Melhor significa melhor segundo o critério e a base avaliados. Diferenças pequenas exigem análise de '
  'incerteza e validação com dados reais antes de concluir superioridade em produção.',
  'Best means best under the evaluated criterion and dataset. Small differences require uncertainty analysis '
  'and real-data validation before concluding superiority in production.',
  'Mejor significa mejor según el criterio y la base evaluados. Las diferencias pequeñas exigen analizar la '
  'incertidumbre y validar con datos reales antes de concluir superioridad en producción.')]
