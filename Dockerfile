FROM python:3.10
ENV PYTHONUNBUFFERED=1
WORKDIR /usr/src/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev

# Copy requirements first for caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL files
COPY . .

# Verify CSV file exists (debugging)
RUN ls -la /usr/src/app/mainapp/multi_stock_data.csv