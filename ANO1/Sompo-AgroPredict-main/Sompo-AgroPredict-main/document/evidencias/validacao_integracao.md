# Evidência — validação da integração com as fontes de dados

> Gerado por `scripts/validar_integracao.py` em 28/09/2026 19:44 · modelo v2.0 (`f7d7d1b30efb`) · 500 leituras simuladas · 29s · banco SQLite temporário (o banco real não é alterado).

**Resultado: todas as verificações passaram.**

## Verificações

| Grupo | Verificação | Esperado | Obtido | Resultado |
|---|---|---|---|---|
| A. Fonte real | Open-Meteo em Sorriso - MT → fluxo completo | campos em faixa física, gravados sem alteração e avaliados | 938 ms · 32.6°C · 0.6 mm · solo 10.6% → predição #1 BAIXO | ✅ OK |
| A. Fonte real | Open-Meteo em Rio Verde - GO → fluxo completo | campos em faixa física, gravados sem alteração e avaliados | 921 ms · 28.4°C · 0.0 mm · solo 13.0% → predição #2 BAIXO | ✅ OK |
| A. Fonte real | Open-Meteo em Cascavel - PR → fluxo completo | campos em faixa física, gravados sem alteração e avaliados | 908 ms · 21.7°C · 1.1 mm · solo 25.6% → predição #3 BAIXO | ✅ OK |
| B. Falha da fonte | timeout | ok=False, sem exceção, fallback manual | ok=False, erro registrado (tempo esgotado) | ✅ OK |
| B. Falha da fonte | sem conexão | ok=False, sem exceção, fallback manual | ok=False, erro registrado (sem rede) | ✅ OK |
| B. Falha da fonte | HTTP 500 | ok=False, sem exceção, fallback manual | ok=False, erro registrado (HTTP 500) | ✅ OK |
| B. Falha da fonte | JSON inválido | ok=False, sem exceção, fallback manual | ok=False, erro registrado (JSON inválido) | ✅ OK |
| B. Falha da fonte | resposta incompleta | ok=False, sem exceção, fallback manual | ok=False, erro registrado ('temperature_2m') | ✅ OK |
| C. GPS | Velocidade calculada em trajeto a 12 km/h | erro ≤ 0,5 km/h nas leituras válidas | 27 leituras, erro máximo 0.00 km/h | ✅ OK |
| C. GPS | Salto de sinal (≈2000 km/h) | descartado, cai para manual | 2 leitura(s) descartada(s) | ✅ OK |
| C. GPS | Velocidade do chip GPS (3,5 m/s) | 12,6 km/h, origem gps_chip | (12.6, 'gps_chip') | ✅ OK |
| D. Lote simulado | Conservação: enviadas = gravadas + rejeitadas | nenhuma leitura perdida | 514 enviadas = 481 gravadas + 19 inválidas + 14 duplicadas + 0 erros | ✅ OK |
| D. Lote simulado | Toda rejeição fica registrada com motivo | 19 inválidas + 14 duplicadas em `rejeicoes` | {'DUPLICADA': 14, 'INVALIDA': 19} | ✅ OK |
| D. Lote simulado | Toda leitura gravada tem exatamente uma predição | 0 sem predição | 481 predições para 481 leituras; 0 não processadas | ✅ OK |
| D. Lote simulado | Valores gravados = valores enviados (ida e volta) | 0 divergências | 0 divergências em 481 leituras × 8 campos | ✅ OK |
| D. Lote simulado | Hash SHA-256 de integridade confere | 100% | 481/481 conferem | ✅ OK |
| D. Lote simulado | Score gravado = risco esperado recalculado das probabilidades | 0 divergências | 0 divergências | ✅ OK |
| D. Lote simulado | Alerta emitido para todo MÉDIO/ALTO e nunca para BAIXO | 0 inconsistências | 117 alertas esperados, 0 inconsistências | ✅ OK |
| D. Lote simulado | Reavaliar a mesma entrada gera o mesmo score (reprodutível) | 0 divergências | 0 em 50 reavaliações | ✅ OK |
| E. Corrupção | Leitura alterada no banco depois de gravada | recusada, marcada como ERRO | status ERRO: integridade violada: a leitura foi alterada depois de gravada | ✅ OK |
| F. Oracle | Mesmo score, classe e versão nas duas persistências | 0 divergências | 0 em 100 predições | ✅ OK |

## A. Clima real consultado (Open-Meteo)

| região | latência (ms) | temperatura (°C) | chuva 24h (mm) | umidade do solo (%) | classe | score |
|---|---:|---:|---:|---:|---|---:|
| Sorriso - MT | 938 | 32.6 | 0.6 | 10.6 | BAIXO | 0 |
| Rio Verde - GO | 921 | 28.4 | 0 | 13 | BAIXO | 0 |
| Cascavel - PR | 908 | 21.7 | 1.1 | 25.6 | BAIXO | 0 |

## D. Lote de telemetria simulada

- Leituras enviadas: **514** (≈5% com problema injetado e ≈3% retransmitidas)
- Gravadas e avaliadas: **481** · rejeitadas por validação: **19** · rejeitadas como duplicata: **14**
- Distribuição das classes gravadas: {'BAIXO': 364, 'MEDIO': 99, 'ALTO': 18}

## Como reproduzir

```bash
python scripts/validar_integracao.py --leituras 500
```
