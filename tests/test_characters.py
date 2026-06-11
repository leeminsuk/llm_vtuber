"""Korean character configs must survive the exact switch path the server uses:
read_yaml -> deep_merge onto base character_config -> validate_config."""

import json

import pytest

from .conftest import PROJECT_ROOT
from src.open_llm_vtuber.config_manager.utils import read_yaml, validate_config
from src.open_llm_vtuber.service_context import deep_merge

KO_CHARACTERS = sorted((PROJECT_ROOT / "characters").glob("ko_*.yaml"))
BASE_CONF = (
    "conf.yaml"
    if (PROJECT_ROOT / "conf.yaml").exists()
    else "config_templates/conf.KO.default.yaml"
)
MODEL_NAMES = {
    m["name"] for m in json.loads((PROJECT_ROOT / "model_dict.json").read_text())
}


def _base_config():
    return read_yaml(str(PROJECT_ROOT / BASE_CONF))


def test_five_korean_characters_present():
    assert len(KO_CHARACTERS) == 5, [p.name for p in KO_CHARACTERS]


def test_base_config_is_korean_ready():
    cfg = validate_config(_base_config())
    char = cfg.character_config
    assert char.asr_config.asr_model == "sherpa_onnx_asr"  # offline ASR with Korean
    assert "ko" in str(char.asr_config.sherpa_onnx_asr.sense_voice)  # ko-capable model
    assert char.tts_config.tts_model == "edge_tts"
    assert char.tts_config.edge_tts.voice == "ko-KR-SunHiNeural"
    assert "한국어" in char.persona_prompt


@pytest.mark.parametrize("char_file", KO_CHARACTERS, ids=lambda p: p.stem)
def test_character_switch_validates(char_file):
    base = _base_config()
    alt = read_yaml(str(char_file)).get("character_config")
    assert alt, f"{char_file.name}: no character_config section"
    merged = deep_merge(base["character_config"], alt)
    cfg = validate_config(
        {"system_config": base["system_config"], "character_config": merged}
    )
    char = cfg.character_config
    assert char.live2d_model_name in MODEL_NAMES
    assert "한국어" in char.persona_prompt, f"{char_file.name}: persona must be Korean"
    assert char.tts_config.edge_tts.voice, f"{char_file.name}: no edge-tts voice"


def test_each_character_has_distinct_model_and_voice():
    models, voices = [], []
    base = _base_config()
    for f in KO_CHARACTERS:
        alt = read_yaml(str(f))["character_config"]
        merged = deep_merge(base["character_config"], alt)
        models.append(merged["live2d_model_name"])
        voices.append(merged["tts_config"]["edge_tts"]["voice"])
    assert len(set(models)) == 5, f"models not distinct: {models}"
    assert len(set(voices)) == 5, f"voices not distinct: {voices}"


def test_mcp_enabled_for_computer_use():
    cfg = validate_config(_base_config())
    settings = cfg.character_config.agent_config.agent_settings.basic_memory_agent
    assert settings.use_mcpp is True
    assert "computer-control" in settings.mcp_enabled_servers
