# Use the official Python base image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data
RUN python -m nltk.downloader wordnet

# Copy the application files
COPY . .

# Expose the port the app runs on
EXPOSE 8080

# Run the application
CMD ["waitress-serve", "--port=8080", "application:application"]