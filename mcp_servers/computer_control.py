"""Computer-control MCP server for llm_vtuber.

Gives the VTuber agent the ability to operate and analyze the user's screen:

- Deterministic screen reading: macOS Vision OCR (`extract_screen_text`,
  `find_text_on_screen`) returns exact text positions in screen points,
  so clicks are targeted by code, not by LLM guesses.
- Vision-LLM analysis: `analyze_screen` sends a screenshot to a local
  Ollama vision model (default: gemma3:4b) and returns its answer —
  used to spot mistakes on screen and explain the correct answer.
- Input control: mouse click/move, typing, hotkeys, scrolling via pyautogui.

macOS permissions required (System Settings → Privacy & Security):
- Accessibility: for mouse/keyboard control
- Screen Recording: for screenshots/OCR

Run standalone for a quick check:  uv run python mcp_servers/computer_control.py --self-test
"""

import base64
import io
import json
import os
import sys
import urllib.request

import pyautogui
from mcp.server.fastmcp import FastMCP

pyautogui.FAILSAFE = True  # slam cursor into a screen corner to abort

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "gemma3:4b")
OCR_LANGUAGES = ["ko-KR", "en-US"]
MAX_IMAGE_WIDTH = 1600  # downscale screenshots sent to the vision model

mcp = FastMCP("computer-control")


def _screenshot_png() -> tuple[bytes, int, int]:
    """Capture the screen. Returns (png_bytes, pixel_width, pixel_height)."""
    img = pyautogui.screenshot()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), img.width, img.height


def _ocr(png_bytes: bytes) -> list[dict]:
    """Run macOS Vision OCR. Returns words with normalized bounding boxes."""
    import Vision  # deferred: only available on macOS

    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(
        png_bytes, None
    )
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(OCR_LANGUAGES)
    request.setUsesLanguageCorrection_(True)
    ok = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError("Vision OCR request failed (check Screen Recording permission)")
    results = []
    for obs in request.results() or []:
        candidates = obs.topCandidates_(1)
        if not candidates:
            continue
        bbox = obs.boundingBox()  # normalized, origin at bottom-left
        results.append(
            {
                "text": str(candidates[0].string()),
                "x": bbox.origin.x,
                "y": 1.0 - (bbox.origin.y + bbox.size.height),  # flip to top-left origin
                "w": bbox.size.width,
                "h": bbox.size.height,
            }
        )
    return results


def _to_points(items: list[dict]) -> list[dict]:
    """Convert normalized OCR boxes to clickable screen-point centers."""
    screen_w, screen_h = pyautogui.size()
    out = []
    for it in items:
        out.append(
            {
                "text": it["text"],
                "click_x": round((it["x"] + it["w"] / 2) * screen_w),
                "click_y": round((it["y"] + it["h"] / 2) * screen_h),
            }
        )
    return out


@mcp.tool()
def get_screen_info() -> str:
    """Get screen size in points (the coordinate system used by mouse tools)."""
    w, h = pyautogui.size()
    x, y = pyautogui.position()
    return json.dumps(
        {"screen_width": w, "screen_height": h, "mouse_x": x, "mouse_y": y}
    )


@mcp.tool()
def extract_screen_text() -> str:
    """Read all text visible on screen via OCR (Korean + English).
    Returns a JSON list of {text, click_x, click_y} where click_x/click_y are
    screen-point coordinates of the text center, usable with mouse_click."""
    png, _, _ = _screenshot_png()
    return json.dumps(_to_points(_ocr(png)), ensure_ascii=False)


@mcp.tool()
def find_text_on_screen(query: str) -> str:
    """Find text on screen (case-insensitive substring match) and return the
    matching items with clickable center coordinates. Use this to locate a
    button/menu/link before clicking it."""
    png, _, _ = _screenshot_png()
    matches = [
        it for it in _to_points(_ocr(png)) if query.lower() in it["text"].lower()
    ]
    if not matches:
        return json.dumps(
            {"found": False, "hint": "Text not visible. Try extract_screen_text."},
            ensure_ascii=False,
        )
    return json.dumps({"found": True, "matches": matches}, ensure_ascii=False)


@mcp.tool()
def analyze_screen(question: str) -> str:
    """Take a screenshot and ask a local vision LLM about it. Use this to
    check the user's work on screen, spot mistakes, and explain the correct
    answer. `question` should say what to look at and what to judge."""
    png, w, h = _screenshot_png()
    if w > MAX_IMAGE_WIDTH:
        from PIL import Image

        img = Image.open(io.BytesIO(png))
        img = img.resize((MAX_IMAGE_WIDTH, int(h * MAX_IMAGE_WIDTH / w)))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png = buf.getvalue()
    payload = {
        "model": VISION_MODEL,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": (
                    "다음은 사용자의 현재 화면 스크린샷이다. 질문에 한국어로,"
                    " 구체적인 근거(화면의 어느 부분인지)를 들어 답하라.\n질문: "
                    + question
                ),
                "images": [base64.b64encode(png).decode()],
            }
        ],
    }
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
        return data["message"]["content"]
    except Exception as e:  # deterministic fallback: OCR dump
        ocr_text = " / ".join(it["text"] for it in _ocr(png)[:80])
        return (
            f"[vision model unavailable: {e}] OCR로 읽은 화면 텍스트로 대신 판단하라: "
            + ocr_text
        )


@mcp.tool()
def mouse_click(x: int, y: int, button: str = "left", clicks: int = 1) -> str:
    """Click at screen-point coordinates (x, y). button: left/right/middle,
    clicks: 1 for single, 2 for double. Get coordinates from
    find_text_on_screen or get_screen_info first."""
    w, h = pyautogui.size()
    x, y = max(0, min(x, w - 1)), max(0, min(y, h - 1))
    pyautogui.click(x=x, y=y, button=button, clicks=clicks, interval=0.1)
    return f"clicked {button} x{clicks} at ({x}, {y})"


@mcp.tool()
def mouse_move(x: int, y: int) -> str:
    """Move the mouse cursor to screen-point coordinates (x, y) without clicking."""
    pyautogui.moveTo(x, y, duration=0.2)
    return f"moved to ({x}, {y})"


@mcp.tool()
def type_text(text: str, press_enter: bool = False) -> str:
    """Type text at the current cursor/focus position. Supports Korean and
    other non-ASCII text. Set press_enter=True to hit Enter afterwards."""
    pyautogui.write(text, interval=0.02) if text.isascii() else _type_unicode(text)
    if press_enter:
        pyautogui.press("enter")
    return f"typed {len(text)} chars" + (" + enter" if press_enter else "")


def _type_unicode(text: str) -> None:
    """pyautogui.write can't produce non-ASCII keystrokes — paste instead."""
    import subprocess

    subprocess.run("pbcopy", input=text.encode("utf-8"), check=True)
    pyautogui.hotkey("command", "v")


@mcp.tool()
def press_key(combo: str) -> str:
    """Press a key or hotkey combo, e.g. 'enter', 'tab', 'command+s',
    'command+shift+4'. Keys are separated by '+'."""
    keys = [k.strip().lower() for k in combo.split("+") if k.strip()]
    if not keys:
        return "no keys given"
    if len(keys) == 1:
        pyautogui.press(keys[0])
    else:
        pyautogui.hotkey(*keys)
    return f"pressed {'+'.join(keys)}"


@mcp.tool()
def scroll(amount: int) -> str:
    """Scroll vertically at the current mouse position.
    Positive = up, negative = down. Try ±5 to ±20."""
    pyautogui.scroll(amount)
    return f"scrolled {amount}"


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        print(get_screen_info())
        png, w, h = _screenshot_png()
        print(f"screenshot: {w}x{h}px, {len(png)} bytes")
        words = _to_points(_ocr(png))
        print(f"OCR words: {len(words)}, first 5: {[w['text'] for w in words[:5]]}")
        sys.exit(0)
    mcp.run()
