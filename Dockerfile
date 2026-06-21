FROM python:3.9-slim

WORKDIR /app

# Copier les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code
COPY . .

# Exposer les ports
EXPOSE 8080 9090

# Commande de démarrage
CMD ["python", "main.py"]
