# Evidência — validação da integração com as fontes de dados

> Gerado por `scripts/validar_integracao.py` em 05/11/2026 15:10 · modelo v2.0 (`f7d7d1b30efb`) · 100 leituras simuladas · 6s · banco SQLite temporário (o banco real não é alterado).

**Resultado: todas as verificações passaram.**

## Verificações

| Grupo | Verificação | Esperado | Obtido | Resultado |
|---|---|---|---|---|
| A. Fonte real | Consulta à Open-Meteo | resposta válida | pulada (--sem-rede) | ⚠️ AVISO |
| B. Falha da fonte | timeout | ok=False, sem exceção, fallback manual | ok=False, erro registrado (tempo esgotado) | ✅ OK |
| B. Falha da fonte | sem conexão | ok=False, sem exceção, fallback manual | ok=False, erro registrado (sem rede) | ✅ OK |
| B. Falha da fonte | HTTP 500 | ok=False, sem exceção, fallback manual | ok=False, erro registrado (HTTP 500) | ✅ OK |
| B. Falha da fonte | JSON inválido | ok=False, sem exceção, fallback manual | ok=False, erro registrado (JSON inválido) | ✅ OK |
| B. Falha da fonte | resposta incompleta | ok=False, sem exceção, fallback manual | ok=False, erro registrado ('temperature_2m') | ✅ OK |
| C. GPS | Velocidade calculada em trajeto a 12 km/h | erro ≤ 0,5 km/h nas leituras válidas | 27 leituras, erro máximo 0.00 km/h | ✅ OK |
| C. GPS | Salto de sinal (≈2000 km/h) | descartado, cai para manual | 2 leitura(s) descartada(s) | ✅ OK |
| C. GPS | Velocidade do chip GPS (3,5 m/s) | 12,6 km/h, origem gps_chip | (12.6, 'gps_chip') | ✅ OK |
| D. Lote simulado | Conservação: enviadas = gravadas + rejeitadas | nenhuma leitura perdida | 103 enviadas = 95 gravadas + 5 inválidas + 3 duplicadas + 0 erros | ✅ OK |
| D. Lote simulado | Toda rejeição fica registrada com motivo | 5 inválidas + 3 duplicadas em `rejeicoes` | {'DUPLICADA': 3, 'INVALIDA': 5} | ✅ OK |
| D. Lote simulado | Toda leitura gravada tem exatamente uma predição | 0 sem predição | 95 predições para 95 leituras; 0 não processadas | ✅ OK |
| D. Lote simulado | Valores gravados = valores enviados (ida e volta) | 0 divergências | 0 divergências em 95 leituras × 8 campos | ✅ OK |
| D. Lote simulado | Hash SHA-256 de integridade confere | 100% | 95/95 conferem | ✅ OK |
| D. Lote simulado | Score gravado = risco esperado recalculado das probabilidades | 0 divergências | 0 divergências | ✅ OK |
| D. Lote simulado | Alerta emitido para todo MÉDIO/ALTO e nunca para BAIXO | 0 inconsistências | 33 alertas esperados, 0 inconsistências | ✅ OK |
| D. Lote simulado | Reavaliar a mesma entrada gera o mesmo score (reprodutível) | 0 divergências | 0 em 50 reavaliações | ✅ OK |
| E. Corrupção | Leitura alterada no banco depois de gravada | recusada, marcada como ERRO | status ERRO: integridade violada: a leitura foi alterada depois de gravada | ✅ OK |
| F. Oracle | Mesmo score, classe e versão nas duas persistências | 0 divergências | 0 em 95 predições | ✅ OK |

## A. Clima real consultado (Open-Meteo)

_Consulta real não executada ou indisponível._

## D. Lote de telemetria simulada

- Leituras enviadas: **103** (≈5% com problema injetado e ≈3% retransmitidas)
- Gravadas e avaliadas: **95** · rejeitadas por validação: **5** · rejeitadas como duplicata: **3**
- Distribuição das classes gravadas: {'BAIXO': 62, 'MEDIO': 27, 'ALTO': 6}

## Como reproduzir

```bash
python scripts/validar_integracao.py --leituras 100
```
