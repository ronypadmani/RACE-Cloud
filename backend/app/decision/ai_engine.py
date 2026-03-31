"""
AI Engine — LLaMA (Ollama) primary + Gemini optional fallback.

AI_MODE env var controls which backend is used:
  - "local"  → LLaMA3 via Ollama  (default, works offline)
  - "gemini" → Google Gemini API   (requires GEMINI_API_KEY)

Features:
  - Deep project understanding (not keyword matching)
  - Strict JSON prompt with validation
  - Automatic retry (up to 3 attempts)
  - Structured logging
"""
from __future__ import annotations

import json
import logging
import os
import re

import requests

logger = logging.getLogger('ai_engine')

# ── Service icons for the frontend ─────────────────────────────────────────────

SERVICE_ICONS: dict[str, str] = {
    'EC2': '🖥️', 'S3': '🪣', 'Lambda': 'λ', 'RDS': '🗄️',
    'CloudFront': '🌐', 'DynamoDB': '📊', 'ElastiCache': '⚡',
    'SageMaker': '🧠', 'ECS': '🐳', 'EKS': '🐳', 'API Gateway': '🔀',
    'EBS': '💾', 'SNS': '📨', 'SQS': '📬', 'Route 53': '🗺️',
    'Cognito': '🔐', 'CloudWatch': '📈', 'Fargate': '📦',
    'Step Functions': '🔄', 'EventBridge': '🔔', 'Kinesis': '🌊',
    'Redshift': '📊', 'Athena': '🔍', 'Glue': '🧩',
    'Bedrock': '🤖', 'AppSync': '🔗',
}

# Required top-level keys the AI must return
_REQUIRED_KEYS = {
    'project_type', 'architecture', 'services', 'reasoning',
    'scalability', 'complexity', 'estimated_usage', 'confidence',
}

_MAX_RETRIES = 3

# Gemini fallback models
_FALLBACK_MODELS = ['gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-1.5-flash']

# ── System prompt (shared by both backends) ────────────────────────────────────

_SYSTEM_PROMPT = """You are a senior AWS Cloud Architect.

Your Thinking Process:
1. Understand the full project deeply (not just keywords)
2. Identify:
   - type of application
   - scale (users/load)
   - constraints (budget/performance)
3. Break the system into:
   - Frontend
   - Backend
   - Database
   - Storage
   - Networking/CDN
4. Select AWS services based on:
   - scalability
   - cost efficiency
   - simplicity
   - reliability
5. Estimate usage realistically

STRICT RULES:
- Return ONLY valid JSON — no markdown fences, no explanation outside JSON.
- Ensure the JSON is complete and properly closed. Do NOT truncate.
- If your output would be invalid JSON, fix it before returning.

REQUIRED JSON FORMAT (return EXACTLY this structure):
{
  "project_type": "web_app | api | realtime | ml_pipeline | data_platform | media | iot | saas",
  "architecture": [
    "Frontend → service_name with brief description",
    "Backend → service_name with brief description",
    "Database → service_name with brief description",
    "Storage → service_name with brief description",
    "Networking → service_name with brief description"
  ],
  "services": ["EC2", "S3", "Lambda"],
  "reasoning": "2-3 sentences explaining why this architecture fits the requirements.",
  "scalability": "Low | Medium | High | Very High",
  "complexity": "Simple | Moderate | Complex | Enterprise",
  "estimated_usage": {
    "compute_hours": 0,
    "storage_gb": 0,
    "requests": 0
  },
  "confidence": 85
}

ALLOWED AWS SERVICES:
EC2, S3, Lambda, RDS, DynamoDB, CloudFront, ElastiCache, SageMaker,
ECS, EKS, API Gateway, EBS, SNS, SQS, Route 53, Cognito, CloudWatch,
Fargate, Step Functions, EventBridge, Kinesis, Redshift, Athena, Glue,
Bedrock, AppSync.

IMPORTANT:
- "architecture" must be an array of strings (one per layer).
- "services" must be an array of AWS service name strings.
- "confidence" must be an integer from 0 to 100.
- "estimated_usage" values must be numbers.
- Match complexity to the actual project scope — do not over-engineer.
- Be practical and realistic with estimated usage figures."""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_ai_mode() -> str:
    return os.getenv('AI_MODE', 'local').strip().lower()


def _validate_ai_response(data: dict) -> bool:
    """Return True if *data* contains all required keys with sensible types."""
    if not isinstance(data, dict):
        return False
    if not _REQUIRED_KEYS.issubset(data.keys()):
        logger.warning('Missing keys: %s', _REQUIRED_KEYS - data.keys())
        return False
    if not isinstance(data.get('services'), list) or len(data['services']) == 0:
        logger.warning('services must be a non-empty list')
        return False
    if not isinstance(data.get('confidence'), (int, float)):
        logger.warning('confidence must be a number')
        return False
    usage = data.get('estimated_usage')
    if not isinstance(usage, dict):
        logger.warning('estimated_usage must be an object')
        return False
    return True


def _parse_raw_response(raw: str) -> dict | None:
    """Extract valid JSON from raw AI output."""
    text = raw.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        text = match.group(0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _build_result(data: dict, ai_mode: str) -> dict:
    """Normalise a validated AI response into the shape the rest of the app expects."""
    arch = data.get('architecture', '')
    if isinstance(arch, list):
        arch_list = arch
        arch_str = ' | '.join(str(item) for item in arch)
    else:
        arch_list = [arch] if arch else []
        arch_str = arch

    services = data.get('services', [])

    return {
        'project_type': data.get('project_type', 'unknown'),
        'architecture': arch_str,
        'architecture_layers': arch_list,
        'services': services,
        'service_icons': {s: SERVICE_ICONS.get(s, '☁️') for s in services},
        'reasoning': data.get('reasoning', ''),
        'scalability': data.get('scalability', 'Medium'),
        'complexity': data.get('complexity', 'Moderate'),
        'estimated_usage': data.get('estimated_usage', {
            'compute_hours': 0, 'storage_gb': 0, 'requests': 0,
        }),
        'confidence': min(100, max(0, int(data.get('confidence', 70)))),
        'ai_provider': 'ollama' if ai_mode == 'local' else 'gemini',
    }


def _build_prompt(user_input: str) -> str:
    return (
        f"User Requirement:\n{user_input}\n\n"
        "Analyze the above requirement and suggest an AWS architecture. "
        "Return ONLY the JSON object described in your instructions."
    )


# ── Local AI (LLaMA via Ollama) ────────────────────────────────────────────────

def generate_local_ai_response(user_input: str) -> dict:
    """Call Ollama API to generate architecture recommendation using LLaMA/phi3.

    Raises RuntimeError if all retry attempts fail.
    """
    ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434').rstrip('/')
    model = os.getenv('OLLAMA_MODEL', 'llama3')
    endpoint = f'{ollama_url}/api/generate'

    prompt = f"{_SYSTEM_PROMPT}\n\n{_build_prompt(user_input)}"
    last_error = ''

    for attempt in range(1, _MAX_RETRIES + 1):
        logger.info('Ollama attempt %d/%d  model=%s', attempt, _MAX_RETRIES, model)

        try:
            resp = requests.post(
                endpoint,
                json={
                    'model': model,
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.4,
                        'num_predict': 1024,
                    },
                },
                timeout=120,
            )
            resp.raise_for_status()
        except requests.ConnectionError:
            raise RuntimeError(
                'Cannot connect to Ollama. Ensure Ollama is running at '
                f'{ollama_url}. Start it with: ollama serve'
            )
        except requests.Timeout:
            last_error = 'Ollama request timed out'
            logger.warning('Ollama timeout on attempt %d', attempt)
            continue
        except requests.RequestException as exc:
            last_error = str(exc)
            logger.error('Ollama error (attempt %d): %s', attempt, exc)
            continue

        raw = resp.json().get('response', '')
        logger.debug('Raw Ollama response (attempt %d): %s', attempt, raw[:500])

        data = _parse_raw_response(raw)
        if data is None:
            logger.warning('Attempt %d: could not parse JSON from Ollama response', attempt)
            last_error = f'Invalid JSON: {raw[:200]}'
            continue

        if not _validate_ai_response(data):
            logger.warning('Attempt %d: Ollama response failed validation', attempt)
            last_error = 'Validation failed — missing or bad fields'
            continue

        logger.info('Ollama returned valid response on attempt %d', attempt)
        return _build_result(data, 'local')

    raise RuntimeError(
        f'Ollama ({model}) failed after {_MAX_RETRIES} attempts. Last issue: {last_error}'
    )


# ── Gemini AI (optional fallback) ──────────────────────────────────────────────

def generate_gemini_response(user_input: str) -> dict:
    """Call Gemini API to generate architecture recommendation.

    Requires GEMINI_API_KEY in env. Tries multiple models on rate-limit.
    Raises EnvironmentError if key is missing, RuntimeError on failure.
    """
    from google import genai
    from google.genai import types as genai_types

    api_key = os.getenv('GEMINI_API_KEY', '').strip()
    if not api_key:
        raise EnvironmentError(
            'GEMINI_API_KEY is not configured. '
            'Add it to backend/.env or switch AI_MODE to "local".'
        )

    client = genai.Client(api_key=api_key)
    primary = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
    models_to_try = [primary] + [m for m in _FALLBACK_MODELS if m != primary]

    prompt = _build_prompt(user_input)
    last_error = ''

    for model_name in models_to_try:
        for attempt in range(1, _MAX_RETRIES + 1):
            logger.info('Gemini attempt %d/%d  model=%s', attempt, _MAX_RETRIES, model_name)
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=_SYSTEM_PROMPT,
                        temperature=0.4,
                        max_output_tokens=1024,
                    ),
                )
            except Exception as exc:
                err_str = str(exc)
                logger.error('Gemini error (model=%s, attempt %d): %s',
                             model_name, attempt, exc)
                if '429' in err_str or 'quota' in err_str.lower():
                    last_error = f'Rate limited on {model_name}'
                    break
                last_error = str(exc)
                continue

            raw = response.text or ''
            logger.debug('Raw Gemini response (model=%s, attempt %d): %s',
                         model_name, attempt, raw[:500])

            data = _parse_raw_response(raw)
            if data is None:
                last_error = f'Invalid JSON: {raw[:200]}'
                continue

            if not _validate_ai_response(data):
                last_error = 'Validation failed — missing or bad fields'
                continue

            logger.info('Gemini returned valid response on attempt %d (model=%s)',
                        attempt, model_name)
            return _build_result(data, 'gemini')
        else:
            continue

    raise RuntimeError(
        f'Gemini failed after {_MAX_RETRIES} attempts. Last issue: {last_error}'
    )


# ── Public API (mode switch) ──────────────────────────────────────────────────

def generate_ai_architecture(user_input: str) -> dict:
    """Generate an AWS architecture recommendation using the configured AI.

    Uses AI_MODE env var:
      - "local"  → LLaMA via Ollama  (default)
      - "gemini" → Google Gemini API

    Raises RuntimeError or EnvironmentError on failure.
    """
    mode = _get_ai_mode()

    if mode == 'gemini':
        return generate_gemini_response(user_input)

    # Default: local AI via Ollama
    return generate_local_ai_response(user_input)
