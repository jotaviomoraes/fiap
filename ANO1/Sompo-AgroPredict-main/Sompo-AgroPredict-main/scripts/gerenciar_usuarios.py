"""
gerenciar_usuarios.py
---------------------
Cadastro de usuarios do dashboard com perfil de acesso. A senha e pedida
de forma interativa (ou lida de AGROPREDICT_SENHA) e gravada apenas como
hash PBKDF2 no SQLite; nenhuma credencial fica no codigo.

Uso, a partir da raiz do repositorio:
    python scripts/gerenciar_usuarios.py criar --usuario gestor1 --perfil gestor --nome "Ana Gestora"
    python scripts/gerenciar_usuarios.py listar
    python scripts/gerenciar_usuarios.py desativar --usuario gestor1

Perfis: operador, gestor, tecnico, analista, admin
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agropredict.persistencia import RepositorioSQLite  # noqa: E402
from agropredict.seguranca import PERFIS, SenhaFraca, ServicoAutenticacao  # noqa: E402


def ler_senha() -> str:
    senha = os.getenv("AGROPREDICT_SENHA")
    if senha:
        return senha
    senha = getpass.getpass("Senha: ")
    if senha != getpass.getpass("Confirme a senha: "):
        sys.exit("[ERRO] As senhas nao conferem.")
    return senha


def main() -> None:
    parser = argparse.ArgumentParser(description="Usuarios do Sompo AgroPredict")
    sub = parser.add_subparsers(dest="comando", required=True)

    criar = sub.add_parser("criar", help="cria o usuario ou redefine senha/perfil")
    criar.add_argument("--usuario", required=True)
    criar.add_argument("--perfil", required=True, choices=sorted(PERFIS))
    criar.add_argument("--nome")

    sub.add_parser("listar")

    desativar = sub.add_parser("desativar")
    desativar.add_argument("--usuario", required=True)

    args = parser.parse_args()
    repo = RepositorioSQLite()

    if args.comando == "criar":
        try:
            ServicoAutenticacao(repo).cadastrar(args.usuario, ler_senha(), args.perfil, args.nome)
        except (SenhaFraca, ValueError) as exc:
            sys.exit(f"[ERRO] {exc}")
        print(f"[OK] Usuario '{args.usuario}' salvo com perfil '{args.perfil}'.")
    elif args.comando == "listar":
        usuarios = repo.listar_usuarios()
        print(usuarios.to_string(index=False) if not usuarios.empty else "Nenhum usuario cadastrado.")
    elif args.comando == "desativar":
        if not repo.definir_usuario_ativo(args.usuario, False):
            sys.exit(f"[ERRO] Usuario '{args.usuario}' nao encontrado.")
        print(f"[OK] Usuario '{args.usuario}' desativado.")


if __name__ == "__main__":
    main()
