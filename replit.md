# Grok Multiagent Lab

A Python environment for building and experimenting with multi-agent systems powered by Grok.

## Project Structure

- `main.py` - Flask web application entry point
- `requirements.txt` - Python dependencies

## Setup

- **Language**: Python 3.11
- **Framework**: Flask (development), Gunicorn (production)
- **Port**: 5000

## Running

The app runs via the "Start application" workflow using:
```
python main.py
```

## Deployment

Configured for autoscale deployment using Gunicorn:
```
gunicorn --bind=0.0.0.0:5000 --reuse-port main:app
```
