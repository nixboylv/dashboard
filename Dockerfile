# Use an official Python runtime as a parent image
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
WORKDIR /app

# Copy application code first (relative to build context)
COPY ./service-dashboard /app

# Install dependencies using requirements.txt from the app code directory
RUN pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 5000
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "app:app"]