# Local Setup & Environment Guide

VALENCE runs strictly on-premises without external network dependencies during runtime.

---

## 1. Prerequisites

- Python 3.9+ (running on Apple Silicon macOS)
- Ollama local daemon installed (`/usr/local/bin/ollama`)

---

## 2. Environment Setup

1. Create a local virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Copy configuration template:
   ```bash
   cp .env.example .env
   ```
3. Set your Python path to the repository root:
   ```bash
   export PYTHONPATH=.
   ```

---

## 3. Local Model Preparation (One-Time Setup)

Ensure the Ollama daemon is running locally:
```bash
ollama serve
```

Pull the required local models in advance:
```bash
# Text generation LLM
ollama pull llama3.2:3b

# Vision-language model for image inspection
ollama pull llama3.2-vision:11b
```

Place the local embedding model weights into:
```
models/all-MiniLM-L6-v2/
```

---

## 4. Running the Application

To launch the Streamlit user interface:
```bash
streamlit run src/ui/app.py
```

---

## 5. Running Verification Tests

Run the contract verification suite:
```bash
python3 -m unittest discover -s tests
```
