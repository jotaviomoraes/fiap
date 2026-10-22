"""
servico.py
----------
Orquestrador do fluxo de ponta a ponta, sem dependencia de interface:

    1. registrar_leitura  -> valida a entrada, recusa duplicatas e grava em
                             `leituras` (PENDENTE) com hash de integridade;
                             entradas recusadas vao para `rejeicoes`
    2. processar_leitura  -> le a leitura DO BANCO, confere o hash, aplica
                             modelo + regras e grava `predicoes`/`alertas`
                             (PROCESSADA)
    3. replicacao Oracle opcional, com o mesmo resultado

`processar` executa 1 e 2 em sequencia. `avaliar` so calcula (previa na
tela, sem gravar) e usa exatamente a mesma funcao de avaliacao.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from . import oracle
from .avaliacao import Avaliacao, avaliar
from .entrada import FEATURES, Leitura, LeituraInvalida
from .integridade import hash_leitura
from .modelo import ModeloRisco
from .persistencia import RepositorioSQLite, agora_iso

logger = logging.getLogger("agropredict.servico")


class ErroProcessamento(RuntimeError):
    pass


class LeituraDuplicada(ValueError):
    """Leitura identica a uma ja registrada (retransmissao)."""

    def __init__(self, id_existente: int):
        self.id_existente = id_existente
        super().__init__(f"Leitura duplicada da leitura #{id_existente}")


@dataclass(frozen=True)
class Resultado:
    id_leitura: int
    id_predicao: int
    id_alerta: int | None
    leitura: Leitura
    avaliacao: Avaliacao
    gravado_oracle: bool


class ServicoAvaliacao:
    def __init__(self, repo: RepositorioSQLite, modelo: ModeloRisco, config_oracle: dict | None = None):
        self.repo = repo
        self.modelo = modelo
        self.config_oracle = config_oracle

    def avaliar(self, dados: dict | Leitura) -> tuple[Leitura, Avaliacao]:
        """Previa sem persistencia. Lanca LeituraInvalida se a entrada for invalida."""
        leitura = dados if isinstance(dados, Leitura) else Leitura.de_dict(dados)
        return leitura, avaliar(self.modelo, leitura)

    def registrar_leitura(
        self,
        dados: dict | Leitura,
        id_equipamento: int,
        usuario: str,
        origem: str = "dashboard",
        fontes: dict | None = None,
        posicao: dict | None = None,
        data_hora: str | None = None,
    ) -> int:
        brutos = dados.como_dict() if isinstance(dados, Leitura) else dict(dados)
        try:
            leitura = dados if isinstance(dados, Leitura) else Leitura.de_dict(dados)
            if self.repo.obter_equipamento(id_equipamento) is None:
                raise LeituraInvalida([f"equipamento {id_equipamento} nao cadastrado"])
        except LeituraInvalida as exc:
            self.repo.registrar_rejeicao("INVALIDA", "; ".join(exc.problemas), origem, usuario,
                                         id_equipamento, brutos)
            logger.warning("leitura rejeitada origem=%s usuario=%s motivo=%s", origem, usuario, exc)
            raise

        data_hora = data_hora or agora_iso()
        existente = self.repo.id_leitura_por_hash(hash_leitura(leitura, id_equipamento, data_hora, usuario[:120]))
        if existente is not None:
            self.repo.registrar_rejeicao("DUPLICADA", f"identica a leitura #{existente}", origem, usuario,
                                         id_equipamento, brutos)
            logger.warning("leitura duplicada origem=%s usuario=%s existente=%s", origem, usuario, existente)
            raise LeituraDuplicada(existente)

        id_leitura = self.repo.inserir_leitura(
            leitura, id_equipamento, usuario, origem, fontes, posicao, data_hora
        )
        logger.info("leitura=%s equipamento=%s usuario=%s origem=%s entrada=%s",
                    id_leitura, id_equipamento, usuario, origem, leitura.como_dict())
        return id_leitura

    def processar_leitura(self, id_leitura: int) -> Resultado:
        registro = self.repo.obter_leitura(id_leitura)
        if registro is None:
            raise ErroProcessamento(f"Leitura {id_leitura} nao encontrada.")
        if registro["status_processamento"] == "PROCESSADA":
            raise ErroProcessamento(f"Leitura {id_leitura} ja foi processada.")

        try:
            # A entrada do modelo vem do banco, nao da tela.
            leitura = Leitura.de_dict({campo: registro[campo] for campo in FEATURES})
            esperado = registro.get("hash_entrada")
            if esperado and esperado != hash_leitura(leitura, registro["id_equipamento"],
                                                     registro["data_hora"], registro["usuario"]):
                raise ErroProcessamento("integridade violada: a leitura foi alterada depois de gravada")
            avaliacao = avaliar(self.modelo, leitura)
            id_predicao, id_alerta = self.repo.salvar_resultado(id_leitura, avaliacao, registro["data_hora"])
        except Exception as exc:
            self.repo.marcar_leitura_com_erro(id_leitura, str(exc))
            logger.exception("Falha ao processar leitura=%s", id_leitura)
            raise ErroProcessamento(f"Falha ao processar leitura {id_leitura}: {exc}") from exc

        gravado_oracle = oracle.replicar(self.config_oracle, leitura, avaliacao, registro["id_equipamento"])
        if gravado_oracle:
            self.repo.marcar_gravado_oracle(id_predicao)

        logger.info(
            "predicao=%s leitura=%s classe=%s score=%.2f override=%s probs=%s modelo=%s/%s alerta=%s",
            id_predicao, id_leitura, avaliacao.classe_risco, avaliacao.score_risco,
            avaliacao.override_aplicado, avaliacao.probabilidades,
            avaliacao.versao_modelo, avaliacao.hash_modelo, id_alerta,
        )
        return Resultado(id_leitura, id_predicao, id_alerta, leitura, avaliacao, gravado_oracle)

    def processar(self, dados: dict | Leitura, id_equipamento: int, usuario: str, **kwargs) -> Resultado:
        id_leitura = self.registrar_leitura(dados, id_equipamento, usuario, **kwargs)
        return self.processar_leitura(id_leitura)

    def processar_pendentes(self) -> list[Resultado]:
        """Reprocessa leituras que entraram no banco mas nao foram avaliadas."""
        resultados = []
        for id_leitura in self.repo.ids_leituras_pendentes():
            try:
                resultados.append(self.processar_leitura(id_leitura))
            except ErroProcessamento:
                continue
        return resultados

    def responder_alerta(self, id_alerta: int, acao: str, usuario: str, observacao: str | None = None) -> bool:
        ok = self.repo.registrar_acao_alerta(id_alerta, acao, usuario, observacao)
        logger.info("alerta=%s acao=%s usuario=%s registrado=%s", id_alerta, acao, usuario, ok)
        return ok
