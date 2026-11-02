"""Confere autenticação com uma consulta ao agente, sem iniciar avaliações."""

import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError


BASE = Path(__file__).resolve().parent


def main():
    # Usa a mesma origem de configuração e a mesma precedência do runner.
    load_dotenv(BASE / ".env")
    chave = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not chave:
        print("Preencha ELEVENLABS_API_KEY no .env local e salve o arquivo.")
        return 2
    agent_id = os.getenv("ELEVENLABS_AGENT_ID", "").strip()
    branch_id = os.getenv("ELEVENLABS_BRANCH_ID", "").strip()
    if not agent_id or not branch_id:
        print("Preencha ELEVENLABS_AGENT_ID e ELEVENLABS_BRANCH_ID no .env local.")
        return 2
    try:
        client = ElevenLabs(api_key=chave, timeout=30)
        agente = client.conversational_ai.agents.get(
            agent_id=agent_id, branch_id=branch_id,
            request_options={"max_retries": 0},
        )
    except ApiError as exc:
        orientacoes = {
            401: "A chave não foi aceita. Confira se a substituta foi salva no .env e está ativa.",
            403: "Acesso negado. Confira ElevenAgents: Write e eventuais restrições por IP.",
            404: "Agente ou branch não encontrados. Confira os identificadores e o workspace.",
            429: "A API limitou a consulta. Aguarde antes de tentar novamente.",
        }
        print(f"HTTP {exc.status_code}: {orientacoes.get(exc.status_code, 'A consulta não foi concluída.')}")
        return 2
    except Exception as exc:
        # Não exibe corpos HTTP, cabeçalhos ou valores das credenciais.
        print(f"Falha na consulta ({type(exc).__name__}). Confira a conexão e a instalação do SDK.")
        return 2
    print("Acesso confirmado: autenticação e leitura do agente funcionando.")
    print("Agente:", agente.name)
    print("Nenhuma simulação iniciada; nenhuma configuração alterada.")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
