import asyncio
import json
import os
import io
import sys
from typing import Callable

from agency_swarm import Agency

from .pdf import save_research_to_pdf

from pathlib import Path


class FilteredStderr(io.TextIOBase):
    def write(self, s):
        if "Failed to convert ToolCallItem using to_input_item()" in s:
            return  # Ignore this line
        sys.__stderr__.write(s)

sys.stderr = FilteredStderr()


def _print_debug(event, seen):
    """Enhanced debug logging to show key research events."""
    event_type = getattr(event, "type", None)

    # Show new event types once
    if (
        event_type
        and event_type not in seen
        and event_type != "response.output_text.delta"
    ):
        print(f"\n[DEBUG] Event: {event_type}")
        seen.add(event_type)

        # Show additional details for key events
        if event_type == "raw_response_event":
            if hasattr(event, "data") and hasattr(event.data, "item"):
                action = getattr(event.data.item, "action", None)
                if action and getattr(action, "type", None) == "search":
                    query_text = getattr(action, "query", "")
                    if query_text:
                        print(f"[DEBUG]   → Search Query: {query_text}")

        elif event_type == "handoff_call_item":
            if hasattr(event, "raw_item"):
                function_name = getattr(event.raw_item, "name", "Unknown")
                print(f"[DEBUG]   → Handoff: {function_name}")

    # Show agent switches
    elif event_type == "agent_updated_stream_event" and hasattr(event, "new_agent"):
        agent_name = event.new_agent.name
        print(f"\n[DEBUG] 🔄 Agent Switch: {agent_name}")

    # Show web searches
    elif event_type == "raw_response_event":
        if hasattr(event, "data") and hasattr(event.data, "item"):
            action = getattr(event.data.item, "action", None)
            if action and getattr(action, "type", None) == "search":
                query_text = getattr(action, "query", "")
                if query_text:
                    print(f"[DEBUG] 🔍 Web Search: {query_text}")

async def stream_demo(
    agency: Agency,
    save_pdf: Callable[[str, str], str] | None = None,
    debug: bool = True,
):
    """Interactive terminal demo with 5-question prompts per round."""
    print("Civil Engineering: Scope of Work")
    print("Type 'quit' at any prompt to exit.")
   

    # --- Collect 5 answers from the user (used together for one research paper) ---
    prompts = [
        ("Who is the project owner?", "project_owner"),
        ("What is the project objective?", "project_objective"),
        ("Estimated project budget?", "project_budget"),
        ("Project Information (e.g., Roadway Design & Culvert Construction):", "project_info"),
        ("What will be some technical services?", "technical_services"),
        ("Estimate project completion:", "completion_estimate"),
    ]
    print("\n")
    print("Please answer the following questions: ")
    user_answers = []
    for question, key in prompts:
        ans = input(f"{question} ").strip()
        if ans.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            return
        user_answers.append(ans or "No response provided.")

    # --- Build one combined prompt for a single research paper ---
    combined_prompt_parts = [
        "Create a comprehensive Scope of Work document for Civil Engineering based on the following project details:\n",
    ]
    for (question, _), answer in zip(prompts, user_answers):
        combined_prompt_parts.append(f"• {question}\n  {answer}\n")
    combined_prompt_parts.append(
        "\nProduce a detailed civil enginnering report that synthesizes all of the above into a cohesive Scope of Work document."
    )
    combined_prompt = "".join(combined_prompt_parts)

    # --- Single research run → one paper ---
    print(f"\n Creating a Scope of Work for {user_answers[0]}...")
    print(" Response: ", end="", flush=True)

    full_text = ""
    clarifying_text = ""
    current_agent = None
    seen_events = set()
    stream_error = None

    try:
        async for event in agency.get_response_stream(combined_prompt):
            if debug:
                _print_debug(event, seen_events)

            if getattr(event, "type", None) == "agent_updated_stream_event" and hasattr(event, "new_agent"):
                current_agent = event.new_agent.name
                print(f"\n\n🔄 Switched to: {current_agent}")
                print("─" * 50)
                continue

            if hasattr(event, "data"):
                data = event.data
                if getattr(data, "type", "") == "response.output_text.delta":
                    delta = getattr(data, "delta", "")
                    if delta:
                        if current_agent == "Clarifying Questions Agent":
                            clarifying_text += delta
                        else:
                            print(delta, end="", flush=True)
                            full_text += delta

            elif getattr(event, "type", None) == "raw_response_event":
                if hasattr(event, "data") and hasattr(event.data, "item"):
                    action = getattr(event.data.item, "action", None)
                    if action and getattr(action, "type", None) == "search":
                        query_text = getattr(action, "query", "")
                        if query_text:
                            print(f"\n🔍 [Web Search]: {query_text}")

    except Exception as e:
        stream_error = e

    # Save one PDF for the complete research paper
    if save_pdf and full_text.strip() and len(full_text) > 50:
        save_pdf(full_text, "scope_of_work")

    print("\nScope of Work has been completed!\n" + "=" * 50)
    if stream_error:
        print(f"\n Error during streaming: {stream_error}")

    print("\n Document saved! Exiting.")


def copilot_demo(agency: Agency, save_pdf_func: Callable[[str, str], str] | None = None):
    """Launch Copilot UI demo with optional PDF saving."""
    try:
        from agency_swarm.ui.demos.launcher import CopilotDemoLauncher

        if save_pdf_func:
            # Wrap the existing agency with PDF saving logic
            original_get_response = agency.get_response

            def _get_response_and_save(query: str, **kwargs):
                response = original_get_response(query, **kwargs)
                save_pdf_func(str(response), query)
                return response

            agency.get_response = _get_response_and_save  # type: ignore

        launcher = CopilotDemoLauncher()
        launcher.start(agency)
    except ImportError:
        print("❌ Copilot demo requires additional dependencies")
        print("Install with: pip install agency-swarm[copilot]")


# -------------------------
# Save PDF
# -------------------------
def save_research_report(response, query, output_dir="reports"):
    """Save response to PDF with error handling."""
    try:
        pdf_path = save_research_to_pdf(
            research_content=str(response), query=query, output_dir=output_dir
        )
        print(f"\n Scope of Work Document saved to: {pdf_path}")
        return pdf_path
    except Exception as e:
        print(f"\n❌ Error saving PDF: {e}")
        return None


# -------------------------
# Run Agency Demo
# -------------------------
def run_agency_demo(agency: Agency):
    """Run the agency demo, either in terminal or Copilot UI."""
    # Files directory
    files_dir = Path("files")
    if files_dir.exists() and files_dir.is_dir():
        print(f"📁 Found files directory with {len(list(files_dir.glob('*')))} files")

    # MCP configuration
    mcp_url = os.getenv("MCP_SERVER_URL", "http://localhost:8001/sse")
    if "ngrok" in mcp_url:
        print("Using ngrok tunnel for public access")
    elif "localhost" in mcp_url:
        print(" Using localhost - OK for local testing, but OpenAI API needs public URL (use ngrok)")

    if len(sys.argv) > 1 and sys.argv[1] in ["--ui", "--copilot"]:
        print("Launching Copilot UI...")
        copilot_demo(agency, save_research_report)
    else:
        print("\n")
        print("Launching Research Agent...")
        asyncio.run(stream_demo(agency, save_research_report))