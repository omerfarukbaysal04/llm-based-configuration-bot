# AI-Driven Configuration Manager

![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=for-the-badge&logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker)
![LLM](https://img.shields.io/badge/AI-Ollama%20%7C%20Qwen-black?style=for-the-badge)

This project is an intelligent microservice aimed at solving the complexity of managing large configuration files (JSON/YAML). Instead of manually editing nested structures—which is error-prone—this tool allows DevOps engineers to modify configurations using **Natural Language**.

It leverages a local Large Language Model (LLM) to understand intent, fetch context from microservices, and apply changes with **strict schema validation** and **self-correction mechanisms**.

---

## 🚀 Key Features

* **Natural Language Interface:** modify complex JSON structures using simple English commands (e.g., *"Set memory limit for service to 2Gi"*).
* **Microservices Architecture:** Decoupled design with separate services for Schemas, Values, and Logic.
* **Resilient AI Pipeline:**
    * **Deterministic Output:** Uses `temperature=0.0` for consistent results.
    * **Self-Correction:** Automatically detects schema violations and prompts the LLM to fix its own errors (Retry Loop).
    * **Greedy JSON Parsing:** Custom parser to handle LLM output quirks.
* **Safety First:**
    * Strict `jsonschema` validation before any change is accepted.
    * No hallucinations (duplicate keys or invented fields are blocked).
* **Local & Private:** Runs entirely on-premise using Docker and Ollama (no data is sent to the cloud).

---

## 🏗️ System Architecture

The project consists of three containerized services orchestrated via Docker Compose:

1.  **Config-Bot (The Brain):**
    * Receives user requests.
    * Identifies the target application context.
    * Communicates with the LLM (Qwen 2.5:3b) via Ollama.
    * Validates generated configs against JSON Schemas.
2.  **Schema-Service:**
    * Simulates a centralized schema registry.
    * Serves strict validation rules for each application.
3.  **Values-Service:**
    * Simulates a "Current State" provider (e.g., GitOps repo or K8s API).
    * Provides the active configuration to be modified.

---

## 🛠️ Installation & Usage

### Prerequisites
* **Docker & Docker Compose** installed.
* **Ollama** installed locally and running.
* Pull the required model:
    ```bash
    ollama pull qwen2.5:3b-instruct
    ```

### 1. Start the Environment
Clone the repo and start the services:

>docker compose up --build

Wait for the services to initialize. The Bot API will be available at http://localhost:5003.

### 2. Example Requests
You can interact with the API using curl or Postman.

Scenario: Update Resource Limits
User wants to increase memory for a specific service.

curl -X POST http://localhost:5003/message \
     -H "Content-Type: application/json" \
     -d '{"input": "set service memory to 1024mb"}'


Scenario: Scaling
User wants to reduce CPU usage to save costs.

curl -X POST http://localhost:5003/message \
     -H "Content-Type: application/json" \
     -d '{"input": "lower cpu limit of chat service to %70"}'

### 🧠 Technical Highlights
The "Self-Correction" Loop
LLMs can sometimes generate invalid JSON or hallucinate fields. To solve this, AutoKube-Config implements a feedback loop:

Generate: LLM produces a draft JSON.

Validate: System checks it against the application's jsonschema.

Retry: If validation fails, the exact error message (e.g., "Property 'replicas' must be an integer") is fed back to the LLM.

Correct: The LLM fixes the specific error and returns the valid JSON.

### Greedy JSON Extraction
LLMs are chatty and often wrap code in Markdown. The project uses a custom greedy parser that locates the outermost { and } to extract clean JSON, ignoring conversational filler.


Developed by Ömer Faruk Baysal
