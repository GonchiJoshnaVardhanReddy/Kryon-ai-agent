"""Kryon subagents — 8 specialized reasoning agents.

The reasoning layer: each subagent has a system prompt, an output
schema, and restricted graph write permissions. Subagents never touch
out-of-scope assets (File #7 enforces), never promote to Findings
without verify (File #4 enforces), and never run real LLM calls
without going through ``kryon.litellm.client`` (File #9).

Quickstart::

    from kryon.subagents import get_subagent_class
    from kryon.subagents.base import MockLLMClient

    cls = get_subagent_class("recon-passive")
    sa = cls(llm=MockLLMClient(), graph=graph, audit=audit, bus=bus, config=config)
    result = await sa.run(ctx)
    print(result.status, result.nodes_written)
"""

from kryon.subagents.base import MockLLMClient, Subagent
from kryon.subagents.impl import (
    AnalysisHypothesisSubagent,
    BlueTeamSubagent,
    ExploitSubagent,
    PostExploitSubagent,
    ReconActiveSubagent,
    ReconPassiveSubagent,
    ReportSubagent,
    VerifySubagent,
)
from kryon.subagents.prompts import (
    ANALYSIS_HYPOTHESIS_PROMPT,
    BLUE_TEAM_PROMPT,
    EXPLOIT_PROMPT,
    POST_EXPLOIT_PROMPT,
    RECON_ACTIVE_PROMPT,
    RECON_PASSIVE_PROMPT,
    REPORT_PROMPT,
    VERIFY_PROMPT,
)
from kryon.subagents.registry import (
    SUBAGENTS,
    get_subagent_class,
    list_subagents,
)
from kryon.subagents.schemas import (
    AnalysisHypothesisOutput,
    BlueTeamOutput,
    ExploitOutput,
    PostExploitOutput,
    ReconActiveOutput,
    ReconPassiveOutput,
    ReportOutput,
    VerifyOutput,
)
from kryon.subagents.types import (
    LLMClient,
    LLMResponse,
    SubagentContext,
    SubagentResult,
    SubagentStatus,
)

__all__ = [  # noqa: RUF022 — multi-section export list
    # Base
    "MockLLMClient",
    "Subagent",
    # Types
    "LLMClient",
    "LLMResponse",
    "SubagentContext",
    "SubagentResult",
    "SubagentStatus",
    # Schemas
    "AnalysisHypothesisOutput",
    "BlueTeamOutput",
    "ExploitOutput",
    "PostExploitOutput",
    "ReconActiveOutput",
    "ReconPassiveOutput",
    "ReportOutput",
    "VerifyOutput",
    # Implementations
    "AnalysisHypothesisSubagent",
    "BlueTeamSubagent",
    "ExploitSubagent",
    "PostExploitSubagent",
    "ReconActiveSubagent",
    "ReconPassiveSubagent",
    "ReportSubagent",
    "VerifySubagent",
    # Prompts
    "ANALYSIS_HYPOTHESIS_PROMPT",
    "BLUE_TEAM_PROMPT",
    "EXPLOIT_PROMPT",
    "POST_EXPLOIT_PROMPT",
    "RECON_ACTIVE_PROMPT",
    "RECON_PASSIVE_PROMPT",
    "REPORT_PROMPT",
    "VERIFY_PROMPT",
    # Registry
    "SUBAGENTS",
    "get_subagent_class",
    "list_subagents",
]
