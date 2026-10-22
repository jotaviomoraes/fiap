# 📋 User Stories — Sompo AgroPredict

> Documento formal das User Stories da solução, incorporando o feedback da Sprint 1. Ao final, a rastreabilidade de cada critério de aceite no MVP entregue na Sprint 4.
> Formato: **Como [persona] / Quero [funcionalidade] / Para [valor]**, com critérios de aceite no padrão **Dado / Quando / Então**.

---

## US-01 — Operador de Campo: alerta preventivo em tempo real

**Como** operador de equipamento agrícola
**Quero** receber alertas em tempo real sobre o nível de risco da operação atual
**Para** evitar incidentes (atolamento, tombamento, falha mecânica) sem comprometer a produtividade da janela de safra

### Contexto

O operador toma decisões em segundos durante a operação. Não pode ficar com olho preso na tela do celular — precisa de uma interface de **baixa carga cognitiva**, com sinalização visual e sonora simples.

### Critérios de aceite

**CA-01.1 — Operação em condições seguras**
> **DADO** que o operador está conduzindo o equipamento com `umidade_solo < 50%`, `declividade < 10%` e `velocidade < 15 km/h`
> **QUANDO** o modelo avalia a operação atual
> **ENTÃO** o aplicativo exibe o status **🟢 BAIXO** com a recomendação *"Seguir rota atual"*
> **E** nenhum alerta sonoro é emitido

**CA-01.2 — Mudança para risco médio**
> **DADO** que o operador está em uma operação com risco BAIXO
> **QUANDO** as condições mudam e o score sobe para a faixa MÉDIO (25–49)
> **ENTÃO** o aplicativo exibe o status **🟡 MÉDIO** com recomendação contextual (ex: *"Reduzir velocidade"*, *"Atenção à inclinação"*)
> **E** emite alerta sonoro **único e curto** (não-disruptivo)
> **E** registra a transição na tabela `predicoes` do banco com `classe_risco='MEDIO'`

**CA-01.3 — Risco alto detectado**
> **DADO** que o operador está em condições críticas (ex: `umidade_solo > 80%` + `chuva_24h > 40mm`)
> **QUANDO** o modelo classifica como ALTO (score ≥ 50)
> **ENTÃO** o aplicativo exibe **🔴 ALTO** em tela cheia com instrução clara (*"INTERROMPER OPERAÇÃO"*)
> **E** dispara alerta sonoro contínuo + vibração
> **E** registra o evento em `predicoes` **e** cria entrada em `alertas` (com `acao_tomada = 'PENDENTE'`)
> **E** exibe a causa principal do risco (ex: *"Solo saturado + chuva nas últimas 24h"*)

**CA-01.4 — Justificativa interpretável**
> **DADO** que um alerta foi emitido
> **QUANDO** o operador toca em "Por quê?"
> **ENTÃO** o sistema mostra as **3 variáveis de maior peso** na decisão (via feature importance do Random Forest)

---

## US-02 — Gestor de Frota: visão tática diária da operação

**Como** gestor de frota / gerente agrícola
**Quero** visualizar o score de risco por equipamento e por talhão em um dashboard consolidado
**Para** planejar a alocação de máquinas no dia, realocar operações em áreas críticas e cumprir a janela climática sem comprometer equipamentos

### Contexto

O gestor acompanha de 5 a 50 máquinas em paralelo. Não pode olhar alerta por alerta — precisa de uma **visão agregada**, com filtros, ranking e capacidade de drilldown nos pontos críticos.

### Critérios de aceite

**CA-02.1 — Visão geral do dia**
> **DADO** que o gestor acessa o dashboard
> **QUANDO** a página carrega
> **ENTÃO** exibe um resumo do dia atual com: total de operações monitoradas, distribuição por classe de risco (BAIXO / MÉDIO / ALTO), score médio e score máximo
> **E** os dados vêm da view `vw_metricas_diarias` do Oracle

**CA-02.2 — Ranking de equipamentos por risco**
> **DADO** que existem predições registradas nas últimas 24h
> **QUANDO** o gestor solicita o ranking
> **ENTÃO** o dashboard lista os equipamentos ordenados por **score médio descrescente**, mostrando: modelo, fabricante, total de operações, score médio e quantidade de alertas ALTO

**CA-02.3 — Drilldown em equipamento crítico**
> **DADO** que um equipamento aparece com score elevado no ranking
> **QUANDO** o gestor clica nesse equipamento
> **ENTÃO** o dashboard exibe o histórico detalhado das últimas predições daquele equipamento, com data/hora, condições ambientais, score e recomendação emitida
> **E** permite identificar padrões temporais (ex: risco sobe sempre no fim da tarde)

**CA-02.4 — Identificação de fatores de risco predominantes**
> **DADO** que o gestor quer entender o que mais causa risco na operação
> **QUANDO** acessa a visão de "Fatores de risco"
> **ENTÃO** o dashboard mostra a contagem de predições MÉDIO/ALTO agrupada por cenário (solo saturado + chuva, velocidade alta em terreno inclinado, máquina antiga em uso intenso, etc.)
> **E** isso ajuda a decidir manutenção preventiva ou ajustes de rota

---

## US-03 — Analista da Sompo: portfolio risk e bonificação por comportamento

**Como** analista de risco / atuária da Sompo
**Quero** acessar relatórios consolidados de comportamento preventivo por produtor segurado
**Para** precificar apólices com justiça, oferecer bonificações por comportamento e reduzir a sinistralidade da carteira

### Contexto

A Sompo precisa transformar o seguro de **reativo** (paga sinistro) em **preventivo** (precifica com base em comportamento real). Esse relatório alimenta tanto o modelo de bonificação na renovação quanto a análise forense de sinistros.

### Critérios de aceite

**CA-03.1 — Taxa de aderência por operador**
> **DADO** que um produtor segurado tem operadores cadastrados em `operadores`
> **QUANDO** o analista consulta o relatório de comportamento
> **ENTÃO** o sistema exibe, **para cada operador**: total de alertas recebidos, quantos foram respeitados, quantos foram ignorados e a **taxa de aderência em %** (respeitou / total)
> **E** a query subjacente é a que está em `sql/consultas.sql` item 4

**CA-03.2 — Score consolidado do produtor**
> **DADO** que um produtor tem 30+ predições registradas no histórico
> **QUANDO** o analista calcula o score de comportamento preventivo
> **ENTÃO** o sistema retorna um score de 0–100 baseado em:
> - Taxa de aderência aos alertas (peso 50%)
> - Proporção de operações em risco BAIXO (peso 30%)
> - Tendência ao longo do tempo (peso 20%)
> **E** classifica em faixas: **Excelente (≥80) / Bom (60–79) / Atenção (40–59) / Crítico (<40)**

**CA-03.3 — Análise forense de sinistro**
> **DADO** que um sinistro foi reportado em data/hora específica para um equipamento
> **QUANDO** a analista filtra `predicoes` por `id_equipamento` e janela temporal (ex: 2h antes do sinistro)
> **ENTÃO** o sistema retorna **todas as predições daquele equipamento nesse intervalo**, incluindo: condições ambientais, classe de risco, recomendação emitida, e se o alerta foi respeitado (via JOIN com `alertas`)
> **E** isso permite avaliar se o sinistro era previsível e se o operador foi alertado

**CA-03.4 — Auditoria do modelo (LGPD / explicabilidade)**
> **DADO** que uma decisão automatizada precisa ser justificada (auditoria ou contestação)
> **QUANDO** a analista consulta uma predição específica pelo `id_predicao`
> **ENTÃO** o sistema retorna: todas as features de entrada, probabilidades de cada classe (`prob_baixo`, `prob_medio`, `prob_alto`), classe predita, score, recomendação e a **versão do modelo** que produziu a decisão (`versao_modelo`)
> **E** isso garante rastreabilidade conforme exigências da LGPD para decisões automatizadas

---

## Rastreabilidade final — User Stories × MVP (Sprint 4)

Cada critério aponta onde está implementado e qual evidência comprova o funcionamento. Os prints estão
em [`../assets/`](../assets/) e as evidências geradas por script em [`evidencias/`](evidencias/).

### US-01 — Operador de campo

| Critério | Situação | Onde está | Evidência |
|---|---|---|---|
| CA-01.1 — Condições seguras | ✅ Implementado | Card 🟢 BAIXO com "Seguir rota atual"; nenhum sinal sonoro para BAIXO (`paginas/operacao.py`) | `test_regras.py`, `test_servico.py` (`test_risco_baixo_nao_gera_alerta`) |
| CA-01.2 — Mudança para MÉDIO | ✅ Implementado | Card 🟡 com recomendação contextual; **um sinal sonoro curto** só na transição para MÉDIO; predição gravada com `classe_risco='MEDIO'` e alerta nível MÉDIO | Print `14_operacao_explicacao.png`; `validacao_integracao.md` (alertas para todo MÉDIO/ALTO) |
| CA-01.3 — Risco ALTO | ✅ Implementado | Card 🔴 em destaque no topo da tela (em vez de tela cheia, para manter a telemetria visível); **sinal repetido + vibração** a cada ciclo em ALTO; predição + alerta `PENDENTE`; causa principal exibida (override com a variável crítica ou explicação do modelo) | `test_servico.py` (`test_risco_alto_gera_alerta_pendente`); `ui_comum.emitir_sinal` |
| CA-01.4 — "Por quê?" | ✅ Implementado (evoluído) | Expansor **"Por que esse risco?"** com as **3 variáveis de maior impacto nesta leitura** (explicação local do modelo), além da importância global | Print `14_operacao_explicacao.png`; `test_modelo.py` (`test_explicacao_aponta_as_variaveis_de_risco`) |

### US-02 — Gestor de frota

| Critério | Situação | Onde está | Evidência |
|---|---|---|---|
| CA-02.1 — Visão geral | ✅ Implementado | Página **Frota e tendências**: operações, distribuição por classe, score médio e máximo, alertas pendentes, com filtros de período, região e tipo de operação. Fonte: `vw_predicoes` do SQLite (a `vw_metricas_diarias` do Oracle continua disponível na réplica opcional) | Print `15_frota_ranking.png`; `test_relatorios.py` (`test_resumo_e_ranking`) |
| CA-02.2 — Ranking de equipamentos | ✅ Implementado | Ranking por score médio decrescente com modelo, fabricante, região, operações, score máximo, quantidade de ALTO e alertas pendentes | Print `15_frota_ranking.png`; `test_relatorios.py` (`test_resumo_e_ranking`) |
| CA-02.3 — Drilldown | ✅ Implementado | Seleção do equipamento → série do score, **score médio por hora do dia** (padrões temporais) e histórico detalhado | Print `15_frota_ranking.png` (drilldown e score por hora) |
| CA-02.4 — Fatores de risco | ✅ Implementado | Aba **Fatores de risco**: cenários (recomendação emitida) e variáveis acima do limiar nas predições MÉDIO/ALTO; tendências por região, tipo de operação e equipamento | Prints `16_frota_tendencias.png` e `17_frota_fatores.png`; `test_relatorios.py` (`test_tendencia_por_regiao_e_por_tipo_de_operacao`) |

### US-03 — Analista Sompo

| Critério | Situação | Onde está | Evidência |
|---|---|---|---|
| CA-03.1 — Aderência por operador | ✅ Implementado | Alertas recebidos, respeitados, ignorados, pendentes e taxa de aderência (respeitados ÷ respondidos) — `Relatorios.aderencia_operadores` (equivalente SQLite do item 4 de `sql/consultas.sql`) | `test_relatorios.py` (`test_alertas_do_operador_e_aderencia`) |
| CA-03.2 — Score do produtor | ✅ Implementado | Por fazenda: 50% aderência + 30% operações BAIXO + 20% tendência (1ª × 2ª metade do período); faixas Excelente/Bom/Atenção/Crítico; exige 30+ predições | Print `20_auditoria_comportamento.png`; `test_relatorios.py` (`test_comportamento_preventivo_do_produtor`) |
| CA-03.3 — Análise forense | ✅ Implementado | Equipamento + data/hora do sinistro + janela → todas as predições, condições, recomendação e se o alerta foi respeitado | `test_relatorios.py` (`test_forense_e_auditoria`) |
| CA-03.4 — Auditoria (LGPD) | ✅ Implementado | Por `id_predicao`: entradas com a fonte de cada dado, probabilidades, classe do modelo e final, override, explicação local, recomendação, versão **e hash** do modelo e conferência do hash de integridade da leitura | Print `21_auditoria_predicao.png`; `validacao_integracao.md` (grupos D e E) |

### Requisitos transversais da Sprint 4

| Requisito do briefing | Onde está | Evidência |
|---|---|---|
| Código modular, exceções tratadas, fluxo estável | Camada `src/agropredict`; validação de entrada; `ErroProcessamento`; fallback manual de GPS/clima | 78 testes em `resultado_testes.txt` |
| Tratamento de inconsistências, faltantes e duplicidades | `qualidade.py` (treino); validação + rejeição de duplicatas (produção) | `relatorio_modelo.md` §1; `test_qualidade.py` |
| Ajuste final do modelo com métricas justificadas | `treinar_modelo.py` | `relatorio_modelo.md` |
| Integração consistente, sem perda ou corrupção | `validar_integracao.py` | `validacao_integracao.md` |
| Proteção de dados, controle de acesso, registros de uso | `seguranca.py`, `integridade.py`, `rejeicoes`, `log_acessos`, log da aplicação | Print `22_qualidade_coleta.png`; `test_seguranca.py` |
| Tendências por equipamento, região e tipo de operação | Página Frota; `gerar_relatorio.py` | Prints 15–17; `test_relatorios.py` |
