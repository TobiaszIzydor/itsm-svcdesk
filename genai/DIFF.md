---
lab3_genai_diff:
  instrumentation: "opentelemetry-instrumentation-genai-openai 1.2b0, opentelemetry-sdk 1.45.0, openai 3.19.2, opentelemetry-exporter-otlp-json-file 0.66b0"
  spec_ref: "semantic-conventions@v1.41.1"
  attributes:
    - {name: gen_ai.operation.name, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.provider.name, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.request.model, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.request.max_tokens, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.request.temperature, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.id, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.model, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.finish_reasons, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.usage.input_tokens, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.usage.output_tokens, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.request.top_p, emitted: false, in_spec: true, stability: development}
    - {name: gen_ai.request.seed, emitted: false, in_spec: true, stability: development}
    - {name: gen_ai.conversation.id, emitted: false, in_spec: true, stability: development}
    - {name: gen_ai.input.messages, emitted: false, in_spec: true, stability: development}
    - {name: gen_ai.output.messages, emitted: false, in_spec: true, stability: development}
    - {name: gen_ai.usage.prompt_tokens, emitted: false, in_spec: true, stability: deprecated}
    - {name: gen_ai.usage.completion_tokens, emitted: false, in_spec: true, stability: deprecated}
---
<!-- ai-generated: 70% - Claude Code ran the call, read the v1.41.1 registry and drafted the table and prose; the choice of reference and attributes to compare is mine -->

# What the library emits, against the spec

**The call.** One chat completion (`genai/call.py`) against a local Ollama model, `qwen3:1.7b`, through its
OpenAI-compatible endpoint, instrumented with `OpenAIInstrumentor` from
`opentelemetry-instrumentation-genai-openai` 1.2b0 and exported as OTLP JSON with `FileSpanExporter` to
`genai/spans.json`: one span, `chat qwen3:1.7b`, kind CLIENT. Message content capture was left off (the default).

**The reference.** `semantic-conventions@v1.41.1`, the last release of the main repository that still held the
GenAI conventions. I read its attribute registry, `model/gen-ai/registry.yaml`, and the deprecated attributes in
`model/gen-ai/deprecated/registry-deprecated.yaml`, both at the tag `v1.41.1`.

**What agrees.** All ten `gen_ai.*` keys the library emitted are defined in v1.41.1, all with stability
`development`, and they use the current names: `gen_ai.provider.name` (not the deprecated `gen_ai.system`) and
`gen_ai.usage.input_tokens` / `output_tokens` (not the deprecated `prompt_tokens` / `completion_tokens`). The span
name follows the convention `{gen_ai.operation.name} {gen_ai.request.model}`. Nothing outside the `gen_ai.*`
namespace was invented under it: the one vendor-specific value, `openai.response.system_fingerprint`, sits in the
`openai.*` namespace, and the connection is described with the general `server.address` and `server.port`.

**What is missing, and why.** Request attributes appear only when the request sets them: `top_p` and `seed` were
not in my request, so they are absent. For `seed` that is exactly the spec ("conditionally required: if the
request includes a seed"); `top_p` is `recommended`, and a library could have recorded the server's default, but
it cannot know it, so leaving it out is honest. `gen_ai.conversation.id` is
not emitted because a bare OpenAI client has no notion of a conversation; an application would have to add it.
`gen_ai.input.messages` and `gen_ai.output.messages` are opt-in in the spec and switched off by default in the
library, which is the right default: they would put the users' prompts, here a service desk question that can
contain names and machine identifiers, into the tracing backend.

**What it means for a dashboard.** Everything on the span is `development`, so the names can change in any
release without a deprecation period; indeed, v1.42.0 deprecated every `gen_ai.*` attribute of this repository and
moved them to `semantic-conventions-genai`. A dashboard or alert built on these keys should pin the
instrumentation version and treat a library upgrade as a schema migration, not as a routine dependency bump.
Token usage (`gen_ai.usage.*`) and `gen_ai.response.finish_reasons` are the attributes worth building on first:
cost and truncated answers are what an operator of such a feature needs to see.
