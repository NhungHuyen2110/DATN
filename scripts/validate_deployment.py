"""Offline structural checks, not a substitute for Docker build/runtime tests."""
import ast
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def validate():
    config = yaml.safe_load((ROOT / 'compose.yaml').read_text(encoding='utf-8'))
    services = config['services']
    for name, dockerfile in [('frontend', 'frontend/Dockerfile'), ('business-api', 'backend/Dockerfile'),
                             ('ai-api', 'AI/Dockerfile')]:
        assert services[name]['build']['dockerfile'] == dockerfile
        assert (ROOT / dockerfile).is_file()
        assert 'HEALTHCHECK' in (ROOT / dockerfile).read_text()
    assert len({services[key]['build']['dockerfile'] for key in ('frontend', 'business-api', 'ai-api')}) == 3
    for name in ('postgres', 'qdrant', 'neo4j', 'ollama'):
        assert not services[name].get('ports'), f'{name} must stay private'
        assert services[name]['volumes']
    for name, service in services.items():
        assert not service.get('container_name'), 'Do not collide with pre-existing containers'
        assert not service.get('privileged')
        assert service.get('mem_limit')
        assert service['logging']['options']['max-size']
        if name != 'reverse-proxy':
            assert not service.get('ports')
    assert config['networks']['business-data']['internal']
    assert config['networks']['ai-data']['internal']
    assert services['business-api']['environment']['PRODUCT_INDEX_SYNC_ENABLED'] == 'false'
    assert 'neo4j' not in services['business-api'].get('depends_on', {})
    assert 'ai-api' not in services['business-api'].get('depends_on', {})
    tree = ast.parse((ROOT / 'backend/app/main.py').read_text(encoding='utf-8-sig'))
    decorated = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    routes = {arg.value for node in decorated for dec in node.decorator_list if isinstance(dec, ast.Call)
              for arg in dec.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)}
    assert {'/health/live', '/health/ready'}.issubset(routes)
    return {'structural_checks': 'passed', 'services': list(services),
            'docker_build': 'not_executed', 'container_runtime': 'not_executed',
            'fault_injection': 'not_executed'}


if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
