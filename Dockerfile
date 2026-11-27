FROM python:3.12-slim

# Docker mode (one container per bot) needs the docker CLI and the socket.
# Railway and Render build without it and run process mode.
ARG WITH_DOCKER=0

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BOT_ROOT=/data/bots

RUN if [ "$WITH_DOCKER" = "1" ]; then \
      apt-get update && \
      apt-get install -y --no-install-recommends docker.io && \
      rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /srv
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . .

RUN mkdir -p /data/bots
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
