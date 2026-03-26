FROM eclipse-temurin:17-jdk-jammy

RUN apt-get update && apt-get install -y \
    python3 python3-pip wget unzip curl \
    && rm -rf /var/lib/apt/lists/*

# Download Eclipse MAT headless (with fallback)
RUN wget -q "https://download.eclipse.org/mat/latest/rcp/MemoryAnalyzer-linux.gtk.x86_64.zip" \
    -O /tmp/mat.zip \
    && unzip /tmp/mat.zip -d /opt/ \
    && rm /tmp/mat.zip \
    || echo "Eclipse MAT download failed - will use fallback analysis"

WORKDIR /analyzer
COPY requirements.txt .
RUN pip3 install --upgrade pip && pip3 install -r requirements.txt --break-system-packages

COPY . .

ENTRYPOINT ["python3", "run_analysis.py"]
