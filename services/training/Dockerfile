FROM python:3.11.14-slim@sha256:c8271b1f627d0068857dce5b53e14a9558603b527e46f1f901722f935b786a39

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system clara-training \
    && useradd --system --gid clara-training --create-home clara-training

WORKDIR /workspace
COPY requirements.lock /tmp/clara-training-requirements.lock
RUN python -m pip install --no-cache-dir -r /tmp/clara-training-requirements.lock

USER clara-training
ENTRYPOINT ["python"]
