# Contributing to LLMGuard

Thanks for your interest! Here's how to get started.

## Setup

```bash
git clone https://github.com/Neeraj-Ch0udhary/llmguard
cd llmguard
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Areas to contribute

- **New attack patterns** — add examples to `guard_input/` training data
- **Language support** — Hindi, Tamil, Telugu injection detection
- **Output guard** — improve hallucination detection accuracy
- **Dashboard** — React frontend for the API

## Running tests

```bash
python examples/three_agent_test.py
python guard_input/classifier.py
python guard_output/checker.py
python guard_memory/store.py
```

## Submitting a PR

1. Fork the repo
2. Create a branch: `git checkout -b feat/your-feature`
3. Make your changes
4. Push and open a PR

All contributions welcome!