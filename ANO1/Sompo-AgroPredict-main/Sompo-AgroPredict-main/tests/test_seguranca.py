import unittest

import apoio

from agropredict.seguranca import (
    MAX_FALHAS_LOGIN,
    PERFIS,
    SenhaFraca,
    ServicoAutenticacao,
    gerar_hash_senha,
    pode,
    verificar_senha,
)


class SenhaTests(unittest.TestCase):
    def test_hash_verifica_e_nao_contem_a_senha(self):
        armazenado = gerar_hash_senha("senha-forte-123")
        self.assertNotIn("senha-forte-123", armazenado)
        self.assertTrue(verificar_senha("senha-forte-123", armazenado))
        self.assertFalse(verificar_senha("senha-errada", armazenado))

    def test_salt_diferente_a_cada_hash(self):
        self.assertNotEqual(gerar_hash_senha("senha-forte-123"), gerar_hash_senha("senha-forte-123"))

    def test_senha_curta_e_rejeitada(self):
        with self.assertRaises(SenhaFraca):
            gerar_hash_senha("123")

    def test_hash_malformado_nao_autentica(self):
        self.assertFalse(verificar_senha("qualquer", "texto-sem-formato"))


class PerfisTests(unittest.TestCase):
    def test_matriz_de_permissoes(self):
        self.assertTrue(pode("operador", "operacao"))
        self.assertFalse(pode("operador", "frota"))
        self.assertFalse(pode("operador", "auditoria"))
        self.assertTrue(pode("gestor", "frota"))
        self.assertFalse(pode("gestor", "auditoria"))
        self.assertTrue(pode("tecnico", "manutencao"))
        self.assertFalse(pode("tecnico", "operacao"))
        self.assertTrue(pode("analista", "auditoria"))
        self.assertFalse(pode("analista", "responder_alerta"))

    def test_admin_acessa_tudo(self):
        for recurso in ("operacao", "frota", "alertas", "responder_alerta", "manutencao", "auditoria"):
            self.assertTrue(pode("admin", recurso))

    def test_todo_perfil_ve_alertas(self):
        for perfil in PERFIS:
            self.assertTrue(pode(perfil, "alertas"))


class AutenticacaoTests(unittest.TestCase):
    def test_login_registra_perfil_no_log(self):
        with apoio.BancoTemporario() as b:
            auth = ServicoAutenticacao(b.repo)
            auth.cadastrar("gestor1", "senha-forte-123", "gestor", "Gestora")
            sessao = auth.autenticar("gestor1", "senha-forte-123")
            self.assertEqual((sessao.usuario, sessao.perfil), ("gestor1", "gestor"))
            self.assertIsNone(auth.autenticar("gestor1", "errada"))

            log = b.repo.consultar("SELECT usuario, perfil, evento, sucesso FROM log_acessos ORDER BY id")
            self.assertEqual(log["sucesso"].tolist(), [1, 0])
            self.assertEqual(log["perfil"].iloc[0], "gestor")

    def test_senha_nao_fica_no_banco(self):
        with apoio.BancoTemporario() as b:
            ServicoAutenticacao(b.repo).cadastrar("op1", "senha-forte-123", "operador")
            self.assertNotIn("senha-forte-123", b.repo.obter_usuario("op1")["senha_hash"])

    def test_bloqueio_apos_falhas_consecutivas(self):
        with apoio.BancoTemporario() as b:
            auth = ServicoAutenticacao(b.repo)
            auth.cadastrar("op1", "senha-forte-123", "operador")
            for _ in range(MAX_FALHAS_LOGIN):
                auth.autenticar("op1", "errada")
            self.assertTrue(auth.bloqueado("op1"))
            # Mesmo com a senha correta, o login fica bloqueado durante a janela
            self.assertIsNone(auth.autenticar("op1", "senha-forte-123"))

    def test_usuario_desativado_nao_entra(self):
        with apoio.BancoTemporario() as b:
            auth = ServicoAutenticacao(b.repo)
            auth.cadastrar("op1", "senha-forte-123", "operador")
            b.repo.definir_usuario_ativo("op1", False)
            self.assertIsNone(auth.autenticar("op1", "senha-forte-123"))

    def test_perfil_invalido(self):
        with apoio.BancoTemporario() as b:
            with self.assertRaises(ValueError):
                ServicoAutenticacao(b.repo).cadastrar("x", "senha-forte-123", "superusuario")


if __name__ == "__main__":
    unittest.main()
