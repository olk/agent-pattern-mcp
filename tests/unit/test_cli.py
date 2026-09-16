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
Unit tests for the src.main click CLI entry point.

Covers:
- --health fast path prints OK and exits 0 without starting the server
- Option defaults and pass-through of config-path / transport / host / port
- Invalid transport choice and non-integer port are rejected (usage error)
- server_main is invoked exactly once per normal invocation
"""

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from src.main import cli


class TestHealthFlag:
    def test_health_flag_prints_ok_and_exits_zero(self) -> None:
        """--health short-circuits: prints OK, exit code 0, server never started."""
        runner = CliRunner()
        with patch("src.main.server_main", new=AsyncMock()) as mock_server_main:
            result = runner.invoke(cli, ["--health"])

        assert result.exit_code == 0
        assert result.output == "OK\n"
        mock_server_main.assert_not_called()


class TestServerWiring:
    def test_default_invocation_passes_none_options_to_server_main(self) -> None:
        """Without options, all four server_main arguments default to None."""
        runner = CliRunner()
        with patch("src.main.server_main", new=AsyncMock()) as mock_server_main:
            result = runner.invoke(cli, [])

        assert result.exit_code == 0
        mock_server_main.assert_called_once_with(
            config_path=None,
            transport=None,
            host=None,
            port=None,
        )

    def test_explicit_options_are_forwarded_to_server_main(self) -> None:
        """All CLI options are passed through to server_main unchanged."""
        runner = CliRunner()
        with patch("src.main.server_main", new=AsyncMock()) as mock_server_main:
            result = runner.invoke(
                cli,
                [
                    "--config-path",
                    "/tmp/config.json",
                    "--transport",
                    "streamable-http",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "9999",
                ],
            )

        assert result.exit_code == 0
        mock_server_main.assert_called_once_with(
            config_path="/tmp/config.json",
            transport="streamable-http",
            host="0.0.0.0",
            port=9999,
        )

    def test_stdio_transport_is_accepted(self) -> None:
        """The stdio transport choice is a valid option value."""
        runner = CliRunner()
        with patch("src.main.server_main", new=AsyncMock()):
            result = runner.invoke(cli, ["--transport", "stdio"])

        assert result.exit_code == 0


class TestOptionValidation:
    def test_invalid_transport_choice_is_rejected(self) -> None:
        """An unknown transport value produces a usage error (exit code 2)."""
        runner = CliRunner()
        with patch("src.main.server_main", new=AsyncMock()) as mock_server_main:
            result = runner.invoke(cli, ["--transport", "websocket"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output
        mock_server_main.assert_not_called()

    def test_non_integer_port_is_rejected(self) -> None:
        """A non-integer port produces a usage error (exit code 2)."""
        runner = CliRunner()
        with patch("src.main.server_main", new=AsyncMock()) as mock_server_main:
            result = runner.invoke(cli, ["--port", "not-a-number"])

        assert result.exit_code != 0
        mock_server_main.assert_not_called()
