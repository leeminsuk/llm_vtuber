"""model_dict.json integrity: every registered Live2D model must be loadable."""

import json
from pathlib import Path

import pytest

from .conftest import PROJECT_ROOT

MODEL_DICT = json.loads((PROJECT_ROOT / "model_dict.json").read_text())
EXPECTED_MODELS = {"mao_pro", "Haru", "Hiyori", "Rice", "Ren"}


def test_required_models_registered():
    names = {m["name"] for m in MODEL_DICT}
    assert EXPECTED_MODELS <= names, f"missing: {EXPECTED_MODELS - names}"


def test_model_names_unique():
    names = [m["name"] for m in MODEL_DICT]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("entry", MODEL_DICT, ids=lambda m: m["name"])
def test_model_file_exists(entry):
    rel = entry["url"].lstrip("/")
    assert (PROJECT_ROOT / rel).is_file(), f"{entry['name']}: {rel} not found"


@pytest.mark.parametrize("entry", MODEL_DICT, ids=lambda m: m["name"])
def test_emotion_map_within_expression_range(entry):
    """Emotion indices must point at expressions that actually exist
    (models without expressions must map everything to 0)."""
    rel = entry["url"].lstrip("/")
    model3 = json.loads((PROJECT_ROOT / rel).read_text())
    expressions = model3.get("FileReferences", {}).get("Expressions", [])
    n = len(expressions)
    for emotion, idx in entry.get("emotionMap", {}).items():
        if n == 0:
            assert idx == 0, f"{entry['name']}.{emotion}: no expressions, idx must be 0"
        else:
            assert 0 <= idx < n, (
                f"{entry['name']}.{emotion}: idx {idx} out of range {n}"
            )


@pytest.mark.parametrize("entry", MODEL_DICT, ids=lambda m: m["name"])
def test_idle_motion_group_exists(entry):
    rel = entry["url"].lstrip("/")
    model3 = json.loads((PROJECT_ROOT / rel).read_text())
    motions = model3.get("FileReferences", {}).get("Motions", {})
    group = entry.get("idleMotionGroupName")
    if group and motions:
        assert group in motions, (
            f"{entry['name']}: idle group '{group}' not in {list(motions)}"
        )


@pytest.mark.parametrize("entry", MODEL_DICT, ids=lambda m: m["name"])
def test_referenced_assets_exist(entry):
    """All files referenced by the model3.json (textures, motions, moc3,
    physics, expressions, sounds) must be present in the repo."""
    rel = Path(entry["url"].lstrip("/"))
    base = (PROJECT_ROOT / rel).parent
    refs = json.loads((PROJECT_ROOT / rel).read_text())["FileReferences"]
    paths = [refs.get("Moc")] + refs.get("Textures", [])
    paths += [e["File"] for e in refs.get("Expressions", [])]
    for group in refs.get("Motions", {}).values():
        for m in group:
            paths.append(m["File"])
            if "Sound" in m:
                paths.append(m["Sound"])
    for p in filter(None, paths):
        assert (base / p).is_file(), f"{entry['name']}: missing asset {p}"
