# Mapeamento da consolidação

Origem de cada arquivo deste repositório nos repositórios das fases anteriores, o que foi alterado e o que ficou de fora.

## Repositórios de origem

| Fase | Repositório |
|---|---|
| 1 | [david-fiap-ai/Farmtech-Solutions-FIAP-Project-CRUD](https://github.com/david-fiap-ai/Farmtech-Solutions-FIAP-Project-CRUD) |
| 2 (cap. 1) | [david-fiap-ai/farmtech-solutions-fase2-cap1](https://github.com/david-fiap-ai/farmtech-solutions-fase2-cap1) |
| 2 (cap. 6) | [david-fiap-ai/farmtech-fase2-cap6](https://github.com/david-fiap-ai/farmtech-fase2-cap6) |
| 3 | [david-fiap-ai/farmtech-solutions-fase3-cap1](https://github.com/david-fiap-ai/farmtech-solutions-fase3-cap1) |
| 4 | [david-fiap-ai/farmtech-fase4-cap1](https://github.com/david-fiap-ai/farmtech-fase4-cap1) |
| 5 | [david-fiap-ai/farmtech-fase5-cap1](https://github.com/david-fiap-ai/farmtech-fase5-cap1) |
| 6 | [dokitodavid/redeneural-fase6-cap1](https://github.com/dokitodavid/redeneural-fase6-cap1) |

## Arquivos trazidos

| Destino | Origem | Alteração |
|---|---|---|
| `src/fase1_gestao_lavoura/gestao_manejo.py` | F1 `farmtech.py` | Renomeado. Carrega `dados_farmtech.csv` ao abrir, para não perder os registros ao salvar |
| `src/fase1_gestao_lavoura/analise_estatistica.R` | F1 `farmtech_estatisticas.r` | Renomeado |
| `src/fase1_gestao_lavoura/dados_farmtech.csv` | F1 `dados_farmtech.csv` | — |
| `src/fase2_irrigacao_iot/esp32/*` (`.ino`, `diagram.json`, `libraries.txt`, `wokwi-project.txt`) | F2c1 `scr/` | Pasta `scr/` corrigida para `esp32/` |
| `src/fase2_irrigacao_iot/openweather_chuva.py` | F2c1 `scr/openweather_chuva.py` | API key lida de `OPENWEATHER_API_KEY` (`.env`) |
| `src/fase2_colheita_cana/{main,colheitas,arquivo}.py` | F2c6 `src/` | — |
| `src/fase2_colheita_cana/banco.py` | F2c6 `src/banco.py` | Credenciais lidas de `ORACLE_USER`, `ORACLE_PASSWORD` e `ORACLE_DSN` (`.env`) |
| `src/fase3_banco_oracle/sensores_agricolas.csv` | F3 `document/sensores_agricolas.csv` | — |
| `src/fase3_banco_oracle/consultas.sql` | F3 `README.md` | **Novo arquivo:** DDL equivalente à importação + as 6 consultas que estavam só no README |
| `src/dashboard/{streamlit_app,farmtech_ml}.py`, `dataset_agricola.csv` | F4 `src/` | Caminho do dataset relativo ao próprio arquivo, para o app rodar da raiz |
| `src/fase3_ml_recomendacao_culturas/recomendacao_culturas.ipynb` + CSV | F3 `document/ml_agronegocio.ipynb` | Renomeado |
| `src/fase5_ml_rendimento_safras/previsao_rendimento_safras.ipynb` + `crop_yield.csv` | F5 `src/` | Renomeado |
| `assets/fase2/circuito_wokwi.png` | F2c1 `assets/` | — |
| `assets/fase2/tabela_colheita.png` | F2c6 `assets/` | — |
| `assets/fase3/01…10_*.jpg` | F3 `assets/print*.jpg` | Renomeados pelo conteúdo |
| `assets/fase5/*.jpg` | F5 `assets/aws/` | — |
| `assets/logo-fiap.png` | modelo [agodoi/templateFiapVfinal](https://github.com/agodoi/templateFiapVfinal) | — |

A lógica dos programas não foi alterada. As únicas mudanças de código são a leitura de credenciais pelo `.env`, o caminho do dataset da dashboard, a carga do CSV na Fase 1 e o tratamento de erros de entrada, de rede e de arquivos inválidos.

## O que ficou de fora e por quê

| Item | Motivo |
|---|---|
| F3 `src/irrigacao.ino` | Idêntico ao `farmtech_fase2.ino` da Fase 2 (duplicata) |
| F6 notebooks, `dataset.zip`, prints e `ai_project_document_fiap.md` | Fora do domínio agrícola do sistema. A configuração de treino foi registrada em `src/fase6_visao_computacional/README.md` |
| READMEs individuais de cada fase | O conteúdo foi consolidado no README integrado da raiz |
| Logos duplicados e `.gitattributes`/`.gitignore` antigos | Substituídos pelos arquivos únicos da raiz |

## Lacunas encontradas na consolidação

- **Fase 3:** só havia SQL manual no SQL Developer. Resolvida com `src/fase3_banco_oracle/servico_oracle.py`.
- **Fase 5:** não há infraestrutura AWS criada, só a estimativa de custo. O serviço de alertas foi criado do zero no Learner Lab.
- **Fase 6:** não havia modelo agrícola nem pesos salvos. Resolvida com a YOLOv5s treinada no AgroInsect, em `src/fase6_visao_computacional/`.
- **ISO 27001** (citada no mapa da Fase 5): não há material nos repositórios.
