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
Prompt examples package — hand-crafted few-shot examples for agent pattern pipeline prompts.

Examples are imported at module level to catch schema drift at import time.
If a schema changes, importing this module raises ValidationError immediately.

Exports:
- AGENT_SYSTEM_DESIGN_EXAMPLE: Few-shot example of a complete AgentSystemDesign
- AGENT_SYSTEM_EVALUATION_EXAMPLE: Few-shot example of an AgentSystemEvaluation
- REQUIREMENT_WEIGHTS_EXAMPLE_PEAKED/SPARSE/NEGATIVE/CONFLICT: Calibration
  examples for the ANALYZE-phase weight extraction (validated at import time)
- get_topology_guidance: Return canonical-shape guidance for a given topology
"""

from src.prompts.examples import (
    AGENT_SYSTEM_DESIGN_EXAMPLE,
    AGENT_SYSTEM_EVALUATION_EXAMPLE,
    REQUIREMENT_WEIGHTS_EXAMPLE_CONFLICT,
    REQUIREMENT_WEIGHTS_EXAMPLE_NEGATIVE,
    REQUIREMENT_WEIGHTS_EXAMPLE_PEAKED,
    REQUIREMENT_WEIGHTS_EXAMPLE_SPARSE,
)
from src.prompts.topology_guidance import get_topology_guidance

__all__ = [
    "AGENT_SYSTEM_DESIGN_EXAMPLE",
    "AGENT_SYSTEM_EVALUATION_EXAMPLE",
    "REQUIREMENT_WEIGHTS_EXAMPLE_CONFLICT",
    "REQUIREMENT_WEIGHTS_EXAMPLE_NEGATIVE",
    "REQUIREMENT_WEIGHTS_EXAMPLE_PEAKED",
    "REQUIREMENT_WEIGHTS_EXAMPLE_SPARSE",
    "get_topology_guidance",
]
