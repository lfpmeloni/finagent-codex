# Base Python image
FROM python:3.11

# Set working directory
WORKDIR /app/backend

# Copy backend code from src/backend
COPY src/backend/ .

# Copy frontend static files from src/frontend/wwwroot
COPY src/frontend/wwwroot ../frontend/wwwroot

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8000

# Start the app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
