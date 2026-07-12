"""Load and validate YAML recipes using pydantic."""

from importlib.resources import files
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class ParserConfig(BaseModel):
    content_selector: str = "main"
    code_selector: str = "pre code"


class SourceConfig(BaseModel):
    type: Literal["sitemap", "crawl", "local"]
    url: str | None = None
    path: str | None = None
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_url_or_path(self) -> "SourceConfig":
        if self.type in ("sitemap", "crawl") and not self.url:
            raise ValueError(f"source.url required for type '{self.type}'")
        if self.type == "local" and not self.path:
            raise ValueError("source.path required for type 'local'")
        return self


class Recipe(BaseModel):
    id: str
    name: str
    homepage: str
    source: SourceConfig
    parser: ParserConfig = Field(default_factory=ParserConfig)
    canary: dict[str, str] = Field(default_factory=dict)


def load_recipes(extra_dir: Path | None = None) -> list[Recipe]:
    """Load all recipes from the bundled recipes/ dir (plus optional extra_dir)."""
    recipe_files: list[Path] = []

    bundled = files("docwarden.recipes")
    for item in bundled.iterdir():  # type: ignore[union-attr]
        name = str(item)
        if name.endswith(".yaml"):
            recipe_files.append(Path(name))

    if extra_dir:
        recipe_files.extend(sorted(extra_dir.glob("*.yaml")))

    recipes: list[Recipe] = []
    errors: list[str] = []
    for f in recipe_files:
        try:
            data = yaml.safe_load(f.read_text())
            recipes.append(Recipe.model_validate(data))
        except Exception as exc:
            errors.append(f"{f.name}: {exc}")

    if errors:
        raise ValueError("Invalid recipe(s):\n" + "\n".join(errors))

    return recipes


def get_recipe(framework_id: str) -> Recipe:
    for r in load_recipes():
        if r.id == framework_id:
            return r
    raise KeyError(f"No recipe found for '{framework_id}'")
