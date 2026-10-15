"""Adaptador opcional de diálogo: nenhum detalhe do fornecedor chega ao Agent Core."""

from __future__ import annotations

import logging
import os
import json

log = logging.getLogger("yasm.agente")


class DialogoGroq:
    def propor_plano(self, texto: str, ferramentas: dict[str, dict]) -> dict | None:
        """Sugere etapas estruturadas usando somente as ferramentas fornecidas."""
        import ia_yasm

        if not ia_yasm.disponivel() or not ferramentas:
            return None
        try:
            cliente = ia_yasm.cliente
            if hasattr(cliente, "with_options"):
                cliente = cliente.with_options(timeout=1.6, max_retries=0)
            instrucao = (
                "Você propõe um plano curto para uma assistente de desenvolvimento. "
                "Responda apenas JSON no formato {\"etapas\":[{\"ferramenta\":\"nome\","
                "\"parametros\":{...}}]}. Use de 1 a 6 etapas sequenciais. "
                "Use exclusivamente as ferramentas abaixo e todos os seus parâmetros exatos. "
                "Represente TODAS as ações solicitadas, na ordem. "
                "Não invente caminhos, nomes de arquivo ou resultados; caminhos devem vir literalmente "
                "do pedido. Se faltar uma capacidade ou informação, responda {\"via\":\"esclarecer\"}. "
                "Ferramentas: " + json.dumps(ferramentas, ensure_ascii=False))
            resposta = cliente.chat.completions.create(
                model=os.environ.get("YASM_DIALOGUE_MODEL", "llama-3.1-8b-instant"),
                messages=[{"role": "system", "content": instrucao},
                          {"role": "user", "content": texto[:1000]}],
                max_tokens=360, temperature=0,
                response_format={"type": "json_object"},
            )
            dados = json.loads(resposta.choices[0].message.content or "")
            return dados if isinstance(dados, dict) else None
        except Exception as erro:
            log.debug("[AGENTE] Plano semântico indisponível: %s", erro)
            return None

    def classificar(self, texto: str, historico: list[dict[str, str]],
                   operacoes: dict[str, dict]) -> dict | None:
        """Propõe apenas operações suportadas; o núcleo valida antes de executar."""
        import ia_yasm

        if not ia_yasm.disponivel():
            return None
        try:
            cliente = ia_yasm.cliente
            if hasattr(cliente, "with_options"):
                cliente = cliente.with_options(timeout=1.4, max_retries=0)
            mensagens = [{"role": "system", "content": (
                "Classifique o pedido para a Yasmin. Responda SOMENTE JSON. "
                "Operações permitidas: " + json.dumps(operacoes, ensure_ascii=False) + ". "
                "Se nenhuma servir, escolha via conversa ou esclarecer. "
                "Não suponha autorização para executar ações não solicitadas. "
                "Exemplos: {\"operacao\":\"preparar_programacao\",\"linguagem\":\"java\"}; "
                "{\"via\":\"conversa\"}." )}]
            for item in historico[-4:]:
                if isinstance(item, dict) and item.get("texto"):
                    if item.get("tipo") == "usuario" and str(item["texto"]).strip() == texto.strip():
                        continue
                    mensagens.append({"role": "user" if item.get("tipo") == "usuario" else "assistant",
                                      "content": str(item["texto"])[:350]})
            mensagens.append({"role": "user", "content": texto[:800]})
            resposta = cliente.chat.completions.create(
                model=os.environ.get("YASM_DIALOGUE_MODEL", "llama-3.1-8b-instant"),
                messages=mensagens, max_tokens=100, temperature=0,
                response_format={"type": "json_object"},
            )
            dados = json.loads(resposta.choices[0].message.content or "")
            return dados if isinstance(dados, dict) else None
        except Exception as erro:
            log.debug("[AGENTE] Classificação semântica indisponível: %s", erro)
            return None

    def responder(self, mensagens: list[dict[str, str]]) -> str | None:
        import ia_yasm

        if not ia_yasm.disponivel():
            return None
        try:
            cliente = ia_yasm.cliente
            if hasattr(cliente, "with_options"):
                cliente = cliente.with_options(timeout=1.8, max_retries=0)
            resposta = cliente.chat.completions.create(
                model=os.environ.get("YASM_DIALOGUE_MODEL", "llama-3.1-8b-instant"),
                messages=mensagens, max_tokens=220, temperature=0.5,
            )
            return (resposta.choices[0].message.content or "").strip() or None
        except Exception as erro:
            log.debug("[AGENTE] Diálogo remoto indisponível: %s", erro)
            return None
