# Dockerfile für websocket_stream  
FROM python:3.9-slim  

# Installiere notwendige Abhängigkeiten  
RUN pip install --no-cache-dir redis websockets requests 

# Arbeitsverzeichnis setzen  
WORKDIR /app  

# Kopiere das Skript in den Container  
COPY websocket_stream.py .  

# Starte das Skript  
CMD ["python", "websocket_stream.py"]  