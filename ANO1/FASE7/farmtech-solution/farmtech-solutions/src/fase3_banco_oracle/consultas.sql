-- ============================================================
-- FarmTech Solutions - Fase 3 - Banco de Dados Estruturado (Oracle)
-- Tabela com as leituras dos sensores gerados na Fase 2 (ESP32/Wokwi).
--
-- Na Fase 3 a tabela foi criada e carregada pelo Assistente de
-- Importação do Oracle SQL Developer a partir de sensores_agricolas.csv
-- (prints em assets/fase3). O DDL abaixo é o equivalente em SQL dessa
-- importação, com os mesmos tipos de coluna.
-- ============================================================

CREATE TABLE farmsensores_agricolas (
    n           NUMBER(1),      -- presença de Nitrogênio (1 = botão pressionado)
    p           NUMBER(1),      -- presença de Fósforo
    k           NUMBER(1),      -- presença de Potássio
    temperatura NUMBER(5,2),    -- °C (DHT22)
    umidade     NUMBER(5,2),    -- % umidade do solo (DHT22)
    ph          NUMBER(5,2),    -- pH do solo (LDR + influência NPK)
    chuva       NUMBER(5,2),    -- chuva prevista em mm (OpenWeather)
    cultura     VARCHAR2(30),   -- coluna "label" do CSV, renomeada
    irrigacao   VARCHAR2(20)    -- LIGADA / DESLIGADA
);

-- 1. Listagem completa (10 registros)
SELECT * FROM farmsensores_agricolas;

-- 2. Temperatura elevada (6 registros acima de 30 °C)
SELECT * FROM farmsensores_agricolas WHERE temperatura > 30;

-- 3. Baixa umidade (6 registros abaixo de 40%)
SELECT * FROM farmsensores_agricolas WHERE umidade < 40;

-- 4. pH ideal para milho (8 registros entre 5.5 e 7.0)
SELECT * FROM farmsensores_agricolas WHERE ph BETWEEN 5.5 AND 7.0;

-- 5. Chuva prevista (2 registros com previsão > 0 mm)
SELECT * FROM farmsensores_agricolas WHERE chuva > 0;

-- 6. Bomba ligada (5 registros em que o sistema acionou a irrigação)
SELECT * FROM farmsensores_agricolas WHERE irrigacao = 'LIGADA';
