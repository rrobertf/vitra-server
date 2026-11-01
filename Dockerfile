FROM node:24-bookworm-slim AS node
FROM python:3.12-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libstdc++6 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home vitra && mkdir -p /app/cache && chown -R vitra:vitra /app
USER vitra
ENV HOST=0.0.0.0 PORT=10000 PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["python","server.py"]
