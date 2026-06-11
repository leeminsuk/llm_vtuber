"""computer-control MCP server: tool discovery through the project's own
MCP client, plus deterministic OCR pipeline checks (no LLM involved)."""

import asyncio
import io
import json
import sys

import pytest

needs_mac = pytest.mark.skipif(sys.platform != "darwin", reason="macOS Vision OCR")

EXPECTED_TOOLS = {
    "get_screen_info",
    "extract_screen_text",
    "find_text_on_screen",
    "analyze_screen",
    "mouse_click",
    "mouse_move",
    "type_text",
    "press_key",
    "scroll",
}


def test_server_registered_in_config():
    from .conftest import PROJECT_ROOT

    cfg = json.loads((PROJECT_ROOT / "mcp_servers.json").read_text())
    assert "computer-control" in cfg["mcp_servers"]


def test_tool_discovery_via_olv_adapter():
    """OLV's ToolAdapter must spawn the server and list all 9 tools —
    the same path the agent uses at runtime."""
    from src.open_llm_vtuber.mcpp.server_registry import ServerRegistry
    from src.open_llm_vtuber.mcpp.tool_adapter import ToolAdapter

    async def run():
        adapter = ToolAdapter(server_registery=ServerRegistry())
        _, openai_tools, claude_tools = await adapter.get_tools(["computer-control"])
        return openai_tools, claude_tools

    openai_tools, claude_tools = asyncio.run(run())
    names = {t["function"]["name"] for t in openai_tools}
    assert names == EXPECTED_TOOLS
    assert len(claude_tools) == len(EXPECTED_TOOLS)


@needs_mac
def test_ocr_synthetic_image():
    """Vision OCR must find rendered text and return top-left-normalized boxes."""
    from PIL import Image, ImageDraw

    import computer_control as cc

    img = Image.new("RGB", (800, 160), "white")
    ImageDraw.Draw(img).text((40, 60), "SAVE BUTTON open file", fill="black")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    words = cc._ocr(buf.getvalue())
    joined = " ".join(w["text"] for w in words)
    assert "SAVE" in joined and "open" in joined
    for w in words:
        assert 0 <= w["x"] <= 1 and 0 <= w["y"] <= 1


@needs_mac
def test_to_points_converts_to_screen_coordinates():
    import computer_control as cc
    import pyautogui

    sw, sh = pyautogui.size()
    pts = cc._to_points([{"text": "t", "x": 0.5, "y": 0.5, "w": 0.0, "h": 0.0}])
    assert pts[0]["click_x"] == round(sw / 2)
    assert pts[0]["click_y"] == round(sh / 2)


def test_get_screen_info_shape():
    import computer_control as cc

    info = json.loads(cc.get_screen_info())
    assert {"screen_width", "screen_height", "mouse_x", "mouse_y"} <= set(info)
    assert info["screen_width"] > 0


def test_analyze_screen_has_deterministic_fallback(monkeypatch):
    """When the vision model is unreachable, analyze_screen must still return
    a usable OCR-based answer instead of raising."""
    import computer_control as cc

    monkeypatch.setattr(cc, "OLLAMA_BASE_URL", "http://localhost:1")
    out = cc.analyze_screen("화면에 뭐가 보여?")
    assert "vision model unavailable" in out
