FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    HOME=/tmp \
    PATH=/opt/venv/bin:$PATH
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir -r /app/requirements.txt
COPY main.py plot_results.py /app/
COPY part1/ /app/part1/
COPY part2/ /app/part2/
COPY part3/ /app/part3/
COPY data/ /app/data/
RUN mkdir /app/output && chmod 1777 /app/output
ENTRYPOINT ["python3", "/app/main.py"]
