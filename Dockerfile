FROM python:3.11-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y wget gnupg2 libnss3 libatk-bridge2.0-0 libgtk-3-0 libxss1 libasound2 libgbm1 libxshmfence1 libxcomposite1 libxrandr2 libu2f-udev libdrm2 libxdamage1 libxfixes3 libxext6 libx11-xcb1 libxcb1 libx11-6 libxrender1 libxi6 libxtst6 fonts-liberation libappindicator3-1 lsb-release xdg-utils && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install Playwright and browsers
RUN pip install playwright && playwright install --with-deps

# Copy your code
COPY . /app
WORKDIR /app

CMD ["python", "bot.py"] 