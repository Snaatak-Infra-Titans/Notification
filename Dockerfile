FROM python:3.11-alpine

LABEL maintainer="OpsTree Solutions"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .

RUN apk add --no-cache \
        bash \
        gcc \
        g++ \
        musl-dev \
        libffi-dev \
        openssl-dev \
        cargo

RUN pip install --no-cache-dir --upgrade pip

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8085

ENTRYPOINT ["./entrypoint.sh"]
