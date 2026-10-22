"""
seguranca.py
------------
Autenticacao com senha em hash (PBKDF2-SHA256 + salt), bloqueio por
tentativas e controle de acesso por perfil (RBAC).

Perfis e o que cada um enxerga:
  operador  -> operacao em tempo real e os proprios alertas (US-01)
  gestor    -> operacao, frota/tendencias, alertas e manutencao (US-02)
  tecnico   -> alertas e painel de manutencao
  analista  -> frota/tendencias, alertas e auditoria (US-03)
  admin     -> tudo
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from .persistencia import RepositorioSQLite

PERFIS = {
    "operador": "Operador de campo",
    "gestor": "Gestor de frota",
    "tecnico": "Tecnico de manutencao",
    "analista": "Analista Sompo",
    "admin": "Administrador",
}

PERMISSOES = {
    "operacao": {"operador", "gestor", "admin"},
    "frota": {"gestor", "analista", "admin"},
    "alertas": {"operador", "gestor", "tecnico", "analista", "admin"},
    "responder_alerta": {"operador", "gestor", "admin"},
    "manutencao": {"tecnico", "gestor", "admin"},
    "auditoria": {"analista", "admin"},
}

ITERACOES_PBKDF2 = 200_000
TAMANHO_MINIMO_SENHA = 8
MAX_FALHAS_LOGIN = 5
JANELA_BLOQUEIO_MIN = 15


class SenhaFraca(ValueError):
    pass


@dataclass(frozen=True)
class Sessao:
    usuario: str
    perfil: str
    nome: str | None = None

    def pode(self, recurso: str) -> bool:
        return pode(self.perfil, recurso)


def pode(perfil: str, recurso: str) -> bool:
    return perfil in PERMISSOES.get(recurso, set())


def gerar_hash_senha(senha: str) -> str:
    if len(senha) < TAMANHO_MINIMO_SENHA:
        raise SenhaFraca(f"A senha precisa ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, ITERACOES_PBKDF2)
    return f"pbkdf2_sha256${ITERACOES_PBKDF2}${salt.hex()}${digest.hex()}"


def verificar_senha(senha: str, armazenado: str) -> bool:
    try:
        algoritmo, iteracoes, salt_hex, digest_hex = armazenado.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        calculado = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(salt_hex), int(iteracoes))
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(calculado.hex(), digest_hex)


class ServicoAutenticacao:
    def __init__(self, repo: RepositorioSQLite):
        self.repo = repo

    def cadastrar(self, usuario: str, senha: str, perfil: str, nome: str | None = None) -> None:
        usuario = usuario.strip()
        if not usuario:
            raise ValueError("Usuario nao pode ser vazio.")
        if perfil not in PERFIS:
            raise ValueError(f"Perfil invalido: {perfil}. Use um de {sorted(PERFIS)}.")
        self.repo.salvar_usuario(usuario, gerar_hash_senha(senha), perfil, nome)

    def bloqueado(self, usuario: str) -> bool:
        desde = (datetime.now() - timedelta(minutes=JANELA_BLOQUEIO_MIN)).isoformat(sep=" ", timespec="seconds")
        return self.repo.falhas_login_desde(usuario, desde) >= MAX_FALHAS_LOGIN

    def autenticar(self, usuario: str, senha: str) -> Sessao | None:
        """Valida as credenciais e registra o resultado no log de acessos."""
        usuario = (usuario or "").strip()
        if self.bloqueado(usuario):
            self.repo.registrar_acesso(usuario, "login_bloqueado", False)
            return None

        registro = self.repo.obter_usuario(usuario) if usuario else None
        valido = bool(registro and registro["ativo"] and verificar_senha(senha or "", registro["senha_hash"]))
        perfil = registro["perfil"] if valido else None
        self.repo.registrar_acesso(usuario, "login", valido, perfil)
        if not valido:
            return None
        return Sessao(usuario=usuario, perfil=perfil, nome=registro.get("nome"))

    def registrar_logout(self, sessao: Sessao) -> None:
        self.repo.registrar_acesso(sessao.usuario, "logout", True, sessao.perfil)

    def registrar_acesso_negado(self, sessao: Sessao, recurso: str) -> None:
        self.repo.registrar_acesso(sessao.usuario, f"negado:{recurso}", False, sessao.perfil)
