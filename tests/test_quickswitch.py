"""Quick character-switch bar: HTML injection + asset sanity."""

from .conftest import PROJECT_ROOT
from src.open_llm_vtuber.server import QUICKSWITCH_TAG, inject_quickswitch

INDEX = (PROJECT_ROOT / "frontend" / "index.html").read_text()


def test_injects_before_app_bundle():
    """The hook must be a classic script placed before the module script,
    otherwise it cannot wrap window.WebSocket in time."""
    out = inject_quickswitch(INDEX)
    assert QUICKSWITCH_TAG in out
    assert out.index(QUICKSWITCH_TAG) < out.index('<script type="module"')


def test_injection_is_idempotent():
    once = inject_quickswitch(INDEX)
    assert inject_quickswitch(once) == once


def test_injection_without_module_marker_falls_back_to_head():
    out = inject_quickswitch("<html><head></head><body></body></html>")
    assert QUICKSWITCH_TAG in out


def test_quickswitch_asset_served_from_web_tool():
    js = (PROJECT_ROOT / "web_tool" / "quickswitch.js").read_text()
    # must speak the same protocol as the settings dialog
    assert "switch-config" in js
    assert "fetch-configs" in js
    assert "set-model-and-conf" in js
    # all five Korean presets get a labeled chip
    for conf in ["ko_yuna", "ko_hana", "ko_sora", "ko_rin", "ko_mao"]:
        assert conf in js


def test_unified_model_is_gemma4():
    """Template, vision tool and docs must agree on the single local model."""
    tpl = (PROJECT_ROOT / "config_templates" / "conf.KO.default.yaml").read_text()
    cc = (PROJECT_ROOT / "mcp_servers" / "computer_control.py").read_text()
    readme = (PROJECT_ROOT / "README.md").read_text()
    assert "gemma4:12b" in tpl
    assert '"gemma4:12b"' in cc
    assert "gemma4:12b" in readme
