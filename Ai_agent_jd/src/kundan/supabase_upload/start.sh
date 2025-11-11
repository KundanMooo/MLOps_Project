#!/bin/bash

# Start FastAPI backend in background
echo "Starting FastAPI backend..."
uvicorn main:app --host 0.0.0.0 --port 8000 &

# Wait for backend to be ready
echo "Waiting for backend to start..."
sleep 5

# Start Streamlit frontend
echo "Starting Streamlit frontend..."
streamlit run app.py --server.address 0.0.0.0 --server.port 8501