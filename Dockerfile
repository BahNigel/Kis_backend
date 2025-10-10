# multi-stage build could be added for optimization
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y build-essential libpq-dev git curl && rm -rf /var/lib/apt/lists/*

COPY requirements /app/requirements
RUN pip install --upgrade pip
RUN pip install -r requirements/base.txt

COPY . /app

# create media and static folders
RUN mkdir -p /vol/web/media /vol/web/static

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
