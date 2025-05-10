# Use Python's lightweight base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy all static files (index.html, etc.)
COPY . .

# Expose the port
EXPOSE 3000

# Start a simple HTTP server
CMD ["python3", "-m", "http.server", "3000"]
