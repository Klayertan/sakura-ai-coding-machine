FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates python3 python3-pip && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://ollama.com/install.sh | sh
WORKDIR /app
COPY backend/requirements.txt .
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt
COPY backend/ .
EXPOSE 8080
CMD ["./start.sh"]
