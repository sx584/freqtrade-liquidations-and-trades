# Dockerfile für csv_writer  
FROM python:3.9-slim  

# Installiere notwendige Abhängigkeiten  
RUN pip install --no-cache-dir redis requests

# Arbeitsverzeichnis setzen  
WORKDIR /app  

# Kopiere das Skript und die Konfiguration in den Container  
COPY csv_writer.py .
COPY ../config.py .  

# Starte das Skript  
CMD ["python", "csv_writer.py"]  