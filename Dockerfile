FROM python:3.12-slim

WORKDIR /app

# Dependencies are installed as part of the image build, so a plain
# `docker compose up` (or `docker run`) starts the service with
# everything already in place.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
