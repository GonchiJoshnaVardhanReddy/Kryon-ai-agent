"""Tests for the subagent registry."""
from __future__ import annotations

import pytest

from kryon.subagents import list_subagents
from kryon.subagents.registry import SUBAGENTS, get_subagent_class


def test_all_8_subagents_registered() -> None:
    expected = {
        "recon-passive",
        "recon-active",
        "analysis-hypothesis",
        "exploit",
        "post-exploit",
        "verify",
        "blue-team",
        "report",
    }
    assert set(SUBAGENTS.keys()) == expected


def test_get_subagent_class() -> None:
    cls = get_subagent_class("recon-passive")
    assert cls.name == "recon-passive"


def test_get_subagent_class_all_8() -> None:
    for name in (
        "recon-passive",
        "recon-active",
        "analysis-hypothesis",
        "exploit",
        "post-exploit",
        "verify",
        "blue-team",
        "report",
    ):
        cls = get_subagent_class(name)
        assert cls.name == name


def test_get_subagent_class_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown subagent"):
        get_subagent_class("nonexistent")


def test_list_subagents() -> None:
    subagents = list_subagents()
    assert len(subagents) == 8
    assert all("name" in s and "description" in s for s in subagents)


def test_subagent_classes_have_required_attrs() -> None:
    """Every registered subagent has name, description, SYSTEM_PROMPT, OUTPUT_SCHEMA."""
    for cls in SUBAGENTS.values():
        assert isinstance(cls.name, str) and cls.name
        assert isinstance(cls.description, str) and cls.description
        assert isinstance(cls.SYSTEM_PROMPT, str) and len(cls.SYSTEM_PROMPT) > 200
        assert issubclass(cls.OUTPUT_SCHEMA, __import__("pydantic").BaseModel)
