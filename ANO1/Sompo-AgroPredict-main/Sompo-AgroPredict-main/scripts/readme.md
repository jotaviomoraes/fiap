# scripts

Scripts auxiliares de execucao, operacao e validacao do projeto. Todos rodam a partir da raiz do
repositorio.

| Script | Descricao |
|---|---|
| `executar_pipeline.py` | Fluxo de ponta a ponta com um comando: testes, frota simulada, validacao da integracao e relatorio, atualizando `document/evidencias/`. Com `--completo`, tambem regera o dataset e retreina o modelo. |
| `simular_frota.py` | Popula o SQLite com uma frota ficticia (6 equipamentos, 3 regioes) pelo mesmo fluxo entrada -> banco -> modelo -> saida do dashboard, com uma pequena taxa de falhas de coleta para exercitar a rastreabilidade. |
| `validar_integracao.py` | Valida as fontes de dados (Open-Meteo real, falhas simuladas, GPS, lote com problemas injetados, corrupcao, consistencia com o Oracle) em banco temporario e gera `document/evidencias/validacao_integracao.md`. |
| `gerar_relatorio.py` | Gera o relatorio consolidado de risco da frota em Markdown (salvo em `data/`, nao versionado) com as mesmas consultas do dashboard. |
| `gerenciar_usuarios.py` | Cria, lista e desativa usuarios do dashboard com perfil (operador, gestor, tecnico, analista, admin). A senha e gravada apenas como hash PBKDF2. |
| `run_dashboard.ps1` | Sobe o dashboard Streamlit no Windows (PowerShell). |
| `run_dashboard.sh` | Mesma funcao, para Linux/macOS. |

Scripts de dados e modelo ficam junto ao codigo-fonte:

- `src/data/gerar_dataset_v3.py` — dataset bruto da Sprint 4, com problemas de coleta
- `src/modelo/treinar_modelo.py` — treino reproduzivel do modelo final, relatorio e graficos
- `src/sql/schema.sql`, `src/sql/inserir_predicoes.py`, `src/sql/consultas.sql` — Oracle XE opcional
