from __future__ import annotations

from .modelos import Etapa, Objetivo, Plano, StatusEtapa
from .ferramentas import RegistroFerramentas


class Planejador:
    def __init__(self, registro: RegistroFerramentas | None = None):
        self.registro = registro

    def criar(self, objetivo: Objetivo, memorias: list[dict]) -> Plano:
        if objetivo.parametros.get("tipo") == "plano_ferramentas":
            if self.registro is None:
                raise ValueError("Registro de ferramentas indisponível para este plano")
            etapas = []
            for item in objetivo.parametros["etapas"]:
                ferramenta = self.registro.obter(item["ferramenta"])
                if not ferramenta.verificacao:
                    raise ValueError(f"Ferramenta sem verificação: {ferramenta.nome}")
                etapas.append(Etapa(ferramenta.descricao, ferramenta.nome,
                                    dict(item["parametros"]),
                                    dependencias=(etapas[-1].id,) if etapas else (),
                                    verificacao=ferramenta.verificacao))
            return Plano(etapas)
        if objetivo.parametros.get("tipo") == "exportar_contexto_projeto_ink":
            abrir = Etapa("Abrir Leitor de Projetos", "abrir_aplicacao_ink",
                          {"aplicacao": "project-reader"}, verificacao="abertura_aplicacao_ink")
            exportar = Etapa("Exportar contexto do projeto", "exportar_contexto_projeto_ink",
                             {"caminho": objetivo.parametros["caminho"],
                              "destino": objetivo.parametros["destino"]},
                             dependencias=(abrir.id,), verificacao="contexto_projeto_ink")
            resumir = Etapa("Criar resumo factual do projeto", "escrever_resumo_projeto",
                            {"caminho": objetivo.parametros["caminho"],
                             "destino": objetivo.parametros["destino"], "nome": "resumo_projeto.md"},
                            dependencias=(exportar.id,), verificacao="arquivo_projeto")
            return Plano([abrir, exportar, resumir])
        if objetivo.parametros.get("tipo") == "descrever_projeto":
            return Plano([Etapa("Descrever projeto", "descrever_projeto",
                                {"caminho": objetivo.parametros["caminho"]},
                                verificacao="descricao_projeto")])
        if objetivo.parametros.get("tipo") == "gerar_readme_projeto":
            inspecao = Etapa("Analisar projeto para documentação", "analisar_projeto_ink",
                             {"caminho": objetivo.parametros["caminho"]},
                             verificacao="analise_projeto_ink")
            escrita = Etapa("Criar README do projeto", "escrever_resumo_projeto",
                            {"caminho": objetivo.parametros["caminho"],
                             "destino": objetivo.parametros.get("destino", objetivo.parametros["caminho"]),
                             "nome": objetivo.parametros["nome"]},
                            dependencias=(inspecao.id,), verificacao="arquivo_projeto")
            return Plano([inspecao, escrita])
        if objetivo.parametros.get("tipo") == "resumir_projeto_em_arquivo":
            inspecao = Etapa("Analisar projeto", "analisar_projeto_ink",
                             {"caminho": objetivo.parametros["caminho"]},
                             verificacao="analise_projeto_ink")
            escrita = Etapa("Criar resumo do projeto", "escrever_resumo_projeto",
                            {"caminho": objetivo.parametros["caminho"],
                             "destino": objetivo.parametros["destino"],
                             "nome": "resumo_projeto.md"},
                            dependencias=(inspecao.id,), verificacao="arquivo_projeto")
            return Plano([inspecao, escrita])
        if objetivo.parametros.get("tipo") == "fechar_aplicativo":
            app = objetivo.parametros["aplicativo"]
            return Plano([Etapa(f"Fechar {app}", "fechar_aplicativo", {"nome": app},
                                verificacao="processo_encerrado")])
        if objetivo.parametros.get("tipo") == "listar_arquivos_projeto_ink":
            return Plano([Etapa("Listar arquivos do projeto", "listar_arquivos_projeto_ink",
                                {"caminho": objetivo.parametros["caminho"]},
                                verificacao="arquivos_projeto_ink")])
        if objetivo.parametros.get("tipo") == "listar_cadernos_ink":
            abrir = Etapa("Abrir Ink Notebook", "abrir_aplicacao_ink",
                          {"aplicacao": "notebook"}, verificacao="abertura_aplicacao_ink")
            listar = Etapa("Listar cadernos do Ink Notebook", "listar_cadernos_ink",
                           dependencias=(abrir.id,), verificacao="cadernos_ink")
            return Plano([abrir, listar])
        if objetivo.parametros.get("tipo") == "abrir_aplicacao_ink":
            aplicacao = objetivo.parametros["aplicacao"]
            return Plano([Etapa(f"Abrir {aplicacao}", "abrir_aplicacao_ink",
                                {"aplicacao": aplicacao}, verificacao="abertura_aplicacao_ink")])
        if objetivo.parametros.get("tipo") == "listar_aplicacoes_ink":
            return Plano([Etapa("Listar aplicações Ink-guginha", "listar_aplicacoes_ink",
                                verificacao="catalogo_aplicacoes_ink")])
        if objetivo.parametros.get("tipo") == "analisar_projeto_ink":
            return Plano([Etapa("Analisar projeto", "analisar_projeto_ink",
                                {"caminho": objetivo.parametros["caminho"]},
                                verificacao="analise_projeto_ink")])
        if objetivo.tipo == "comando" and objetivo.parametros.get("aplicativo"):
            app = objetivo.parametros["aplicativo"]
            return Plano([Etapa(f"Abrir {app}", "abrir_aplicativo", {"nome": app}, verificacao="processo")])
        if objetivo.parametros.get("tipo") != "preparar_programacao":
            raise ValueError("Objetivo ainda não suportado por este planejador")
        preferido = "intellij" if objetivo.parametros.get("linguagem") == "java" else "vscode"
        # Experiências só sugerem estratégia; a verificação atual continua obrigatória.
        for memoria in memorias:
            if memoria.get("categoria") == "experiencia" and memoria.get("valor", {}).get("objetivo") == objetivo.parametros:
                candidato = memoria["valor"].get("aplicativo")
                if candidato in ("vscode", "intellij"):
                    preferido = candidato
                    break
        inspecao = Etapa(f"Localizar {preferido}", "localizar_aplicativo", {"nome": preferido}, verificacao="executavel")
        abrir = Etapa(f"Abrir {preferido}", "abrir_aplicativo", {"nome": preferido},
                      dependencias=(inspecao.id,), verificacao="processo")
        return Plano([inspecao, abrir])

    def replanejar(self, plano: Plano, falha: Etapa, objetivo: Objetivo) -> bool:
        if (objetivo.parametros.get("tipo") in {"exportar_contexto_projeto_ink",
                                                  "resumir_projeto_em_arquivo", "plano_ferramentas"}
                and falha.ferramenta == "escrever_resumo_projeto"
                and falha.parametros.get("nome") == "resumo_projeto.md"
                and "resumo_projeto.md" not in objetivo.descricao.casefold()
                and falha.resultado and "já existe" in (falha.resultado.erro or "")):
            nomes = {e.parametros.get("nome") for e in plano.etapas
                     if e.ferramenta == "escrever_resumo_projeto"}
            for numero in range(2, 10):
                nome = f"resumo_projeto_{numero}.md"
                if nome not in nomes:
                    plano.etapas.append(Etapa(
                        "Criar resumo factual em novo arquivo", "escrever_resumo_projeto",
                        {**falha.parametros, "nome": nome},
                        dependencias=falha.dependencias, verificacao="arquivo_projeto"))
                    plano.revisao += 1
                    return True
            return False
        if objetivo.parametros.get("tipo") != "preparar_programacao":
            return False
        atual = falha.parametros.get("nome")
        alternativo = {"vscode": "intellij", "intellij": "vscode"}.get(atual)
        if not alternativo or any(e.parametros.get("nome") == alternativo for e in plano.etapas):
            return False
        for etapa in plano.etapas:
            if etapa.status == StatusEtapa.PENDENTE:
                etapa.status = StatusEtapa.IGNORADA
        localizar = Etapa(f"Localizar {alternativo}", "localizar_aplicativo",
                         {"nome": alternativo}, verificacao="executavel")
        abrir = Etapa(f"Abrir {alternativo}", "abrir_aplicativo", {"nome": alternativo},
                      dependencias=(localizar.id,), verificacao="processo")
        plano.etapas.extend((localizar, abrir))
        plano.revisao += 1
        return True

    def cancelar(self, plano: Plano) -> None:
        for etapa in plano.etapas:
            if etapa.status in (StatusEtapa.PENDENTE, StatusEtapa.EXECUTANDO):
                etapa.status = StatusEtapa.CANCELADA

    def pular(self, etapa: Etapa) -> None:
        etapa.status = StatusEtapa.IGNORADA

    def voltar(self, etapa: Etapa) -> None:
        etapa.status = StatusEtapa.PENDENTE

    def adicionar(self, plano: Plano, etapa: Etapa) -> None:
        plano.etapas.append(etapa)
        plano.revisao += 1
