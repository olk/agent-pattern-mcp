from pydantic import BaseModel, Field


class LayerDefinition(BaseModel):
    name: str
    description: str
    components: list[str]
    patterns: list[str]


class ReactSingleAgentTemplate(BaseModel):
    name: str = "react-single-agent"
    description: str = "Single ReAct agent with interleaved reasoning and tool execution"
    components: list[LayerDefinition] = Field(
        default_factory=lambda: [
            LayerDefinition(
                name="Agent Loop",
                description="ReAct agent: Thought → Action → Observation → ...",
                components=["LLM", "Tool Registry", "Memory"],
                patterns=["react"],
            ),
        ]
    )
    best_practices: list[str] = Field(
        default_factory=lambda: [
            "Keep tool descriptions precise — they become the LLM's action space",
            "Log the full reasoning trace for observability",
            "Set explicit step budgets to prevent runaway loops",
            "Use structured output for reliable tool parsing",
        ]
    )


class SupervisorWorkerTemplate(BaseModel):
    name: str = "supervisor-worker"
    description: str = "Hierarchical supervisor decomposes tasks and delegates to specialized workers"
    components: list[LayerDefinition] = Field(
        default_factory=lambda: [
            LayerDefinition(
                name="Supervisor",
                description="Plans, decomposes, routes, and aggregates",
                components=["Supervisor Agent", "Task Router"],
                patterns=["supervisor-worker"],
            ),
            LayerDefinition(
                name="Workers",
                description="Specialized executors for sub-task types",
                components=["Retriever Worker", "Executor Worker", "Critic Worker"],
                patterns=["supervisor-worker", "tool-use"],
            ),
        ]
    )
    best_practices: list[str] = Field(
        default_factory=lambda: [
            "Supervisor should be stateless between delegations",
            "Workers should confirm task completion before supervisor aggregates",
            "Add checkpointing for long-running task delegations",
            "Implement timeouts per worker to prevent cascade delays",
        ]
    )


class MultiAgentDebateTemplate(BaseModel):
    name: str = "multi-agent-debate"
    description: str = "Multiple agents argue distinct positions with a judge synthesizing verdicts"
    components: list[LayerDefinition] = Field(
        default_factory=lambda: [
            LayerDefinition(
                name="Proponent Agents",
                description="Argue one position each",
                components=["Proponent A", "Proponent B"],
                patterns=["multi-agent-debate"],
            ),
            LayerDefinition(
                name="Judge",
                description="Scores arguments and synthesizes final verdict",
                components=["Judge Agent"],
                patterns=["evaluator-optimizer"],
            ),
        ]
    )
    best_practices: list[str] = Field(
        default_factory=lambda: [
            "Use 2-3 agents over 2-3 rounds to control token cost",
            "Reveal positions simultaneously to prevent anchoring",
            "Score arguments by evidence before letting judge see positions",
        ]
    )


class AgenticRAGTemplate(BaseModel):
    name: str = "agentic-rag"
    description: str = "Agentic RAG with iterative retrieval, self-reflection, and re-querying"
    components: list[LayerDefinition] = Field(
        default_factory=lambda: [
            LayerDefinition(
                name="Retrieval Agent",
                description="Plans retrieval, selects sources, re-queries on low relevance",
                components=["Retriever Agent", "Query Rewriter"],
                patterns=["agentic-rag", "corrective-rag"],
            ),
            LayerDefinition(
                name="Generation Agent",
                description="Synthesizes final answer from retrieved context",
                components=["LLM", "Context Manager"],
                patterns=["naive-rag"],
            ),
        ]
    )
    best_practices: list[str] = Field(
        default_factory=lambda: [
            "Evaluate retrieved documents before generation — retry if relevance < threshold",
            "Use query rewriting to handle ambiguous questions",
            "Log retrieval steps for debugging",
        ]
    )


RESOURCES: dict[str, BaseModel] = {
    "react-single-agent-template": ReactSingleAgentTemplate(),
    "supervisor-worker-template": SupervisorWorkerTemplate(),
    "multi-agent-debate-template": MultiAgentDebateTemplate(),
    "agentic-rag-template": AgenticRAGTemplate(),
}
