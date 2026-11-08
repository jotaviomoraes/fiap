options(scipen = 999) # Desativa a notação científica

# ============================================================
# FarmTech Solutions - Análise Estatística + Meteorologia
# ============================================================

if (!require(httr)) install.packages("httr")
if (!require(jsonlite)) install.packages("jsonlite")

library(httr)
library(jsonlite)

# 1. Importando os dados do arquivo gerado pelo Python 

if (!file.exists("dados_farmtech.csv")) {
  cat("Arquivo dados_farmtech.csv não encontrado. Rode gestao_manejo.py antes.\n")
  quit(save = "no", status = 1)
}

dados_farmtech <- read.csv("dados_farmtech.csv", fileEncoding = "UTF-8")

cat("=== Dados Carregados do CSV ===\n")
print(dados_farmtech)

# 2. Cálculo das Estatísticas 

# Área (m²)
media_area         <- mean(dados_farmtech$Area_m2)
desvio_padrao_area <- sd(dados_farmtech$Area_m2)

# Quantidade de Ruas
media_ruas         <- mean(dados_farmtech$Qtd_Ruas)
desvio_padrao_ruas <- sd(dados_farmtech$Qtd_Ruas)

# 3. Exibição dos Resultados 

cat("\n=== Estatísticas da Área (m²) ===\n")
cat("Média da Área:        ", round(media_area, 2), "m²\n")
cat("Desvio Padrão da Área:", round(desvio_padrao_area, 2), "m²\n")

cat("\n=== Estatísticas da Quantidade de Ruas ===\n")
cat("Média de Ruas:        ", round(media_ruas, 2), "\n")
cat("Desvio Padrão de Ruas:", round(desvio_padrao_ruas, 2), "\n")

# 4. Resumo Estatístico Geral 

cat("\n=== Resumo Estatístico Geral (summary) ===\n")
print(summary(dados_farmtech[c("Area_m2", "Qtd_Ruas")]))

# ============================================================
# 5. Dados Meteorológicos - Open-Meteo API
# ============================================================

# Cidade da fazenda 

cidade    <- "Marília, SP (Café/Soja)"
latitude  <- -22.21
longitude <- -49.95

# Chamada à API 

url <- paste0(
  "https://api.open-meteo.com/v1/forecast",
  "?latitude=", latitude,
  "&longitude=", longitude,
  "&current_weather=true",
  "&hourly=relative_humidity_2m,precipitation_probability"
)

resposta <- tryCatch(GET(url), error = function(erro) NULL)

if (is.null(resposta) || status_code(resposta) != 200) {
  cat("\nNão foi possível consultar a Open-Meteo. Verifique a conexão com a internet.\n")
  quit(save = "no", status = 1)
}

# Processando e exibindo os dados

dados       <- fromJSON(content(resposta, as = "text", encoding = "UTF-8"))
temperatura <- dados$current_weather$temperature
vento_kmh   <- dados$current_weather$windspeed
umidade     <- dados$hourly$relative_humidity_2m[1]
chuva_prob  <- dados$hourly$precipitation_probability[1]

cat("\n============================================================\n")
cat("       FarmTech Solutions - Condições Meteorológicas\n")
cat("============================================================\n")
cat("Cidade              :", cidade, "\n")
cat("Temperatura         :", temperatura, "°C\n")
cat("Velocidade do Vento :", vento_kmh, "km/h\n")
cat("Umidade Relativa    :", umidade, "%\n")
cat("Probabilidade Chuva :", chuva_prob, "%\n")
cat("============================================================\n")