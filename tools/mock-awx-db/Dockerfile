FROM postgres:15

# Install Python and pip
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Install Python packages (--break-system-packages is required for Python 3.13+)
RUN pip3 install --no-cache-dir --break-system-packages psycopg2-binary faker

# The init scripts will be mounted at runtime

