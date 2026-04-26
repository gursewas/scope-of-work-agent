#!/usr/bin/env python3
"""
Basic Research Agency

Single agent with o4-mini-deep-research model.
Using Agency Swarm v1.x with proper streaming pattern.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from agency_swarm import Agency, Agent
from agents import ModelSettings, WebSearchTool, HostedMCPTool

from utils import run_agency_demo

from dotenv import load_dotenv

load_dotenv()

# Get MCP server URL from environment or use default
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/sse")
# Limit total tool calls (web search + file search + MCP) per question. Default 5 to reduce web searches.
MAX_TOOL_CALLS = int(os.getenv("MAX_TOOL_CALLS", "4"))

print(f"MCP Server URL: {MCP_SERVER_URL}")
print(f"Max web search calls per question: {MAX_TOOL_CALLS}")

# Basic Research Agent - o4-mini-deep-research with web search
research_agent = Agent(
    name="Research Agent",
    model="o4-mini-deep-research-2025-06-26",
    tools=[
        WebSearchTool(),
        HostedMCPTool(
            tool_config={
                "type": "mcp",
                "server_label": "file_search",
                "server_url": MCP_SERVER_URL,
                "require_approval": "never",
            }
        ),
    ],
    instructions="""Create a Scope of Work for Civil Engineering.

Always format your response in well-structured markdown:
- Use ## and ### headings to organize sections
- Use bullet lists (- item) and numbered lists (1. item) for enumerations
- Use **bold** for emphasis on key terms
- Separate all block-level elements (headings, lists, paragraphs) with blank lines
- Do NOT use code blocks or fenced code unless presenting actual code""",

    model_settings=ModelSettings(extra_args={"max_tool_calls": MAX_TOOL_CALLS}),
)

# Create the agency
agency = Agency(research_agent)

if __name__ == "__main__":
    run_agency_demo(agency)
