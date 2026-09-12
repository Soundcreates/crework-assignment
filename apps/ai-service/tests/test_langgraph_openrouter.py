from app.ai.openrouter import (
    build_chat_openrouter,
    resolve_openrouter_api_key,
    resolve_openrouter_model,
)
from app.config import Settings
from app.workflows.discovery_graph import (
    build_discovery_graph,
    route_after_dedupe,
    route_after_search,
)


def test_resolve_openrouter_api_key_prefers_openrouter_key():
    settings = Settings(openrouter_api_key="sk-or-preferred", llm_api_key="fallback")
    assert resolve_openrouter_api_key(settings) == "sk-or-preferred"


def test_resolve_openrouter_api_key_falls_back_to_llm_api_key():
    settings = Settings(openrouter_api_key="", llm_api_key="sk-or-from-llm")
    assert resolve_openrouter_api_key(settings) == "sk-or-from-llm"


def test_resolve_openrouter_model_uses_settings():
    settings = Settings(llm_model="openrouter/free")
    assert resolve_openrouter_model(settings) == "openrouter/free"


def test_build_chat_openrouter_returns_none_without_key():
    settings = Settings(openrouter_api_key="", llm_api_key="")
    assert build_chat_openrouter(settings) is None


def test_langgraph_discovery_graph_compiles():
    app = build_discovery_graph()
    assert app is not None


def test_route_after_dedupe():
    assert route_after_dedupe({"discovery_only": True}) == "persist_discovered"
    assert route_after_dedupe({"discovery_only": False}) == "enrich_companies"
    assert route_after_dedupe({}) == "enrich_companies"


def test_route_after_search():
    assert route_after_search({"error": "boom", "search_results": []}) == "finalize"
    assert route_after_search({"error": None, "search_results": [{"url": "x"}]}) == "resolve"
