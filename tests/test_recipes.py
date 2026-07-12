"""Test recipe loading and validation."""

import pytest
from pydantic import ValidationError

from docwarden.recipes import Recipe, load_recipes


def test_all_shipped_recipes_load():
    recipes = load_recipes()
    assert len(recipes) >= 3
    ids = {r.id for r in recipes}
    assert "fastapi" in ids
    assert "react" in ids
    assert "nextjs" in ids


def test_recipe_has_required_fields():
    recipes = load_recipes()
    for r in recipes:
        assert r.id
        assert r.name
        assert r.homepage
        assert r.source.url or r.source.path


def test_invalid_source_type_rejected():
    with pytest.raises(ValidationError):
        Recipe.model_validate(
            {
                "id": "bad",
                "name": "Bad",
                "homepage": "https://example.com",
                "source": {"type": "ftp", "url": "https://example.com/sitemap.xml"},
            }
        )


def test_sitemap_without_url_rejected():
    with pytest.raises(ValidationError):
        Recipe.model_validate(
            {
                "id": "bad",
                "name": "Bad",
                "homepage": "https://example.com",
                "source": {"type": "sitemap"},
            }
        )


def test_local_without_path_rejected():
    with pytest.raises(ValidationError):
        Recipe.model_validate(
            {
                "id": "bad",
                "name": "Bad",
                "homepage": "https://example.com",
                "source": {"type": "local"},
            }
        )


def test_parser_defaults():
    r = Recipe.model_validate(
        {
            "id": "test",
            "name": "Test",
            "homepage": "https://example.com",
            "source": {"type": "sitemap", "url": "https://example.com/sitemap.xml"},
        }
    )
    assert r.parser.content_selector == "main"
    assert r.parser.code_selector == "pre code"
