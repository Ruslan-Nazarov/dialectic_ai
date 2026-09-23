import asyncio
import json
import os
import subprocess
import sys

import pytest

from dialectic_ai.integrations.providers import build_llm
from dialectic_ai.core.semantic_validator import LLMSemanticValidator
from dialectic_ai.core.runtime import Goal, MoveType, Proposal, RuntimeState


@pytest.mark.parametrize('name', ['groq', 'cerebras', 'openrouter'])
def test_named_provider_is_never_mock(name, monkeypatch):
    monkeypatch.setenv(name.upper() + '_API_KEY', 'test-placeholder')
    monkeypatch.setenv(name.upper() + '_MODEL', 'test-model')
    monkeypatch.setenv('OPENAI_API_KEY', 'other-provider-key')
    llm = build_llm(name)
    assert type(llm).__name__ == 'OpenAILLM'
    assert llm.api_key == 'test-placeholder'
    assert name in llm.base_url


def test_unknown_provider_rejected():
    with pytest.raises(ValueError, match='Unknown'):
        build_llm('typo-provider')


def test_no_implicit_provider_switch(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setenv('GROQ_API_KEY', 'test-placeholder')
    assert build_llm('openai').base_url == os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
    assert build_llm('openai').api_key == ''


@pytest.mark.parametrize('module, cls', [('openai', 'OpenAILLM'), ('gemini', 'GeminiLLM'), ('gigachat', 'GigaChatLLM')])
def test_provider_import_in_fresh_process(module, cls):
    script = f'import sys; sys.path[:0]={sys.path!r}; from dialectic_ai.integrations.{module}.llm import {cls}; print("ok")'
    result = subprocess.run([sys.executable, '-B', '-c', script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.asyncio
@pytest.mark.parametrize('response', ['{"accepted":"true","reason":"bad"}', '[]', '{}', 'not JSON'])
async def test_semantic_judge_fails_closed(response):
    class Judge:
        async def generate(self, messages):
            return response
    p = Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={'content':'p'}, why_this_move_now='w', expected_goal_contribution='e')
    result = await LLMSemanticValidator(Judge()).validate(p, RuntimeState(), Goal(content='g'))
    assert not result.accepted


@pytest.mark.asyncio
async def test_judge_sees_actual_state():
    class Judge:
        async def generate(self, messages):
            self.prompt = messages[0]['content']
            return '{"accepted":false,"reason":"not substantiated","issues":[]}'
    judge = Judge()
    state = RuntimeState()
    goal = Goal(content='UNIQUE_GOAL')
    state._goals[goal.id] = goal
    p = Proposal(move_type=MoveType.PROPOSE_SIMPLEST, payload={'content':'UNIQUE_PROPOSAL'}, why_this_move_now='w', expected_goal_contribution='e')
    await LLMSemanticValidator(judge).validate(p, state, goal)
    assert 'UNIQUE_GOAL' in judge.prompt and 'UNIQUE_PROPOSAL' in judge.prompt
    assert 'planning' in judge.prompt and 'runtime' in judge.prompt


@pytest.mark.asyncio
async def test_api_mock_run_and_shared_snapshot():
    pytest.importorskip('fastapi')
    pytest.importorskip('uvicorn')
    pytest.importorskip('httpx')
    from fastapi.testclient import TestClient
    from dialectic_ai.api import server
    server.ACTIVE_RUNS['test'] = {'agent_goal':'agent purpose','task':'g','provider':'mock','status':'pending'}
    try:
        await server.background_run_v2('test', 'agent purpose', 'g', 'mock')
        assert server.ACTIVE_RUNS['test']['status'] == 'completed'
        assert server.ACTIVE_RUNS['test']['engine'].agent.goal == 'agent purpose'
        assert next(iter(server.ACTIVE_RUNS['test']['engine'].state._goals.values())).content == 'g'
        with TestClient(server.app) as client:
            response = client.get('/api/state?run_id=test')
            assert response.status_code == 200
            snapshot = response.json()['snapshot']
            assert snapshot['allowed_moves'] == []
            assert snapshot['phase'] == 'executing'
            assert len(snapshot['roadmaps']) == 1
            assert client.get('/api/state?run_id=missing').status_code == 404
            assert client.post('/api/run', json={'agent_goal':'purpose','task':'   '}).status_code == 422
            assert client.post('/api/run', json={'agent_goal':'purpose','task':'g','provider':'typo'}).status_code == 422
            before = len(server.ACTIVE_RUNS)
            greeting = client.post('/api/run', json={'agent_goal':'architecture analyst','task':'привет','provider':'mock'})
            assert greeting.status_code == 200
            assert greeting.json()['kind'] == 'conversation'
            assert greeting.json()['run_id'] is None
            assert len(server.ACTIVE_RUNS) == before
    finally:
        server.ACTIVE_RUNS.pop('test', None)


def test_generated_agent_handles_quotes_and_newlines(tmp_path):
    from dialectic_ai.cli.creator import generate_agent
    import ast
    target = tmp_path / 'example.py'
    generate_agent('A "quoted" name', 'Line one\n"Quoted" task', ['web_search'], 'mock', True, str(target), skip_refine=True)
    ast.parse(target.read_text(encoding='utf-8'))


def test_gigachat_uses_verified_tls(monkeypatch):
    import ssl
    from dialectic_ai.integrations.gigachat.llm import GigaChatLLM
    monkeypatch.delenv('GIGACHAT_CA_BUNDLE', raising=False)
    contexts = []
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self): return b'{"access_token":"test","expires_at":9999999999999}'
    def urlopen(req, *, context, timeout):
        contexts.append(context)
        return Response()
    monkeypatch.setattr('urllib.request.urlopen', urlopen)
    assert GigaChatLLM(auth_key='test')._get_access_token() == 'test'
    assert contexts[0].verify_mode == ssl.CERT_REQUIRED
    assert contexts[0].check_hostname


@pytest.mark.asyncio
async def test_file_tools_confine_paths_and_report_failures(tmp_path, monkeypatch):
    from dialectic_ai.tools.file_editor import read_file, write_file
    monkeypatch.setenv('DIALECTIC_WORKSPACE', str(tmp_path))
    for path in ['../escape.txt', '.env']:
        result = await write_file().execute({'path':path, 'content':'data'})
        assert not result.success
    result = await write_file().execute({'path':'report.txt', 'content':'verified'})
    assert result.success
    assert (await read_file().execute({'path':'report.txt'})).content == 'verified'
    assert not (await read_file().execute({'path':'missing.txt'})).success


@pytest.mark.asyncio
async def test_trace_evaluator_uses_latest_run(tmp_path):
    from dialectic_ai.agent import DialecticalAgent
    from dialectic_ai.core.logger import DevelopmentLogger
    from dialectic_ai.core.schema import AgentInput
    from dialectic_ai.engine import DialecticalEngine
    from dialectic_ai.observability.evaluator import AgentEvaluator
    from dialectic_ai.observability.tracer import TraceReader
    from dialectic_ai.tools import web_search
    trace = tmp_path / 'trace.jsonl'
    engine = DialecticalEngine(DialecticalAgent('demo', tools=[web_search()]), logger=DevelopmentLogger(trace_path=str(trace)))
    first = await engine.run(AgentInput(user_message='demo'))
    engine.max_iterations = 0
    second = await engine.run(AgentInput(user_message='unfinished'))
    evaluator = AgentEvaluator(TraceReader(str(trace)))
    assert evaluator.evaluate_session(first.run_id).completed
    assert not evaluator.evaluate_session().completed
    assert evaluator.evaluate_session().session_id == second.run_id


def test_usage_hook_normalizes_provider_payloads():
    from dialectic_ai.core.llm import MockLLM
    captured = []
    llm = MockLLM()
    llm.set_usage_callback('gemini', lambda provider, usage: captured.append((provider, usage)))
    usage = llm._record_usage({'promptTokenCount': 12, 'candidatesTokenCount': 5, 'totalTokenCount': 17})
    assert usage.total_tokens == 17
    assert captured[0][0] == 'gemini'
    assert captured[0][1].prompt_tokens == 12


def test_dashboard_records_exact_usage_by_provider(tmp_path, monkeypatch):
    pytest.importorskip('fastapi')
    pytest.importorskip('uvicorn')
    from dialectic_ai.api import server
    from dialectic_ai.core.schema import ModelUsage
    metrics_file = tmp_path / 'metrics.json'
    metrics_file.write_text(json.dumps({
        'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0,
        'total_calls': 0, 'estimated': False, 'exact_calls': 0,
        'estimated_calls': 0, 'last_updated': None, 'by_provider': {}
    }), encoding='utf-8')
    monkeypatch.setattr(server, 'METRICS_FILE', str(metrics_file))
    server.record_model_usage('gigachat', ModelUsage(prompt_tokens=90, completion_tokens=10, total_tokens=100))
    metrics = server.load_token_metrics()
    assert metrics['total_tokens'] == 100
    assert metrics['exact_calls'] == 1
    assert metrics['estimated'] is False
    assert metrics['by_provider']['gigachat']['completion_tokens'] == 10
