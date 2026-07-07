# 🛡️ ShieldPDF — Document De-Identification Suite

ShieldPDF is a professional, secure, and user-friendly web application designed to automatically extract text from PDF files, identify sensitive Personal Identifiable Information (PII), and apply high-fidelity, layout-preserving redactions. 

This repository contains two main implementations designed to suit different runtime environments:
1. **Hybrid Web Interface (Express + React + Python Engine)**: Ideal for integrated Javascript stack developers. Uses a React frontend, an Express API gateway, and a Python subprocess core.
2. **Pure Standalone Python Service (FastAPI + PyMuPDF)**: Ideal for pure Python environments. A standalone microservice with an integrated responsive Tailwind HTML UI.

---

## ✨ Features

- **Automated PII Recognition**: Out-of-the-box support for detecting:
  - Person & Company Names
  - Emails & Phone Numbers
  - CIN (Corporate Identification Number) & GST Numbers
  - IFSC Codes & Bank Account Numbers
  - Indian Vehicle registration numbers
  - Bar Council registrations
- **Integrated Interactive Dashboard**: Side-by-side original and redacted text comparison view, list of detected entities, and real-time redaction summaries.
- **Dynamic Configuration Filters**: Toggle which categories of sensitive records to redact dynamically.
- **Manual Overrides Dictionary**: Inject custom names, company terms, or secret words to redact instantly.
- **Layout-Preserving Redaction**: PDF redaction overlays preserve original document layouts, typography, and images.
- **Durable File Protection**: All file processing happens completely on-premise inside secure containers — zero data-leak to external third parties.

---

## 🛠️ Prerequisites

Ensure you have the following installed on your machine:
- **Node.js** (v18 or higher)
- **Python** (v3.10 or higher)

---

## 🚀 Setup & Execution — 1. Hybrid Web Application (Express + React)

This is the default application served in this workspace on port `3000`.

### Local Installation

1. Install Node.js dependencies:
   ```bash
   npm install
   ```
2. Install Python PDF processing core:
   ```bash
   pip install pymupdf
   ```

### Running Locally

To boot the dev server with Hot Module Replacement and TypeScript Express API proxying:
```bash
npm run dev
```
Open your browser and navigate to `http://localhost:3000` to start de-identifying!

---

## 🐍 Setup & Execution — 2. Standalone Python App (FastAPI)

For teams wanting a lightweight Python microservice, we provide an all-in-one FastAPI application inside the `python_app/` folder. It includes the complete redaction engine and an embedded modern web dashboard!

### Standalone Installation

1. Change directory:
   ```bash
   cd python_app
   ```
2. Install Python web framework and PDF core:
   ```bash
   pip install fastapi uvicorn pymupdf pydantic
   ```

### Running the Standalone App

Start the FastAPI application on port `8000`:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```
Open your browser and navigate to `http://localhost:8000` to access the integrated dashboard.

---

## 📦 Cloud Deployment Guide

ShieldPDF is container-friendly and can be deployed to any container registry or host (Google Cloud Run, AWS App Runner, Render, Heroku).

### 🐋 Dockerfile for Standalone FastAPI App

Create a `Dockerfile` in your root or `python_app/` directory:

```dockerfile
# Use a secure, slim Python base image
FROM python:3.10-slim

# Set environment variable to ensure logs are piped directly
ENV PYTHONUNBUFFERED=1

# Create and set working directory
WORKDIR /app

# Copy dependency specifications and install
RUN pip install --no-cache-dir fastapi uvicorn pymupdf pydantic

# Copy application files
COPY redact.py /app/redact.py
COPY python_app/ /app/

# Expose service port
EXPOSE 8000

# Run FastAPI app with uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run your container:
```bash
docker build -t shieldpdf-fastapi .
docker run -p 8000:8000 shieldpdf-fastapi
```

---

## 📜 Compliance & Security Notes

- **Completely On-Premise**: ShieldPDF does not transfer file contents or extracted text to any external cloud-based AI or analytics platforms.
- **Disposable Jobs**: Workspaces and redacted files are created in disposable system directories and are only persisted for the duration of the active download handle.
