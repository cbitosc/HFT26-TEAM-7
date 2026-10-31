"""summariser.py - Featherless (OpenAI-compatible) uncertainty-aware wildlife summary.

The prompt is dynamically constructed: when human feedback exists (from the
Review Queue page), the LLM is told which species the model gets right, which
it misclassifies, and what the overall human-validated accuracy is.  This makes
the narrative more honest — it hedges on species the model struggles with and
speaks confidently about ones humans have confirmed.
"""
import json, os
from config import BASE
from dotenv import load_dotenv

load_dotenv(BASE / ".env")

SYSTEM_PROMPT = """You are a wildlife ecologist analysing camera-trap data.
Write clear, concise summaries for field researchers.
Always mention: how many images are unverified, any species with low confidence,
and whether conclusions are preliminary due to data limitations.
Do not overstate certainty."""

SYSTEM_PROMPT_WITH_FEEDBACK = """You are a wildlife ecologist analysing camera-trap data.
Write clear, concise summaries for field researchers.

IMPORTANT - Human-in-the-loop learning context:
Scientists have been reviewing the AI's predictions and providing corrections.
Use the feedback statistics below to calibrate your language:
- For species marked RELIABLE (>80% human agreement): you may state findings with moderate confidence.
- For species marked UNRELIABLE (<50% accuracy): explicitly flag these as uncertain and needing more review.
- Mention the overall model accuracy and total human decisions to give context on data quality.
- If common misclassifications are listed, warn about confusion between those species pairs.
Do not overstate certainty. Always note whether counts are AI-predicted, human-verified, or mixed."""


def _client():
    from openai import OpenAI
    key = os.getenv("FEATHERLESS_API_KEY")
    if not key:
        raise RuntimeError("FEATHERLESS_API_KEY is missing from .env")
    return OpenAI(api_key=key.strip(), base_url=os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"))


def _get_feedback_context():
    """Try to load feedback context; return None if unavailable."""
    try:
        from pipeline.feedback import feedback_context_for_llm
        return feedback_context_for_llm()
    except Exception:
        return None


def build_prompt(stats: dict, feedback: dict | None = None) -> str:
    base = f"""Here are detection statistics from a camera-trap wildlife survey.
Write a 3-paragraph summary covering:
1. Overall wildlife activity and dominant species.
2. Temporal and spatial patterns (time of day, hotspot locations).
3. Data limitations and caveats (unverified images, low-confidence predictions).

Survey data:
{json.dumps(stats, indent=2, default=str)}"""

    if feedback:
        base += f"""

Human feedback / model learning data:
{json.dumps(feedback, indent=2, default=str)}

Use this feedback to calibrate your confidence: trust reliable species more,
flag unreliable ones explicitly, and mention any common misclassification pairs."""

    return base


def _messages(stats):
    feedback = _get_feedback_context()
    sys_prompt = SYSTEM_PROMPT_WITH_FEEDBACK if feedback else SYSTEM_PROMPT
    return [{"role": "system", "content": sys_prompt},
            {"role": "user", "content": build_prompt(stats, feedback)}]


MODEL = "mistralai/Mistral-7B-Instruct-v0.2"


def summarise_text(stats: dict, model: str = MODEL) -> str:
    r = _client().chat.completions.create(model=model, messages=_messages(stats), temperature=0.4, max_tokens=700)
    return r.choices[0].message.content


def summarise(stats: dict, model: str = MODEL, stream: bool = True):
    """Generator of text chunks (for st.write_stream)."""
    resp = _client().chat.completions.create(model=model, messages=_messages(stats),
                                             stream=True, temperature=0.4, max_tokens=700)
    for chunk in resp:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
