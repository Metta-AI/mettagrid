import pytest
from pydantic import ValidationError

from mettagrid.base_config import LENIENT_CONTEXT, Config


class Inner(Config):
    x: int = 0


class Outer(Config):
    inner: Inner = Inner()
    name: str = "test"


def test_strict_rejects_extra_fields():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Inner(x=1, unknown_field=2)


def test_strict_rejects_extra_fields_nested():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Outer.model_validate({"inner": {"x": 1, "unknown_field": 2}})


def test_lenient_ignores_extra_fields():
    result = Inner.model_validate({"x": 1, "unknown_field": 2}, context=LENIENT_CONTEXT)
    assert result.x == 1
    assert not hasattr(result, "unknown_field")


def test_lenient_ignores_extra_fields_nested():
    result = Outer.model_validate(
        {"inner": {"x": 1, "future_field": True}, "name": "hello", "new_top_field": "ignored"},
        context=LENIENT_CONTEXT,
    )
    assert result.inner.x == 1
    assert result.name == "hello"


def test_lenient_json():
    result = Outer.model_validate_json(
        '{"inner": {"x": 5, "extra": true}, "name": "ok", "also_extra": 1}',
        context=LENIENT_CONTEXT,
    )
    assert result.inner.x == 5
    assert result.name == "ok"


def test_strict_allows_valid_fields():
    result = Inner(x=42)
    assert result.x == 42


def test_non_dict_context_does_not_crash():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Inner.model_validate({"x": 1, "extra": 2}, context="not-a-dict")
