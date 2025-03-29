# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Prevent Python from writing pyc files and prevent buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies if needed (e.g., for ca-certificates if checking external HTTPS)
# RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker cache
COPY ./service-dashboard/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY ./service-dashboard /app

# Expose the port Gunicorn will run on
EXPOSE 5000

# Command to run the application using Gunicorn
# Adjust workers based on your server resources (2-4 is often a good starting point)
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:5000", "app:app", "--log-level", "info"]