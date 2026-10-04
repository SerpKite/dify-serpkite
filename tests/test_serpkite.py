from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests
import yaml
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from provider.serpkite import SerpKiteProvider
from tools.common import markdown, search
from tools.news import SerpKiteNewsTool
from tools.search import SerpKiteSearchTool


def response(payload):
    result = Mock()
    result.json.return_value = payload
    return result


@pytest.mark.parametrize('endpoint', ['search', 'news'])
def test_auth_localization_and_response_envelope(endpoint):
    payload = {'results': [{'title': 'Example', 'link': 'https://example.com'}], 'meta': {'credits': 1}}
    with patch('tools.common.requests.get', return_value=response(payload)) as get:
        assert search({'api_key': 'skt_live_test'}, {'query': 'test', 'country': 'gb', 'language': 'en', 'num': 20}, endpoint) == payload
    args, kwargs = get.call_args
    assert args == (f'https://api.serpkite.com/v1/{endpoint}',)
    assert kwargs['headers'] == {'Authorization': 'Bearer skt_live_test'}
    assert kwargs['params'] == {'q': 'test', 'country': 'gb', 'language': 'en', 'num': 20}
    assert kwargs['timeout'] == 90


@pytest.mark.parametrize('num', [0, 101, 1.5, True, '10'])
def test_invalid_count_never_calls_http(num):
    with patch('tools.common.requests.get') as get:
        with pytest.raises(ValueError, match='integer from 1 to 100'):
            search({'api_key': 'test'}, {'query': 'test', 'num': num}, 'search')
        get.assert_not_called()


@pytest.mark.parametrize('params, credentials', [({'query': ''}, {'api_key': 'test'}), ({'query': 'test'}, {})])
def test_missing_required_values_fail_before_network(params, credentials):
    with patch('tools.common.requests.get') as get:
        with pytest.raises(ValueError):
            search(credentials, params, 'search')
        get.assert_not_called()


def test_api_errors_do_not_expose_keys_or_query_urls():
    with patch('tools.common.requests.get', side_effect=requests.HTTPError('secret-key https://api.serpkite.com/v1/search?q=private')):
        with pytest.raises(ValueError) as error:
            search({'api_key': 'secret-key'}, {'query': 'private'}, 'search')
    assert 'secret-key' not in str(error.value)
    assert 'private' not in str(error.value)


def test_markdown_and_empty_results():
    assert markdown({'results': []}) == 'No results found.'
    rendered = markdown({'results': [{'title': 'Example', 'link': 'https://example.com', 'snippet': 'Summary'}]})
    assert '[Example](https://example.com)' in rendered
    assert 'Summary' in rendered


@pytest.mark.parametrize('cls, endpoint', [(SerpKiteSearchTool, 'search'), (SerpKiteNewsTool, 'news')])
def test_dify_invoke_emits_json_and_markdown(cls, endpoint):
    payload = {'results': [{'title': 'Example', 'link': 'https://example.com'}], 'meta': {'credits': 1}}
    tool = SimpleNamespace(runtime=SimpleNamespace(credentials={'api_key': 'test'}), create_json_message=lambda value: ('json', value), create_text_message=lambda value: ('text', value))
    with patch(f'tools.{endpoint}.search', return_value=payload) as api:
        outputs = list(cls._invoke(tool, {'query': 'test'}))
    api.assert_called_once_with({'api_key': 'test'}, {'query': 'test'}, endpoint)
    assert outputs[0] == ('json', payload)
    assert outputs[1][0] == 'text'
    assert 'Example' in outputs[1][1]


def test_credential_check_is_non_billable_and_sanitizes_failures():
    with patch('provider.serpkite.requests.get', return_value=response({})) as get:
        SerpKiteProvider._validate_credentials(None, {'api_key': 'test'})
    assert get.call_args.args == ('https://api.serpkite.com/v1/account',)
    with patch('provider.serpkite.requests.get', side_effect=requests.Timeout('private-key')):
        with pytest.raises(ToolProviderCredentialValidationError) as error:
            SerpKiteProvider._validate_credentials(None, {'api_key': 'private-key'})
    assert 'private-key' not in str(error.value)


def test_runtime_metadata_sources_exist():
    from pathlib import Path
    root = Path(__file__).parent.parent
    manifest = yaml.safe_load((root / 'manifest.yaml').read_text())
    assert (root / manifest['privacy']).is_file()
    provider = yaml.safe_load((root / manifest['plugins']['tools'][0]).read_text())
    for tool in provider['tools']:
        spec = yaml.safe_load((root / tool).read_text())
        assert (root / spec['extra']['python']['source']).is_file()
