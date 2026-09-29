FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-matplotlib ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY main.py plot_results.py /app/
COPY part1/ /app/part1/
COPY part2/ /app/part2/
COPY part3/ /app/part3/
COPY data/ /app/data/
ENTRYPOINT ["python3", "/app/main.py"]
