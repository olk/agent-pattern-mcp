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
Drift tripwire for error-code constants that exist in two modules.

src/tools/design.py re-declares ERROR_REQUIREMENTS_VALIDATION instead of
importing it from src/errors.py. Until that is consolidated, this test pins
the two copies to the same value so silent drift fails the unit gate.
The canonical definition lives in src/errors.py.
"""

from src import errors
from src.tools import design


class TestErrorConstantConsistency:
    def test_requirements_validation_code_matches_canonical_definition(self) -> None:
        """The design.py copy of ERROR_REQUIREMENTS_VALIDATION must not drift from src.errors."""
        assert design.ERROR_REQUIREMENTS_VALIDATION == errors.ERROR_REQUIREMENTS_VALIDATION

    def test_canonical_requirements_validation_code_is_stable(self) -> None:
        """The public error code ERR_001 is part of the tool-error contract."""
        assert errors.ERROR_REQUIREMENTS_VALIDATION == "ERR_001"
