FROM python:3.10-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files including main.py and fonts directory
COPY . .

# Download NLTK data required by your code
RUN python3 -m nltk.downloader punkt

# Expose port 8080 (Cloud Run expects the application to listen on this port)
EXPOSE 8080

# Run the application using python3.
# main.py calls app.run_polling(), so the bot will start polling Telegram for updates.
CMD ["python3", "main.py"]
