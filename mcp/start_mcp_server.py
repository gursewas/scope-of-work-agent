#!/usr/bin/env python3
"""
Convenience script to start the MCP server for Deep Research Agent Tutorial
"""

import sys
from pathlib import Path

# Add the mcp directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    try:
        from server import main

        print("🚀 Starting MCP Server for Deep Research Agent Tutorial...")
        print("📁 Server will auto-detect vector store from files_vs_* directories")
        print("🔌 Server will run on http://localhost:8001")
        print("⚠️  Keep this terminal open while using the research agencies")
        print("📝 Press Ctrl+C to stop the server")
        print("=" * 60)
        main()
    except KeyboardInterrupt:
        print("\n👋 MCP Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting MCP server: {e}")
        print("💡 Make sure you have:")
        print("   - Set OPENAI_API_KEY in your .env file")
        print("   - Run an agency first to create vector store")
        print("   - Installed all dependencies: pip install -r requirements.txt")
        sys.exit(1)
