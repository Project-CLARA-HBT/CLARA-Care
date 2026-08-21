from __future__ import annotations

try:
    from langchain_core.prompts import PromptTemplate
except Exception:  # pragma: no cover - fallback cho môi trường chưa có langchain_core
    PromptTemplate = None

def build_prompt(role: str, intent: str, template: str, variables: dict[str, str]) -> str:
    """Render prompt với langchain_core nếu có, fallback sang format thường."""
    if PromptTemplate is not None:
        rendered = PromptTemplate.from_template(template).format(**variables)
    else:
        rendered = template.format(**variables)
    return f"[role={role} intent={intent}]\n{rendered}"
