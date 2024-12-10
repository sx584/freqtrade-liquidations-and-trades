# Dockerfile für csv_writer  
FROM python:3.9-slim  

# Installiere notwendige Abhängigkeiten  
RUN pip install --no-cache-dir redis requests

# Arbeitsverzeichnis setzen  
WORKDIR /app  

# Kopiere das Skript in den Container  
COPY csv_writer.py .  

# Starte das Skript  
CMD ["python", "csv_writer.py"]  