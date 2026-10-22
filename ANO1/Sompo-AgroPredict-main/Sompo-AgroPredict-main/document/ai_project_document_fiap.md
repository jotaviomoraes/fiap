
<img src="../assets/logo-fiap.png" alt="FIAP - Faculdade de Informática e Admnistração Paulista" border="0" width=30% height=30%>

# AI Project Document — Challenge Sompo × FIAP — Sprint 4 (entrega final)

## Sompo AgroPredict

#### Nomes dos integrantes do grupo

- Renata de Almeida Marinho — RM569342
- Giselli Mayumi Takahashi Yokoyama — RM572690
- David Ribeiro Prado de Lacerda — RM570350
- João Otavio Moraes — RM573227
- Pedro Henrique Lacerda — RM573114

## Sumário

[1. Introdução](#c1)

[2. Visão Geral do Projeto](#c2)

[3. Desenvolvimento do Projeto](#c3)

[4. Resultados e Avaliações](#c4)

[5. Conclusões e Trabalhos Futuros](#c5)

[6. Referências](#c6)

[Anexos](#c7)

<br>

# <a name="c1"></a>1. Introdução

## 1.1. Escopo do Projeto

### 1.1.1. Contexto da Inteligência Artificial

O setor de seguros opera historicamente de forma **reativa**: o risco é precificado na contratação da
apólice e a seguradora só volta a agir quando o sinistro já aconteceu, no momento da indenização.
Aplicações de Inteligência Artificial vêm deslocando esse eixo para a **prevenção** — a chamada
*predictive underwriting* e o *risk engineering* orientado a dados —, em que modelos consomem
telemetria em tempo real para antecipar o evento antes que ele ocorra.

No agronegócio esse deslocamento é especialmente valioso. O Brasil é um dos maiores mercados
agrícolas do mundo e concentra frotas de equipamentos de alto valor unitário (colheitadeiras,
tratores, pulverizadores) operando em condições ambientais adversas e variáveis. Incidentes como
atolamento, tombamento em declive e falha mecânica por desgaste geram sinistros caros e paradas de
operação em janelas de safra curtas, nas quais cada hora parada tem custo direto para o produtor.

A abrangência da aplicação é **nacional**, com potencial de replicação regional (América Latina), e o
segmento de atuação é a intersecção entre **seguros patrimoniais/agrícolas** e **gestão de frotas
agrícolas**. As atividades executadas pelo sistema são coleta de telemetria, classificação de risco
operacional, emissão de alertas e recomendações preventivas e relatórios de comportamento para a
seguradora.

### 1.1.2. Descrição da Solução Desenvolvida

O **Sompo AgroPredict** é uma plataforma de monitoramento preventivo de risco operacional para
equipamentos agrícolas. A proposta de valor é direta: **em vez de pagar o sinistro depois, calcular
o risco antes**.

A solução captura variáveis ambientais (umidade do solo, chuva acumulada em 24h, temperatura,
declividade) e operacionais (velocidade, idade da máquina, horas de operação, tipo de operação),
classifica o risco da operação corrente em três níveis — **BAIXO, MÉDIO e ALTO** — e devolve, junto
com um score de 0 a 100, uma **recomendação contextual acionável** e a **explicação** das variáveis
que mais pesaram na decisão.

Uma decisão de projeto central orienta toda a arquitetura: **todas as variáveis são captáveis por
fontes externas à máquina** — o celular do operador, uma API pública de clima e o cadastro do
equipamento. Isso viabiliza a adoção em **frotas legadas**, que representam a maior parte do parque
brasileiro e não possuem telemetria proprietária embarcada.

Na entrega final, a solução é um **MVP consolidado e validado**: o fluxo entrada → banco → modelo →
saída roda em uma camada de serviço independente da interface, cada leitura é validada e protegida
por hash de integridade, o modelo foi retreinado e selecionado por critério explícito, e cada perfil
de usuário tem a sua visão no dashboard.

# <a name="c2"></a>2. Visão Geral do Projeto

## 2.1. Objetivos do Projeto

O objetivo geral é **transformar a gestão de risco agrícola de reativa em preventiva**, reduzindo a
sinistralidade nas operações e no transporte de equipamentos.

Objetivos específicos da Sprint 4, focada em **consolidação e confiabilidade**:

| # | Objetivo do briefing | Como foi atendido |
|---|---|---|
| 1 | **Refinamento do sistema** — arquitetura organizada, funções padronizadas, módulos, exceções tratadas, fluxo estável e reproduzível | Camada de serviço `src/agropredict` com módulos de responsabilidade única; validação de entrada; erros de processamento marcados no banco; pipeline de ponta a ponta com um comando e sementes fixas |
| 2 | **Refinamento de dados e modelo** — acesso ao banco, variáveis revisadas, inconsistências tratadas, previsões melhores | Migrações versionadas do banco; pipeline de qualidade sobre dataset bruto; comparação de 3 algoritmos; revisão de variáveis; F1 macro de 92,8% → 97,6% no mesmo teste |
| 3 | **Validação da integração** — entradas reais ou simuladas, coleta confiável, informações consistentes | Script de validação com clima real, falhas simuladas da API, GPS simulado, lote com problemas injetados, detecção de corrupção e consistência com o Oracle — 21 de 21 verificações OK |
| 4 | **Segurança e rastreabilidade** — proteção de dados, controle de acesso, integridade, registros de uso | Perfis de acesso, senha em hash, bloqueio, hash SHA-256 por leitura, registro de entradas recusadas, versão e hash do modelo e explicação em cada predição, log de acessos e da aplicação |
| 5 | **Entrega de valor** — relatórios e tendências por equipamento, região e tipo de operação, alertas e recomendações claros | Páginas por perfil, critérios de alerta explícitos, alerta sonoro e vibração, score de comportamento do produtor, exportação CSV e relatório consolidado |

## 2.2. Público-Alvo

A solução foi desenhada para as personas formalizadas como User Stories em
[`user_stories.md`](user_stories.md), mais o técnico de manutenção citado no briefing final:

| Persona | Necessidade | Como a solução atende |
|---|---|---|
| **Operador de campo** (US-01) | Decidir em segundos, sem tirar o olho da operação | Card de risco colorido, uma recomendação direta, explicação em 3 linhas, sinal sonoro e vibração, resposta ao alerta com um toque |
| **Gestor de frota** (US-02) | Enxergar onde está o risco na frota | Resumo do período, ranking de equipamentos, drilldown com padrão por hora, tendências por região e tipo de operação, fatores de risco |
| **Técnico de manutenção** | Priorizar máquinas com sinais de desgaste | Prioridade de manutenção por equipamento a partir dos alertas de categoria mecânica |
| **Analista da seguradora** (US-03) | Precificar com justiça e analisar sinistros | Aderência aos alertas, score de comportamento por produtor, análise forense e auditoria completa de cada decisão automatizada |

## 2.3. Metodologia

O projeto foi desenvolvido de forma **incremental ao longo de quatro sprints**, cada uma entregando um
artefato funcional que a seguinte integra ou refina:

| Sprint | Foco | Entregas |
|---|---|---|
| **Sprint 1** | Estrutura e proposta (sem código) | Definição do problema, personas, 5 variáveis com tabela ilustrativa, modelo proposto, arquitetura, diretrizes de segurança, mockups |
| **Sprint 2** | Modelo preditivo | Dataset com 8 variáveis e 1000 linhas, Random Forest treinado e validado, schema Oracle, dashboard, User Stories formalizadas |
| **Sprint 3** | Integração ponta a ponta | Telemetria real (GPS + Open-Meteo), persistência no SQLite, fluxo completo entrada → banco → modelo → saída |
| **Correções 3.1** | Feedback da Sprint 3 | Camada de serviço, leitura gravada antes do modelo, score único entre bancos, auditoria no SQLite, perfis de acesso, visão de frota |
| **Sprint 4** | **Consolidação e validação** | Pipeline de qualidade, modelo final v2.0, integridade e rastreabilidade das entradas, relatórios e alertas completos, validação automatizada e evidências |

As etapas seguidas na Sprint 4 foram:

1. **Diagnóstico** — comparação do estado do repositório com cada requisito do briefing e com o
   feedback da Sprint 3
2. **Dados e modelo** — dataset bruto com problemas reais de coleta, pipeline de qualidade e treino
   reproduzível com seleção por critério explícito
3. **Confiabilidade do fluxo** — hash de integridade, rejeição rastreável, migrações do banco e testes
   de cada caminho de erro
4. **Validação da integração** — script que prova, com fonte real e simulada, que nenhum dado se perde
   ou corrompe
5. **Entrega de valor** — explicação local, alerta sonoro, relatórios por perfil e exportação
6. **Evidências e documentação** — pipeline de um comando que regenera testes, validação e relatório;
   README final e rastreabilidade das User Stories

# <a name="c3"></a>3. Desenvolvimento do Projeto

## 3.1. Tecnologias Utilizadas

| Camada | Tecnologia | Papel no projeto |
|---|---|---|
| **Linguagem** | Python 3.10+ | Camada de serviço, scripts e interface |
| **Machine Learning** | scikit-learn, joblib | Pipeline com imputação, `HistGradientBoostingClassifier`, `GridSearchCV`, importância por permutação, calibração avaliada |
| **Manipulação de dados** | pandas, numpy | Pipeline de qualidade, geração do dataset, relatórios |
| **Interface** | Streamlit | Dashboard com navegação por perfil, exportação CSV e componente de alerta sonoro |
| **Telemetria** | streamlit-js-eval, streamlit-autorefresh | Geolocalização do navegador e ciclo de atualização de 10 s |
| **Fonte externa** | API Open-Meteo (via `requests`) | Temperatura, chuva 24h e aproximação de umidade do solo — gratuita, sem API key |
| **Banco principal** | SQLite (`sqlite3`) | Leituras, predições, alertas, rejeições, usuários e logs, com migrações versionadas |
| **Réplica opcional** | Oracle XE 21c (`oracledb`) | Mesmo resultado gravado em um banco central |
| **Segurança** | `hashlib` (PBKDF2, SHA-256), `hmac`, `secrets` | Senhas em hash, integridade das leituras, comparação em tempo constante |
| **Testes** | `unittest`, `unittest.mock` | 78 testes, incluindo respostas simuladas da API de clima |
| **Visualização** | matplotlib | Gráficos de avaliação do modelo gerados pelo treino |

### Organização do código

| Módulo | Responsabilidade |
|---|---|
| `agropredict/entrada.py` | Contrato da leitura e validação (faixas físicas, tipos, categorias) |
| `agropredict/qualidade.py` | Pipeline de qualidade do dataset de treino |
| `agropredict/regras.py` | Limiares, override, score de risco esperado, recomendação e critério de alerta |
| `agropredict/modelo.py` | Carrega modelo e metadados; probabilidades e explicação local em uma chamada |
| `agropredict/avaliacao.py` | Fonte única da decisão (modelo + regras) para todos os consumidores |
| `agropredict/integridade.py` | Hash SHA-256 das leituras |
| `agropredict/persistencia.py` | Repositório SQLite, transações e migrações |
| `agropredict/servico.py` | Orquestrador: validação → banco → integridade → modelo → saída; duplicatas e rejeições |
| `agropredict/relatorios.py` | Consultas por equipamento, região, tipo de operação, alertas, aderência, comportamento, manutenção, auditoria e qualidade da coleta |
| `agropredict/seguranca.py` | Hash de senha, bloqueio por tentativas e perfis de acesso |
| `agropredict/telemetria.py`, `clima.py` | Velocidade por GPS e integração com a Open-Meteo, com descarte de leituras incoerentes |
| `agropredict/oracle.py` | Réplica opcional com o mesmo resultado |
| `dashboard/` | Interface: login, menu por perfil e cinco páginas |
| `modelo/treinar_modelo.py` | Treino reproduzível, relatório e gráficos |
| `scripts/` | Pipeline de ponta a ponta, simulador, validação, relatório e usuários |

O tratamento de exceções segue o princípio de **degradação graciosa com registro**: uma falha na API
de clima, no GPS ou no Oracle não derruba a aplicação; uma entrada inválida é recusada com o motivo
gravado; uma falha de processamento marca a leitura como `ERRO` em vez de sumir.

## 3.2. Modelagem e Algoritmos

### Algoritmo final: Gradient Boosting (`HistGradientBoostingClassifier`)

O algoritmo foi **escolhido por evidência**, não por preferência. Três candidatos — Regressão
Logística (baseline), Random Forest (modelo das Sprints 2 e 3) e Gradient Boosting — tiveram os
hiperparâmetros ajustados por `GridSearchCV` com validação cruzada estratificada de 5 folds, e a
escolha seguiu um critério declarado antes do treino:

> Entre os candidatos com **recall de ALTO ≥ 95%** na validação cruzada, vence o de **maior F1 macro**.

O critério reflete o domínio: um falso negativo de ALTO significa deixar de alertar uma situação
perigosa — o erro mais caro para o operador e para a seguradora. O F1 macro garante que as três
classes, inclusive MÉDIO, tenham desempenho equilibrado.

| Algoritmo | Hiperparâmetros escolhidos | F1 macro (CV) | Recall ALTO (CV) |
|---|---|---:|---:|
| Regressão Logística | `C=10`, `class_weight="balanced"` | 87,2% | 85,9% |
| Random Forest | `max_depth=16`, `min_samples_leaf=1`, 300 árvores | 92,9% | 97,0% |
| **Gradient Boosting** | `learning_rate=0.05`, `max_iter=300`, `class_weight="balanced"` | **96,1%** | **97,7%** |

### Revisão de variáveis e calibração

- **Ablação de `status_operacao`:** F1 macro 96,05% com a variável e 96,21% sem ela. Como a regra era
  remover variáveis cuja retirada custe menos de 0,5 ponto de F1, a variável saiu do modelo — ela
  continua coletada e usada nos relatórios por tipo de operação.
- **Importância por permutação** no teste: declividade, umidade do solo, velocidade, temperatura,
  chuva 24h, horas de operação e idade da máquina.
- **Calibração isotônica avaliada:** reduziu o log loss (0,095 → 0,083) mas piorou o Brier
  (0,0098 → 0,0137) e o F1. A regra exigia melhora nas duas medidas de probabilidade; com evidência
  mista, ficou o modelo mais simples.

### Camada de regras de domínio

Sobre a saída do modelo há uma camada determinística de segurança: se **qualquer** variável cruza um
limite crítico absoluto (`umidade_solo ≥ 45`, `declividade ≥ 25`, `chuva_24h ≥ 40`,
`temperatura ≥ 45`, `velocidade ≥ 20`), a classe é forçada para **ALTO** e o score para 100,
independentemente da predição estatística, e o motivo é exibido e gravado.

O **score** é o risco esperado, `0·P(BAIXO) + 50·P(MÉDIO) + 100·P(ALTO)` — não a confiança do modelo
na classe prevista. Essa definição vive em uma única função usada por todos os consumidores.

### Explicação local

Para cada predição, o valor de cada variável é trocado pelo valor típico de uma operação segura
(mediana das operações BAIXO no treino) e mede-se quanto o score cai. As três variáveis de maior
impacto são mostradas ao operador e gravadas para auditoria. Todas as variações são avaliadas em uma
única chamada ao modelo, sem custo perceptível no ciclo de 10 segundos.

## 3.3. Treinamento e Teste

### Conjunto de dados

O dataset de treino da Sprint 4 (`src/data/dataset_v3_bruto.csv`) é **simulado** e tem 3000 linhas
geradas pela mesma lógica de cenários e rotulagem da Sprint 2, às quais foram **injetados problemas
reais de coleta**: faltantes, números com vírgula decimal, textos inválidos, picos de sensor,
grafias inconsistentes, linhas sem rótulo, retransmissões e duplicatas conflitantes — 3072 linhas
brutas no total.

O pipeline de qualidade (`qualidade.py`) trata cada problema com uma regra declarada e produz um
relatório de quantos registros foram afetados. Resultado: **2958 linhas aptas** (ALTO 1272, BAIXO
1125, MÉDIO 561). Os faltantes restantes são imputados pela mediana **dentro do pipeline do modelo**,
ajustada apenas no treino, para evitar vazamento de informação do teste.

### Protocolo de avaliação

- Split estratificado **75/25** (2218 treino / 740 teste), semente fixa
- Ajuste de hiperparâmetros e seleção **só no treino**, com validação cruzada estratificada de 5 folds
- Métricas: **recall de ALTO** (segurança), **F1 macro** (equilíbrio entre classes), acurácia,
  precisão por classe, log loss e Brier (qualidade das probabilidades, que formam o score)
- Comparação com o **modelo anterior (v1.0)** no mesmo conjunto de teste
- O modelo final é reajustado com todas as linhas limpas depois da avaliação

Todo o processo está em `src/modelo/treinar_modelo.py`; rodar de novo reproduz as mesmas métricas.

# <a name="c4"></a>4. Resultados e Avaliações

## 4.1. Análise dos Resultados

### Métricas do modelo final (conjunto de teste, n = 740)

| Métrica | v1.0 — Random Forest (Sprint 2/3) | **v2.0 — Gradient Boosting (Sprint 4)** |
|---|---:|---:|
| Acurácia | 94,2% | **98,1%** |
| F1 macro | 92,8% | **97,6%** |
| Recall ALTO | 95,6% | **99,1%** |
| Recall MÉDIO | 90,0% | **96,4%** |
| Log loss | 0,195 | **0,095** |
| ALTO previsto como BAIXO | 0 | **0** |

Na validação cruzada, o modelo final obteve F1 macro de 96,2% (±0,9%) e recall de ALTO de 97,7%
(±0,4%) — próximos do teste, sem sinal de *overfitting*.

### Matriz de confusão (teste)

```
              Predito
Real      BAIXO  MEDIO  ALTO
BAIXO     [276     6     0]
MEDIO     [  1   135     4]
ALTO      [  0     3   315]
```

- **Nenhuma confusão entre os extremos** (BAIXO ↔ ALTO = 0): os erros restantes acontecem apenas
  entre classes vizinhas.
- **Recall de ALTO = 99,1%** (315/318): apenas 3 situações ALTO foram classificadas como MÉDIO, e
  ainda assim geram alerta.
- A classe **MÉDIO**, a mais difícil por ser fronteiriça, passou de 90,0% para 96,4% de recall.

### Validação do sistema integrado

| Evidência | Resultado |
|---|---|
| Testes automatizados | 78 passando |
| Fonte real (Open-Meteo em 3 regiões) | Respostas válidas em ~0,6 s, gravadas sem alteração e avaliadas |
| Falhas da fonte (timeout, HTTP 500, JSON inválido etc.) | Todas tratadas sem exceção, com fallback manual |
| Lote de 514 leituras com problemas injetados | 481 gravadas + 19 inválidas + 14 duplicadas = 514; nenhuma perdida, todas as rejeições registradas |
| Integridade | 100% dos hashes conferem; leitura alterada no banco é recusada |
| Consistência | Score gravado = risco esperado recalculado; mesmo resultado no SQLite e no Oracle |

### Diferença entre o resultado esperado e o real

As métricas continuam calculadas sobre dados **simulados**, cujos rótulos seguem regras de domínio —
o modelo aprende essas regras muito bem. O ganho da Sprint 4 vem de três fontes verificáveis: mais
dados, algoritmo mais adequado ao problema e retirada de uma variável sem sinal. A validação contra
sinistros reais confirmados continua sendo o passo seguinte e impõe cautela na leitura desses
números.

## 4.2. Feedback dos Usuários

O feedback recebido ao longo das sprints orientou decisões concretas:

- **Sprint 1** — User Stories "apenas implícitas dentro das personas" e dataset a ampliar em variáveis →
  na Sprint 2, três User Stories formalizadas em Dado/Quando/Então e dataset com 8 variáveis e 1000
  linhas; na Sprint 4, 3000 linhas com pipeline de qualidade e rastreabilidade de cada critério.
- **Sprint 3** — a tutoria apontou orquestração presa à tela, banco recebendo só o resultado, scores
  diferentes entre SQLite e Oracle, SQLite sem probabilidades nem versão do modelo, perfil único para
  todas as personas e ausência de visão por equipamento, frota ou região. **Todos os pontos foram
  corrigidos** (versão 0.3.1) antes da Sprint 4, e cada um tem teste automatizado.
- **Operador** — não pode desviar a atenção → card único, recomendação curta, sinal sonoro distinto
  para MÉDIO e ALTO e explicação em três linhas.

# <a name="c5"></a>5. Conclusões e Trabalhos Futuros

## Como a solução atingiu os objetivos

A proposta apresentada ao cliente foi entregue como um **MVP consolidado, integrado e validado**. Uma
leitura percorre hoje todo o caminho sem depender da tela: é coletada (GPS, clima real, cadastro),
validada, gravada com hash, lida do banco, avaliada pelo modelo e pelas regras de domínio, explicada e
gravada com alerta — e cada perfil de usuário vê o que precisa para agir. As três User Stories estão
atendidas nos seus doze critérios de aceite, cada um com evidência.

## Pontos fortes

- **Fluxo confiável e reproduzível**: um comando regenera dados, modelo, testes, validação e relatório
  com as mesmas sementes
- **Nenhum dado some sem registro**: entradas recusadas ficam em `rejeicoes`, falhas ficam como `ERRO`
- **Decisões auditáveis e explicáveis**: probabilidades, versão e hash do modelo, override e
  explicação local em cada predição
- **Modelo escolhido por critério declarado**, com comparação honesta contra o modelo anterior
- **Baixa barreira de adoção**: nenhuma variável exige hardware embarcado
- **Honestidade sobre o alcance**: o projeto distingue o que é real, aproximado e simulado

## Pontos a melhorar

| Ponto | Situação atual |
|---|---|
| **Modelo treinado em dados simulados** | Nenhuma validação contra sinistros reais confirmados |
| **Declividade e umidade do solo** | Declividade manual; umidade aproximada pela Open-Meteo |
| **Banco local** | SQLite na máquina de quem roda o dashboard; o Oracle seria o banco central |
| **Dados pessoais no Oracle** | Campo `cpf` em texto claro no schema opcional (dados fictícios) |
| **Usuário Oracle dedicado** | Falta um usuário de aplicação com *grants* mínimos |
| **Alerta sonoro** | Depende do navegador; vibração só em Android |

## Plano de ações futuras

| Prioridade | Ação | Resultado esperado |
|---|---|---|
| 1 | Coletar rótulos reais (sinistros confirmados) a partir das leituras gravadas e reavaliar o modelo | Substitui a validação sintética por validação de campo |
| 2 | Integrar mapa de declividade por talhão e sensor de solo ou satélite | Elimina a entrada manual e a aproximação das variáveis mais importantes |
| 3 | Implantar o banco central (Oracle ou PostgreSQL) com usuário de aplicação de privilégio mínimo | Visão consolidada de várias fazendas e seguradoras |
| 4 | Aplicativo móvel com notificação nativa | Alerta sonoro e vibração garantidos, inclusive com a tela bloqueada |
| 5 | Pseudonimização de dados pessoais e política de retenção | Conformidade plena com a LGPD |
| 6 | Monitoramento de desvio dos dados (*data drift*) e retreino periódico | Modelo acompanha mudanças de safra, região e frota |

# <a name="c6"></a>6. Referências

- **Open-Meteo API** — documentação da API climática gratuita utilizada: https://open-meteo.com/en/docs
- **scikit-learn** — `HistGradientBoostingClassifier`, `GridSearchCV`, `permutation_importance`,
  `CalibratedClassifierCV`, `Pipeline`/`ColumnTransformer`: https://scikit-learn.org/stable/
- **Streamlit** — documentação oficial do framework de interface: https://docs.streamlit.io/
- **python-oracledb** — driver Oracle para Python: https://python-oracledb.readthedocs.io/
- **MDN Web Docs** — Geolocation API, Web Audio API e Vibration API: https://developer.mozilla.org/
- **OWASP Password Storage Cheat Sheet** — armazenamento de senhas com PBKDF2:
  https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- **LGPD — Lei nº 13.709/2018**, art. 20 (direito à revisão de decisões automatizadas):
  https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm

# <a name="c7"></a>Anexos

## Anexo A — Arquitetura final

O diagrama do fluxo de ponta a ponta (entrada → banco → modelo → saída), incluindo o treino offline,
a integridade e as rejeições, está no [README do projeto](../README.md#-arquitetura-final-ponta-a-ponta).

## Anexo B — Modelo de dados

As tabelas do SQLite e o schema Oracle opcional estão descritos no
[README](../README.md#-engenharia-de-dados); o schema SQLite e as migrações estão em
[`../src/agropredict/persistencia.py`](../src/agropredict/persistencia.py) e o DDL Oracle em
[`../src/sql/schema.sql`](../src/sql/schema.sql).

## Anexo C — User Stories e rastreabilidade

As três User Stories, com os doze critérios de aceite e a rastreabilidade final de cada um, estão em
[`user_stories.md`](user_stories.md).

## Anexo D — Evidências

| Arquivo | Conteúdo |
|---|---|
| [`relatorio_modelo.md`](relatorio_modelo.md) | Qualidade dos dados, comparação de algoritmos, revisão de variáveis, calibração e métricas |
| [`evidencias/validacao_integracao.md`](evidencias/validacao_integracao.md) | 21 verificações da integração com as fontes de dados |
| [`evidencias/resultado_testes.txt`](evidencias/resultado_testes.txt) | Saída dos 78 testes automatizados |
| `../assets/01..06` | Gráficos da análise exploratória e do modelo da Sprint 2 |
| `../assets/07..09` | Prints do dashboard da Sprint 3 |
| `../assets/10..13` | Gráficos de avaliação do modelo final (gerados pelo treino) |
| `../assets/14..22` | Prints do dashboard final, por perfil |
