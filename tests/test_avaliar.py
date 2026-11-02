"""Verifica o código local, com o SDK real e HTTP simulado; não chama a ElevenLabs."""

import copy
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import httpx
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError
from elevenlabs.types.get_test_suite_invocation_response_model import GetTestSuiteInvocationResponseModel

import avaliar


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.cenario = avaliar.ler_json(avaliar.BASE / "cenarios" / "01-duvida-ingles.json")
        self.catalogo = avaliar.ler_json(avaliar.BASE / "fixtures" / "catalogo.json")
        self.payload = avaliar.preparar(self.cenario, self.catalogo, "tool_teste")
        self.entradas = {"cenario": self.cenario, "catalogo": self.catalogo, "cadastro": self.payload}
        self.resultado = {
            "id": "suite_local", "agent_id": "agent_local", "branch_id": "branch_local",
            "version_id": "version_local", "ran_against_draft": False,
            "test_runs": [{
                "test_run_id": "run_local", "test_invocation_id": "suite_local",
                "agent_id": "agent_local", "test_id": "test_local", "status": "passed",
                "condition_result": {"result": "success", "rationale": {"summary": "Dados corretos."}},
                "agent_responses": [{
                    "role": "agent", "time_in_call_secs": 1,
                    "message": "R$ 220, terças e quintas, das 19h às 20h.",
                    "tool_calls": [{"tool_name": "consultar_cursos", "request_id": "req_local",
                                    "params_as_json": "{}", "tool_has_been_called": True}],
                    "tool_results": [{"tool_name": "consultar_cursos", "is_error": False,
                                      "request_id": "req_local", "tool_has_been_called": True,
                                      "result_value": json.dumps(self.catalogo)}],
                }],
            }],
        }

    def client(self, handler):
        return ElevenLabs(api_key="chave-apenas-para-teste-local", httpx_client=httpx.Client(
            transport=httpx.MockTransport(handler)))

    def test_sdk_serializa_mock_run_e_consulta_sem_rede(self):
        requests = []
        def handler(req):
            requests.append((req.method, req.url.path))
            if req.url.path.endswith("/create"):
                body = json.loads(req.content)
                self.assertEqual(body["type"], "simulation")
                self.assertEqual(body["tool_mock_config"]["fallback_strategy"], "raise_error")
                mock = body["tool_mock_overrides"]["tool_teste"][0]
                self.assertEqual(json.loads(mock["mock_result"]), self.catalogo)
                return httpx.Response(200, json={"id": "test_local"})
            if req.method == "POST":
                body = json.loads(req.content)
                self.assertEqual(body["repeat_count"], 1)
                self.assertEqual(body["tests"], [{"test_id": "test_local"}])
                self.assertEqual(body["branch_id"], "branch_local")
                pending = copy.deepcopy(self.resultado)
                pending["test_runs"][0]["status"] = "pending"
                return httpx.Response(200, json=pending)
            return httpx.Response(200, json=self.resultado)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp, redirect_stdout(StringIO()):
            state = Path(tmp) / "estado.json"
            client = self.client(handler)
            started = avaliar.iniciar(client, "agent_local", "branch_local", self.payload, state, self.entradas)
            result = avaliar.aguardar(client, started, segundos=1, intervalo=0)
            summary, folder = avaliar.registrar(Path(tmp), result, self.cenario, self.catalogo, self.payload)
            self.assertEqual(summary["resultado"], "APROVADO")
            self.assertTrue((folder / "conversa.txt").exists())
            self.assertIn("version_local", (folder / "resumo.csv").read_text(encoding="utf-8-sig"))
            self.assertNotIn("chave-apenas-para-teste-local", (folder / "resultado-completo.json").read_text())
            self.assertEqual(sum(m == "POST" for m, _ in requests), 2)
            self.assertEqual(avaliar.ler_json(state)["ultima_execucao"], "suite_local")

    def test_aprovacao_sem_evidencia_nao_vira_aprovacao_final(self):
        self.resultado["test_runs"][0]["agent_responses"] = []
        summary = avaliar.resumir(self.resultado, self.cenario, self.catalogo)
        self.assertEqual(summary["resultado"], "REVISAR_EVIDENCIA")

    def test_mock_errado_ou_erro_de_ferramenta_nao_aprova(self):
        result = self.resultado["test_runs"][0]["agent_responses"][0]["tool_results"][0]
        result["result_value"] = '{"status": "ok", "total": 0, "cursos": []}'
        self.assertEqual(avaliar.resumir(self.resultado, self.cenario, self.catalogo)["resultado"], "REVISAR_EVIDENCIA")
        result["result_value"] = json.dumps(self.catalogo)
        result["is_error"] = True
        self.assertFalse(avaliar.resumir(self.resultado, self.cenario, self.catalogo)["mock_confirmado"])

    def test_pendente_ou_falha_tecnica_nao_aprova(self):
        for status, grade in [("pending", "success"), ("failed", "unknown")]:
            self.resultado["test_runs"][0]["status"] = status
            self.resultado["test_runs"][0]["condition_result"]["result"] = grade
            self.assertEqual(avaliar.resumir(self.resultado, self.cenario, self.catalogo)["resultado"], "INCONCLUSIVO")
        self.resultado["test_runs"][0]["status"] = "pending"
        response = GetTestSuiteInvocationResponseModel(**self.resultado)
        client = self.client(lambda r: self.fail("Timeout local não deveria consultar a rede"))
        self.assertEqual(avaliar.aguardar(client, response, segundos=0)["test_runs"][0]["status"], "pending")

    def test_preview_nao_instancia_cliente(self):
        with patch.object(avaliar, "ElevenLabs", side_effect=AssertionError("Não deve criar cliente")), redirect_stdout(StringIO()):
            self.assertEqual(avaliar.main(["--preview"]), 0)

    def test_post_rejeitado_pode_corrigir_chave_sem_travar(self):
        self.verificar_falha_post(401, False)

    def test_post_incerto_nao_repete_e_preserva_bloqueio(self):
        self.verificar_falha_post(500, True)

    def verificar_falha_post(self, status, esperando):
        count = 0
        def handler(req):
            nonlocal count
            count += 1
            return httpx.Response(status, json={"detail": "Erro de teste local"})
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp, redirect_stdout(StringIO()):
            state = Path(tmp) / "estado.json"
            assinatura = __import__("hashlib").sha256(json.dumps(self.payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            avaliar.salvar_json(state, {"cadastros": {assinatura: "test_local"}})
            with self.assertRaises(ApiError):
                avaliar.iniciar(self.client(handler), "agent_local", "branch_local", self.payload, state, self.entradas)
            self.assertEqual(count, 1)
            self.assertEqual(avaliar.ler_json(state)["aguardando"], esperando)
            if esperando:
                with self.assertRaisesRegex(ValueError, "pendente"):
                    avaliar.iniciar(self.client(handler), "agent_local", "branch_local", self.payload, state, self.entradas)
                self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
