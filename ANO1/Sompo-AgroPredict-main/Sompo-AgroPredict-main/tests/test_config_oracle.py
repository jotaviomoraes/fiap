"""Wallet textual dos Secrets: arquivos privados, compatibilidade e fallback."""

import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agropredict.config import backend_configurado, config_oracle, _criar_wallet_temporaria
from agropredict.fabrica import abrir_repositorio

TNS = "teste_tp = (DESCRIPTION=(ADDRESS=(PROTOCOL=TCPS)(HOST=example.invalid)(PORT=1522)))"
# Conteúdo fictício; os testes nunca abrem conexão Oracle.
PEM = "-----BEGIN CERTIFICATE-----\nCERTIFICADO_FICTICIO\n-----END CERTIFICATE-----"
CREDENCIAIS = {"ORACLE_USER": "usuario_teste", "ORACLE_PASSWORD": "senha_ficticia",
               "ORACLE_DSN": "teste_tp", "ORACLE_WALLET_PASSWORD": "senha_wallet_ficticia"}


class ConfigOracleTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.secrets = {}
        self.streamlit = patch.dict(sys.modules, {"streamlit": SimpleNamespace(secrets=self.secrets)})
        self.streamlit.start()
        _criar_wallet_temporaria.cache_clear()

    def tearDown(self):
        _criar_wallet_temporaria.cache_clear()
        self.streamlit.stop()
        self.env.stop()

    def configurar_wallet(self):
        self.secrets.update(CREDENCIAIS, ORACLE_TNSNAMES=TNS, ORACLE_WALLET_PEM=PEM)

    def test_secrets_criam_arquivos_e_reutilizam_a_mesma_pasta(self):
        self.configurar_wallet()
        config = config_oracle()
        pasta = Path(config["config_dir"])
        self.assertEqual(config["wallet_location"], str(pasta))
        self.assertEqual(config["wallet_password"], CREDENCIAIS["ORACLE_WALLET_PASSWORD"])
        self.assertEqual(config["password"], CREDENCIAIS["ORACLE_PASSWORD"])
        self.assertEqual((pasta / "tnsnames.ora").read_text(encoding="utf-8"), TNS + "\n")
        self.assertEqual((pasta / "ewallet.pem").read_text(encoding="utf-8"), PEM + "\n")
        self.assertEqual(config_oracle()["config_dir"], str(pasta))
        if os.name != "nt":
            self.assertEqual(pasta.stat().st_mode & 0o777, 0o700)
            self.assertEqual((pasta / "ewallet.pem").stat().st_mode & 0o777, 0o600)

    def test_conteudos_substituem_caminhos_windows_do_env(self):
        self.configurar_wallet()
        os.environ.update(ORACLE_CONFIG_DIR="C:\\pasta_inexistente", ORACLE_WALLET_LOCATION="C:\\pasta_inexistente")
        config = config_oracle()
        self.assertTrue(Path(config["config_dir"]).is_dir())
        self.assertNotEqual(config["config_dir"], os.environ["ORACLE_CONFIG_DIR"])

    def test_local_sem_conteudos_preserva_caminhos_e_senhas(self):
        os.environ.update(CREDENCIAIS, ORACLE_CONFIG_DIR="wallet-local", ORACLE_WALLET_LOCATION="wallet-local")
        with patch("agropredict.config._criar_wallet_temporaria") as criar:
            config = config_oracle()
        criar.assert_not_called()
        self.assertEqual(config["config_dir"], "wallet-local")
        self.assertEqual(config["wallet_location"], "wallet-local")

    def test_ambiente_tem_precedencia_sobre_secrets(self):
        self.secrets.update(CREDENCIAIS)
        os.environ.update(ORACLE_USER="usuario_ambiente", ORACLE_PASSWORD=" senha com espacos ")
        config = config_oracle()
        self.assertEqual(config["user"], "usuario_ambiente")
        self.assertEqual(config["password"], " senha com espacos ")

    def test_conteudos_incompletos_ou_placeholder_nao_expoem_segredos(self):
        for conteudos in ({"ORACLE_TNSNAMES": TNS}, {"ORACLE_WALLET_PEM": PEM},
                          {"ORACLE_TNSNAMES": TNS, "ORACLE_WALLET_PEM": "CONTEUDO_PRIVADO_INVALIDO"}):
            self.secrets.clear()
            self.secrets.update(conteudos)
            with self.assertRaises(ValueError) as erro:
                config_oracle()
            for valor in conteudos.values():
                self.assertNotIn(valor, str(erro.exception))
        self.assertEqual(_criar_wallet_temporaria.cache_info().currsize, 0)

    def test_normaliza_bom_e_quebras_windows(self):
        self.configurar_wallet()
        self.secrets["ORACLE_TNSNAMES"] = "\ufeff\r\n" + TNS + "\r\n"
        self.secrets["ORACLE_WALLET_PEM"] = "\r\n" + PEM.replace("\n", "\r\n") + "\r\n"
        config = config_oracle()
        self.assertEqual((Path(config["config_dir"]) / "ewallet.pem").read_bytes(), (PEM + "\n").encode())

    def test_sessoes_concorrentes_reutilizam_wallet(self):
        self.configurar_wallet()
        with ThreadPoolExecutor(max_workers=4) as executor:
            pastas = list(executor.map(lambda _: config_oracle()["config_dir"], range(8)))
        self.assertEqual(len(set(pastas)), 1)
        self.assertEqual(_criar_wallet_temporaria.cache_info().misses, 1)

    def test_rotacao_do_conteudo_gera_nova_wallet_sem_apagar_anterior(self):
        self.configurar_wallet()
        primeira = config_oracle()["config_dir"]
        self.secrets["ORACLE_TNSNAMES"] = TNS.replace("example.invalid", "novo.example.invalid")
        segunda = config_oracle()["config_dir"]
        self.assertNotEqual(primeira, segunda)
        self.assertTrue(Path(primeira).is_dir())

    def test_backend_pode_vir_dos_secrets(self):
        self.secrets["DB_BACKEND"] = "oracle"
        self.assertEqual(backend_configurado(), "oracle")

    def test_wallet_incompleta_respeita_auto_e_modo_oracle(self):
        self.secrets.update(CREDENCIAIS, ORACLE_TNSNAMES=TNS)
        with patch("agropredict.fabrica.RepositorioSQLite") as sqlite, \
                patch("agropredict.repositorio_oracle.RepositorioOracle") as oracle:
            _, backend, aviso = abrir_repositorio("auto")
            self.assertEqual(backend, "sqlite")
            self.assertIn("ORACLE_TNSNAMES e ORACLE_WALLET_PEM", aviso)
            sqlite.assert_called_once()
            oracle.assert_not_called()
            sqlite.reset_mock()
            with self.assertRaises(RuntimeError):
                abrir_repositorio("oracle")
            sqlite.assert_not_called()

    def test_sem_arquivo_secrets_e_erro_de_toml_sao_tratados(self):
        streamlit = sys.modules["streamlit"]
        streamlit.secrets = Mock()
        streamlit.secrets.get.side_effect = FileNotFoundError()
        self.assertEqual(config_oracle()["user"], "")
        streamlit.secrets.get.side_effect = RuntimeError("conteudo secreto nao deve aparecer")
        with self.assertRaises(ValueError) as erro:
            config_oracle()
        self.assertNotIn("conteudo secreto", str(erro.exception))


if __name__ == "__main__":
    unittest.main()
