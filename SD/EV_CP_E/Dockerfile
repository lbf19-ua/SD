# Dockerfile para EV_CP_E (Engine)
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir kafka-python
CMD ["python", "EV_CP_E.py"]