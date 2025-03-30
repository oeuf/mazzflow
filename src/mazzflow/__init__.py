"""Mazzflow - MCP GitHub integration tool."""

from .mcp_client import analyze_pull_request, create_review_checklist, generate_code
from .mcp_server import app

__version__ = "0.1.0"
__all__ = [
    "analyze_pull_request",
    "app",
    "create_review_checklist",
    "generate_code",
]
