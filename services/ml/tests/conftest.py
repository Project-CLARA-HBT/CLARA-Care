import os

# Ensure tests run hermetically with default test configuration (e.g. no external deepseek key in base test environment).
# Specific tests that require an API key explicitly mock or monkeypatch it.
os.environ.setdefault("DEEPSEEK_API_KEY", "")
os.environ.setdefault("ROUTER_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("EMBEDDING_API_KEY", "")
os.environ.setdefault("YESCALE_API_KEY", "")
os.environ.setdefault("OCR_API_KEY", "")
