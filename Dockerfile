FROM python:3.12

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY .env_docker .env
COPY *.py .

LABEL authors="Romain Thomas"
LABEL org.opencontainers.image.source="https://github.com/romain894/openalex-elasticsearch"

#ENTRYPOINT ["python3", "openalex_main.py"]