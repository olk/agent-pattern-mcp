# Agent Tracing Telemetry Pattern

## Overview

[JSON Data](./agent-tracing-telemetry-pattern.json)

Production agent systems that require full observability into agent behavior — not just input/output pairs but the full reasoning trace, tool calls, intermediate decisions, and state transitions. Trac

## When to Use

- Tasks in these domains: regulated-domains, high-stakes-outputs, multi-agent-systems

## How It Works

- Span Emitter
- Trace Context Propagator
- Trace Processor
- Span Storage

## Examples

Production monitoring of customer-facing agent systems

## Best Practices

- Define a span naming convention and stick to it across the codebase
- Include cost, latency, token count, and decision reason as standard span attributes
- Integrate trace storage with a queryable backend for dashboarding

## Common Pitfalls

- Instrumentation adds overhead to every agent step
- Trace storage and processing can be expensive at scale

## References

- OpenTelemetry, Distributed Tracing for LLM Applications, 2024 — https://opentelemetry.io/docs/specs/otel/
- LangSmith, Tracing LLM Applications — https://docs.smith.langchain.com/tracing
