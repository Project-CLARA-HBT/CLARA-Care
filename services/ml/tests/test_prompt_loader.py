from pathlib import Path

import pytest

from clara_ml.prompts.loader import PromptLoader


def test_prompt_loader_reads_yaml_templates():
    base = Path(__file__).resolve().parents[1] / "src" / "clara_ml" / "prompts" / "templates"
    loader = PromptLoader(base)
    prompt = loader.load("normal_user", "selfmed_ddi_check")
    assert prompt["role"] == "normal_user"
    assert "template" in prompt


def test_prompt_loader_rejects_path_traversal_role():
    base = Path(__file__).resolve().parents[1] / "src" / "clara_ml" / "prompts" / "templates"
    loader = PromptLoader(base)
    with pytest.raises(KeyError):
        loader.load("../secret", "steal")
