FROM python:3.11-slim

RUN apt-get update && apt-get install -y cron gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY cronjob /etc/cron.d/mycron
RUN chmod 0644 /etc/cron.d/mycron && crontab /etc/cron.d/mycron
RUN printenv >> /etc/environment

CMD ["cron", "-f"]
