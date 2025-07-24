FROM python:3.9-slim

# Set environment variables for PySpark
ENV PYSPARK_PYTHON=python3
ENV PYSPARK_DRIVER_PYTHON=python3
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-arm64
ENV SPARK_HOME=/usr/local/lib/python3.9/site-packages/pyspark

# Set the working directory in the container
WORKDIR /app

# Install dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    procps \
    curl \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Azure libraries for Hadoop/Spark
RUN mkdir -p /app/jars && \
    wget -q https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-azure/3.3.4/hadoop-azure-3.3.4.jar -O /app/jars/hadoop-azure-3.3.4.jar && \
    wget -q https://repo1.maven.org/maven2/com/microsoft/azure/azure-storage/8.6.6/azure-storage-8.6.6.jar -O /app/jars/azure-storage-8.6.6.jar

# Set Spark to use the downloaded JARs
ENV SPARK_CLASSPATH="/app/jars/*"

# Copy the source code into the container
COPY ./src /app/src

# Copy the data into the container
COPY ./data /app/data

# # Set the default command
# CMD ["python", "src/main.py"]