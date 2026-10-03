# Official Ollama image: ships the GPU runtime libraries, so no CUDA base image or
# `curl | sh` installer is needed. Pin a version for reproducible builds:
#   docker build --build-arg OLLAMA_VERSION=<tag> ...
ARG OLLAMA_VERSION=latest
FROM ollama/ollama:${OLLAMA_VERSION}

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates python3 python3-venv \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional: bake model weights into the image so a DOK task starts without a
# billed download. DOK caps images at 30 GB, so this suits gpt-oss:20b (~14 GB)
# but not gpt-oss:120b (~65 GB). See docs/dok-deployment.md.
ARG BAKE_MODEL=""
RUN if [ -n "$BAKE_MODEL" ]; then \
      (ollama serve &) ; \
      for i in $(seq 1 30); do curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break; sleep 1; done ; \
      ollama pull "$BAKE_MODEL" ; \
    fi

COPY backend/ .

EXPOSE 8080
# The base image's entrypoint is the ollama binary; start.sh runs both processes.
ENTRYPOINT []
CMD ["./start.sh"]
