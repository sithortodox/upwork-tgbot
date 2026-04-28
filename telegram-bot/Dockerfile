FROM python:3.11-slim

WORKDIR /app

COPY telegram-bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ /app/shared/
COPY telegram-bot/app/ /app/app/

CMD ["python", "-m", "app.main"]
