# Dockerfile para EV_Driver
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir kafka-python
CMD ["python", "EV_Driver.py"]