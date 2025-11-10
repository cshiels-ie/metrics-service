#!/bin/bash
set -e

echo "==================================================================="
echo "AWX Mock Data Generator"
echo "==================================================================="

echo "Running mock data generator script..."
cd /docker-entrypoint-initdb.d
python3 02-insert-data.py

echo "==================================================================="
echo "Data generation completed successfully!"
echo "==================================================================="

