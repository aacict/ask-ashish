# Using python image
FROM python:3.11-slim

# Setting up a work dir inside docker
WORKDIR /app

# Copy requirements file to the workdir and install the dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app codes to the workdir
COPY . .

# Expose the port
EXPOSE 5000

# Rn the Server
CMD [ "gunicorn","-b", "0.0.0.0:5000", "app:app" ]