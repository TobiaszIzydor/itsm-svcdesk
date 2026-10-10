# ai-generated: 70% - Claude Code wrote the script from my instructions (endpoint, model, library versions and output are mine)
"""Stretch 1 (L3-STRETCH-1, MONITORING-SPEC.md M-28): one instrumented chat completion, spans to genai/spans.json.

Run from the repository root (no Python on the host; Ollama with qwen3:1.7b on port 11434):
  docker run --rm -v "${PWD}:/repo" -w /repo python:3.13-slim sh -c "pip install -q openai==3.19.2
    opentelemetry-sdk==1.45.0 opentelemetry-instrumentation-genai-openai==1.2b0
    opentelemetry-exporter-otlp-json-file==0.66b0 && python genai/call.py"
"""

import os
from pathlib import Path

from openai import OpenAI
from opentelemetry import trace
from opentelemetry.exporter.otlp.json.file import FileSpanExporter
from opentelemetry.instrumentation.genai.openai import OpenAIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

SPANS_FILE = Path(__file__).with_name("spans.json")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://host.docker.internal:11434/v1")
MODEL = os.environ.get("GENAI_MODEL", "qwen3:1.7b")


def main() -> None:
    SPANS_FILE.unlink(missing_ok=True)
    provider = TracerProvider(resource=Resource.create({"service.name": "svcdesk-genai-stretch"}))
    provider.add_span_processor(SimpleSpanProcessor(FileSpanExporter(str(SPANS_FILE))))
    trace.set_tracer_provider(provider)
    OpenAIInstrumentor().instrument(tracer_provider=provider)

    client = OpenAI(base_url=BASE_URL, api_key="ollama")
    answer = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a service desk assistant. Answer in one sentence."},
            {"role": "user", "content": "My VPN drops every few minutes. What should I check first?"},
        ],
        max_tokens=200,
        temperature=0.2,
    )
    print(answer.choices[0].message.content)
    provider.shutdown()


if __name__ == "__main__":
    main()
