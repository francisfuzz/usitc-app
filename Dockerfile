FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# data/ is a mount point — ensure the directory exists inside the image
RUN mkdir -p /app/data

# Run as non-root user
RUN useradd --create-home --no-log-init appuser \
    && chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["python"]
CMD ["hts.py", "--help"]
