"""Regression tests for `prompt_injection.resolve_prompt_template`.

The template-level resolver owns un-namespaced `{PLACEHOLDER}` tokens
only. Namespaced runtime tokens like `{USER:HEALTH}` are owned by
`runtime_placeholders.apply_runtime_placeholders` and must survive
this pass untouched (feature 012).
"""

from app.services.prompts.prompt_injection import resolve_prompt_template


def test_resolve_prompt_template_does_not_match_namespaced_tokens() -> None:
    template = "World: {WORLD_NAME} stat: {USER:HEALTH} other: {WORLD:WEATHER}"

    result = resolve_prompt_template(template, WORLD_NAME="Eden")

    # Un-namespaced placeholder substituted; namespaced tokens preserved
    # verbatim for the runtime-placeholder pass downstream.
    assert "Eden" in result
    assert "{USER:HEALTH}" in result
    assert "{WORLD:WEATHER}" in result
