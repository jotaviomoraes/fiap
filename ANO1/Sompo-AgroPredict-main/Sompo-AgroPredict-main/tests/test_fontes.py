"""Confiabilidade da coleta: API Open-Meteo (com respostas simuladas) e velocidade por GPS."""

import unittest
from unittest import mock

import requests

import apoio  # noqa: F401

from agropredict import clima
from agropredict.telemetria import calcular_velocidade_kmh, haversine_km


def _resposta(json_data, status=200):
    resp = mock.Mock()
    resp.json.return_value = json_data
    resp.raise_for_status.side_effect = None if status == 200 else requests.HTTPError(f"HTTP {status}")
    return resp


HORAS = [f"2026-09-26T{h:02d}:00" for h in range(24)] + ["2026-09-27T00:00"]
OK = {
    "current": {"time": "2026-09-26T23:00", "temperature_2m": 27.4, "precipitation": 0.0},
    "hourly": {"time": HORAS, "precipitation": [0.5] * 25, "soil_moisture_0_to_1cm": [0.31] * 25},
}


class OpenMeteoTests(unittest.TestCase):
    def test_resposta_valida(self):
        with mock.patch.object(clima.requests, "get", return_value=_resposta(OK)):
            dados = clima.buscar_clima_atual(-12.5, -55.7)
        self.assertTrue(dados["ok"])
        self.assertEqual(dados["temperatura"], 27.4)
        self.assertEqual(dados["chuva_24h"], 12.0)  # 24 horas x 0.5 mm
        self.assertEqual(dados["umidade_solo"], 31.0)

    def test_horas_sem_chuva_informada_nao_quebram_a_soma(self):
        payload = {**OK, "hourly": {**OK["hourly"], "precipitation": [None, 1.0] * 12 + [None]}}
        with mock.patch.object(clima.requests, "get", return_value=_resposta(payload)):
            self.assertEqual(clima.buscar_clima_atual(0, 0)["chuva_24h"], 12.0)

    def test_sem_umidade_do_solo(self):
        payload = {**OK, "hourly": {k: v for k, v in OK["hourly"].items() if k != "soil_moisture_0_to_1cm"}}
        with mock.patch.object(clima.requests, "get", return_value=_resposta(payload)):
            dados = clima.buscar_clima_atual(0, 0)
        self.assertTrue(dados["ok"])
        self.assertIsNone(dados["umidade_solo"])

    def test_falhas_viram_ok_false_sem_excecao(self):
        cenarios = {
            "timeout": mock.Mock(side_effect=requests.Timeout("tempo esgotado")),
            "sem rede": mock.Mock(side_effect=requests.ConnectionError("sem rede")),
            "http 500": mock.Mock(return_value=_resposta({}, status=500)),
            "json sem campos": mock.Mock(return_value=_resposta({"current": {}})),
            "json invalido": mock.Mock(return_value=mock.Mock(raise_for_status=mock.Mock(),
                                                              json=mock.Mock(side_effect=ValueError("json")))),
            "tipo errado": mock.Mock(return_value=_resposta({**OK, "current": {**OK["current"],
                                                                               "temperature_2m": None}})),
        }
        for nome, get in cenarios.items():
            with self.subTest(nome), mock.patch.object(clima.requests, "get", get):
                dados = clima.buscar_clima_atual(0, 0)
                self.assertFalse(dados["ok"])
                self.assertIsNone(dados["temperatura"])
                self.assertIn("erro", dados)


class VelocidadeGpsTests(unittest.TestCase):
    A = {"lat": -12.5000, "lon": -55.7000, "timestamp": 1000.0}

    def test_haversine(self):
        # 1 grau de latitude ~ 111,2 km
        self.assertAlmostEqual(haversine_km(0, 0, 1, 0), 111.19, places=1)

    def test_velocidade_do_chip(self):
        self.assertEqual(calcular_velocidade_kmh({**self.A, "speed_ms": 5.0}, None), (18.0, "gps_chip"))

    def test_velocidade_calculada_entre_dois_pontos(self):
        # ~0,0833 km em 30 s = ~10 km/h
        b = {"lat": -12.500749, "lon": -55.7000, "timestamp": 1030.0}
        velocidade, origem = calcular_velocidade_kmh(b, self.A)
        self.assertEqual(origem, "calculada")
        self.assertAlmostEqual(velocidade, 10.0, delta=0.2)

    def test_deriva_parado_vira_zero(self):
        b = {"lat": -12.500001, "lon": -55.7000, "timestamp": 1010.0}
        self.assertEqual(calcular_velocidade_kmh(b, self.A), (0.0, "calculada"))

    def test_leituras_incoerentes_sao_descartadas(self):
        casos = {
            "sem posicao": (None, self.A),
            "primeira leitura": (self.A, None),
            "tempo voltou": ({**self.A, "timestamp": 990.0, "lat": -12.6}, self.A),
            "mesmo instante": ({**self.A, "lat": -12.6}, self.A),
            "salto de GPS": ({"lat": -13.5, "lon": -55.7, "timestamp": 1010.0}, self.A),
            "chip absurdo": ({**self.A, "speed_ms": 90.0}, None),
            "latitude invalida": ({**self.A, "lat": 123.0}, None),
            "coordenada em texto": ({**self.A, "lat": "-12.5"}, None),
        }
        for nome, (atual, anterior) in casos.items():
            with self.subTest(nome):
                self.assertEqual(calcular_velocidade_kmh(atual, anterior), (None, "indisponivel"))


if __name__ == "__main__":
    unittest.main()
