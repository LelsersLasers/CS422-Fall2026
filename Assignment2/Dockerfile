FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-matplotlib ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY part1.py /app/part1.py
COPY data/ /app/data/
ENTRYPOINT ["python3", "/app/part1.py"]
