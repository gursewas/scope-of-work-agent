#!/usr/bin/env python3
"""
Sample MCP Server for Deep Research API Integration

This server implements the Model Context Protocol (MCP) with search and fetch
capabilities designed to work with ChatGPT's deep research feature.
"""

import logging
import os
from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from openai import OpenAI
from vector_utils import detect_vector_store_id

# Load environment variables from .env file
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai_client = OpenAI()

# Vector store ID (detected at runtime)
VECTOR_STORE_ID = None


def create_server():
    """Create MCP server with search and fetch tools."""
    mcp = FastMCP(
        name="Sample Deep Research MCP Server",
        instructions="""
        This MCP server provides search and document retrieval capabilities for deep research.
        Use the search tool to find relevant documents based on keywords, then use the fetch
        tool to retrieve complete document content with citations.
        """,
    )

    @mcp.tool()
    async def search(query: str) -> dict[str, list[dict[str, Any]]]:
        """Search vector store for relevant documents. Returns list with id, title, text snippet."""
        if not query or not query.strip():
            return {"results": []}

        if not openai_client:
            logger.error("OpenAI client not initialized - API key missing")
            raise ValueError("OpenAI API key is required for vector store search")

        if not VECTOR_STORE_ID:
            logger.error("Vector store ID not configured")
            raise ValueError("Vector store ID is required for search")

        try:
            # Search the vector store using OpenAI API
            logger.info(
                f"Searching vector store {VECTOR_STORE_ID} for query: '{query}'"
            )

            response = openai_client.vector_stores.search(
                vector_store_id=VECTOR_STORE_ID, query=query
            )

            results = []

            # Process search results
            if hasattr(response, "data") and response.data:
                for i, item in enumerate(response.data):
                    item_id = getattr(item, "file_id", f"vs_{i}")
                    item_filename = getattr(item, "filename", f"Document {i + 1}")

                    # Extract text content
                    content_list = getattr(item, "content", [])
                    text_content = ""
                    if content_list and len(content_list) > 0:
                        first_content = content_list[0]
                        if hasattr(first_content, "text"):
                            text_content = first_content.text
                        elif isinstance(first_content, dict):
                            text_content = first_content.get("text", "")

                    if not text_content:
                        text_content = "No content available"

                    text_snippet = (
                        text_content[:200] + "..."
                        if len(text_content) > 200
                        else text_content
                    )

                    result = {
                        "id": item_id,
                        "title": item_filename,
                        "text": text_snippet,
                        "url": f"https://platform.openai.com/storage/files/{item_id}",
                    }

                    results.append(result)

            logger.info(f"Vector store search returned {len(results)} results")
            return {"results": results}

        except Exception as e:
            logger.error(f"Error during vector store search: {e}")
            # Return empty results instead of raising to prevent server crash
            return {"results": []}

    @mcp.tool()
    async def fetch(id: str) -> dict[str, Any]:
        """Retrieve complete document content by ID for analysis and citation."""
        if not id:
            raise ValueError("Document ID is required")

        if not openai_client:
            logger.error("OpenAI client not initialized - API key missing")
            raise ValueError(
                "OpenAI API key is required for vector store file retrieval"
            )

        if not VECTOR_STORE_ID:
            logger.error("Vector store ID not configured")
            raise ValueError("Vector store ID is required for file retrieval")

        try:
            logger.info(f"Fetching content from vector store for file ID: {id}")

            # Fetch file content from vector store
            content_response = openai_client.vector_stores.files.content(
                vector_store_id=VECTOR_STORE_ID, file_id=id
            )

            # Get file metadata
            file_info = openai_client.vector_stores.files.retrieve(
                vector_store_id=VECTOR_STORE_ID, file_id=id
            )

            # Extract content
            file_content = ""
            if hasattr(content_response, "data") and content_response.data:
                content_parts = []
                for content_item in content_response.data:
                    if hasattr(content_item, "text"):
                        content_parts.append(content_item.text)
                file_content = "\n".join(content_parts)
            else:
                file_content = "No content available"

            filename = getattr(file_info, "filename", f"Document {id}")

            result = {
                "id": id,
                "title": filename,
                "text": file_content,
                "url": f"https://platform.openai.com/storage/files/{id}",
                "metadata": None,
            }

            # Add metadata if available from file info
            if hasattr(file_info, "attributes") and file_info.attributes:
                result["metadata"] = file_info.attributes

            logger.info(f"Successfully fetched vector store file: {id}")
            return result

        except Exception as e:
            logger.error(f"Error fetching vector store file {id}: {e}")
            # Return error result instead of raising to prevent server crash
            return {
                "id": id,
                "title": f"Error retrieving document {id}",
                "text": f"Error: {str(e)}",
                "url": f"https://platform.openai.com/storage/files/{id}",
                "metadata": None,
            }

    return mcp


def main():
    """Main function to start the MCP server."""
    global VECTOR_STORE_ID

    # Verify OpenAI client is initialized
    if not openai_client:
        logger.error(
            "OpenAI API key not found. Please set OPENAI_API_KEY environment variable."
        )
        raise ValueError("OpenAI API key is required")

    # Detect vector store ID with proper error handling
    try:
        VECTOR_STORE_ID = detect_vector_store_id()
        logger.info(f"Using vector store: {VECTOR_STORE_ID}")
    except ValueError as e:
        logger.error(f"Vector store detection failed: {e}")
        raise

    # Create the MCP server
    server = create_server()

    # Start server
    logger.info("Starting MCP server...")

    try:
        # Use direct SSE app method for FastMCP 2.2.0 compatibility on port 8001
        import uvicorn

        app = server.sse_app()
        # Use Railway's PORT env var if available, fallback to 8001 for local dev
        port = int(os.environ.get("PORT", 8001))
        uvicorn.run(app, host="0.0.0.0", port=port)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()
