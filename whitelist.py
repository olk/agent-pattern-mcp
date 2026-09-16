# Vulture whitelist: symbol references invisible to static analysis.
# https://github.com/jendrikseipp/vulture#whitelists
#
# Used by `make deadcode` / CI:
#   vulture src examples whitelist.py --min-confidence 80 \
#       --ignore-decorators "@step,@field_validator,@model_validator,@*.resource,@*.prompt"
#
# Add an entry here ONLY for a symbol that is provably live but has no static
# reference, and document the dispatch mechanism next to it. Prune entries when
# the symbol dies.

# MCP tools are dispatched dynamically via MCPAgentPatternServer._TOOL_METHOD_MAP
# (src/server.py): getattr(tool_instance, method_name) -> server.add_tool().
tool.list_agent_patterns
tool.get_agent_pattern
tool.submit_job
tool.get_status
tool.cancel
tool.design
tool.analyze
tool.generate
tool.evaluate

# CLI entry point declared in pyproject.toml [project.scripts].
cli

# MCP prompts registered by src/mcp_prompts/__init__.py::register_prompts
# via @server.prompt decorators (covered by --ignore-decorators, kept here
# for lower-confidence manual audits).
design_agent_system_workflow
explore_pattern_catalog
evaluate_my_agent_system
compare_agent_topologies

# Interface-compatibility parameters: accepted-and-ignored to satisfy the
# upstream BaseEmbedding / BaseReader signatures our classes extend.
# VectorStoreIndex node embedding passes show_progress to the upstream
# BaseEmbedding.get_text_embedding_batch (batching is now upstream).
show_progress
# PatternJSONReader.load_data(extra_info=...) per BaseReader contract.
extra_info

# HybridPatternRetriever.retrieve(user_domain=...) is kept for API compat
# with callers that previously passed raw user input; the parameter is now
# derived from normalized_domain internally.
src.patterns.retriever.user_domain
