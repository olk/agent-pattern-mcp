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

"""Canonical-shape guidance for each AgentTopology, injected into the
GENERATE-phase system prompt.

The GENERATE system prompt is cached per topology, so a dict lookup here costs
nothing at steady state. Every AgentTopology enum value SHOULD have an
explicit entry; the default is reserved for topologies added to the enum
without corresponding guidance.

Entry constraints:
- non-empty and at least 50 characters (meaningful guidance)
- at most 800 characters (bounds the per-topology prompt size)
"""

DEFAULT_TOPOLOGY_GUIDANCE = (
    "Design a minimal, well-structured agent system: identify the core agent(s), "
    "define clear responsibilities for each, specify tool contracts precisely, "
    "and describe how agents communicate (synchronous request/response, "
    "asynchronous events, shared state). Keep the topology no more complex "
    "than the requirements demand."
)

TOPOLOGY_GUIDANCE: dict[str, str] = {
    "evaluator-loop": (
        "Two-agent loop: a Generator agent produces a candidate artifact (code, "
        "plan, config) and an Evaluator agent scores it against explicit criteria, "
        "returning feedback that drives the next generation. Components: generator "
        "agent, evaluator agent, shared context/artifact store, feedback routing "
        "logic, termination condition. Tech: ReAct-style LLMs, structured output "
        "for evaluator scores, message-passing or shared blackboard. Keep the "
        "evaluator's criteria precise and quantitative; fuzzy feedback produces "
        "noise rather than convergence. Anti-pattern: evaluator that just says "
        "'good' without actionable critique."
    ),
    "graph-orchestrated": (
        "A directed graph of agents where edges encode explicit dependencies; "
        "a supervisor or DAG executor routes tasks and aggregates results. "
        "Components: graph definition (nodes = agents, edges = data/control flow), "
        "executor/scheduler, result aggregator, error-propagation routing. "
        "Tech: LangGraph state graphs, Airflow DAGs with agent operators, "
        "temporal workflows. Each agent node should have a single responsibility "
        "and produce a well-defined output. Anti-pattern: agents that need "
        "bidirectional state sharing forced into a unidirectional graph."
    ),
    "hierarchical": (
        "A manager agent decomposes high-level goals into sub-tasks and "
        "dispatches them to worker agents; workers report results up the chain. "
        "Components: manager agent, worker agents (may themselves be managers), "
        "task queue or message passing, result synthesis, escalation path. "
        "Tech: hierarchical prompt patterns, supervisor/worker LLM chains, "
        "ORK-type agent frameworks. The manager must have enough context to "
        "decompose effectively but not so much that it becomes a bottleneck. "
        "Anti-pattern: a manager that delegates everything without adding value."
    ),
    "parallel-fan-out": (
        "A single coordinator agent fans out identical tasks to a pool of "
        "homogeneous worker agents executing in parallel, then collects and "
        "aggregates their results. Components: coordinator agent, worker pool, "
        "task distribution mechanism, result aggregator, partition/sharding logic. "
        "Tech: parallel tool calls, batched API calls, map-reduce patterns. "
        "Workers must be stateless and idempotent so failures can be retried "
        "against any worker. Anti-pattern: workers that need cross-communication "
        "or shared mutable state."
    ),
    "pipeline": (
        "A sequential chain of agents where each agent's output feeds directly "
        "into the next agent's input; like a data-processing pipeline but each "
        "stage is an LLM-powered agent. Components: ordered list of pipeline agents, "
        "each with a defined input/output schema, pipeline controller/orchestrator, "
        "error handling with stage-level retry, optional dead-letter queue. "
        "Tech: LangChain SequentialChain, custom pipeline orchestrator, "
        "streaming output where possible. Each stage should transform or refine "
        "the artifact rather than just passing it through. Anti-pattern: a "
        "pipeline stage that ignores its input and generates independently."
    ),
    "plan-execute": (
        "Separation of concerns: a Planner agent thinks and produces a step-by-step "
        "plan; an Executor agent (or agent pool) carries out the steps, reporting "
        "back. The Planner may revise the plan based on execution feedback. "
        "Components: planner agent, executor agent(s), plan store/versioning, "
        "feedback loop, step-tracking/state. Tech: plan-fix-execute loops, "
        "temporal planning, reflective LLM patterns. The planner and executor "
        "may use different models or prompts suited to their roles. "
        "Anti-pattern: a planner that cannot see execution feedback, producing "
        "plans that ignore real-world constraints."
    ),
    "single-agent-loop": (
        "A single agent repeatedly selects tools, executes them, and observes "
        "results to converge on a goal — the classic ReAct/ Reflexion loop. "
        "Components: single agent with tool registry, working memory or context "
        "accumulation, loop termination condition, reflection/reasoning trace. "
        "Tech: ReAct prompting, tool-use LLMs, structured inner monologue, "
        "short-term memory accumulation. Best for tasks with a clear terminal "
        "condition. Anti-pattern: loops that never terminate because the agent "
        "cannot recognize completion."
    ),
    "swarm": (
        "Multiple agents coordinate through emergent, asynchronous interactions "
        "without centralized control; coordination emerges from local agent "
        "rules and message passing. Components: autonomous agents, pub-sub or "
        "blackboard for agent-to-agent communication, local state per agent, "
        "emergent behavior via field-specific aggregation rules. "
        "Tech: agent messaging systems, topic-based pub/sub, shared datastore "
        "with eventual consistency. Each agent is largely independent and makes "
        "local decisions. Anti-pattern: a swarm that actually needs sequential "
        "coordination forced into emergent semantics."
    ),
}


def get_topology_guidance(topology: str) -> str:
    """Return canonical-shape guidance for ``topology`` with a safe default fallback."""
    return TOPOLOGY_GUIDANCE.get(topology, DEFAULT_TOPOLOGY_GUIDANCE)
