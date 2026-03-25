# CLARA API (P0)

FastAPI backend skeleton for CLARA P0.

## Run

```bash
uv pip install -e ".[dev]"
uvicorn clara_api.main:app --reload --host 0.0.0.0 --port 8000
```

## Auth Email Delivery

```bash
# preview | smtp | disabled
export AUTH_EMAIL_DELIVERY_MODE=preview
export AUTH_EXPOSE_ACTION_TOKEN_PREVIEW=true
export AUTH_REQUIRE_EMAIL_VERIFICATION=false

# only required when AUTH_EMAIL_DELIVERY_MODE=smtp
export SMTP_HOST=smtp.example.com
export SMTP_PORT=587
export SMTP_USERNAME=user
export SMTP_PASSWORD=pass
export SMTP_FROM_EMAIL=no-reply@clara.example
```

## Alembic

```bash
alembic upgrade head
```
