# Copyright (c) 2026 Oliver Kowalke
# SPDX-License-Identifier: MIT
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
L9 output-contract corpus (testing-strategies.md §3.9a).

Recorded (requirements, domain) pairs covering the agent pattern catalogue's
major domains. Each entry runs through the REAL pipeline (opt-in via the
AGENT_BENCH_LLM marker — never in default CI) and the output design is
asserted against the structural invariants (invariants.py). The tracked
structural pass-rate is the drift signal for prompt/model/pipeline changes;
corpus entries are added per catalogue domain, never per individual design.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CorpusEntry:
    requirements: str
    domain: str
    note: str


CORPUS: tuple[CorpusEntry, ...] = (
    CorpusEntry(
        requirements=(
            "Build a research assistant that answers multi-hop questions by "
            "iteratively searching the web, extracting facts from pages, "
            "revising its plan when evidence conflicts, and producing a "
            "cited report. Budget: at most 20 tool calls per question."
        ),
        domain="exploratory-research",
        note="reasoning / plan-execute family",
    ),
    CorpusEntry(
        requirements=(
            "Design a coding agent that edits files in a sandbox: read the "
            "repo, propose a patch, run the test suite, and iterate on "
            "failures until green or a step budget is exhausted. Every shell "
            "command must be allow-listed and logged."
        ),
        domain="code-generation",
        note="tool-use / single-agent-loop family",
    ),
    CorpusEntry(
        requirements=(
            "Design a document review pipeline: a router classifies incoming "
            "contracts, parallel specialist agents extract clauses, dates and "
            "parties, a verifier cross-checks the extraction against the "
            "source, and a synthesizer produces the final summary. Conflicting "
            "extractions must be flagged, not silently merged."
        ),
        domain="document-processing",
        note="parallel-fan-out / evaluator-loop family",
    ),
    CorpusEntry(
        requirements=(
            "Build a customer-support triage system: intake messages are "
            "classified by severity, a planner delegates to executor agents "
            "with restricted tool sets, a critic reviews every draft reply "
            "before it is sent, and escalations open a human handoff task. "
            "Cost per ticket must stay predictable."
        ),
        domain="customer-support",
        note="hierarchical supervisor/worker family",
    ),
    CorpusEntry(
        requirements=(
            "Design a market-monitoring swarm: many lightweight scraper "
            "agents publish price events, a shared blackboard aggregates the "
            "signals, an analyst agent detects anomalies and publishes "
            "alerts. Each alert needs at least one consumer, and agent "
            "crashes must not lose events."
        ),
        domain="data-analysis",
        note="swarm / event-driven family (producer/consumer closure)",
    ),
)
