FROM python:3.13-slim

WORKDIR /app

# Install only MCP server dependencies
COPY mcp/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the MCP server code
COPY mcp/server.py ./server.py
COPY mcp/vector_utils.py ./vector_utils.py

# Railway provides PORT env var; default to 8001 for local testing
ENV PORT=8001
ENV HOST=0.0.0.0

EXPOSE ${PORT}

CMD ["python", "server.py"]
