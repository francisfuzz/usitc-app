FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# data/ is a mount point — ensure the directory exists inside the image
RUN mkdir -p /app/data

ENTRYPOINT ["python"]
CMD ["hts.py", "--help"]
