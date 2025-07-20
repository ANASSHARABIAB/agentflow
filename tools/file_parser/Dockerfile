# tools/file_parser/Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Copy your requirements if you have them
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy your code
COPY main.py ./

# If your script has other dependencies, copy them here

# Run your script by default
CMD ["python", "main.py"]
