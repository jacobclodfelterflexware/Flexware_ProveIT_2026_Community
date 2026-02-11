"""MCP Server for MQTT topic mapping management and similarity search."""
import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
import uvicorn

from .config import config
from .clients.ingestor_client import get_ingestor_client, close_ingestor_client
from .clients.middleware_client import get_middleware_client, close_middleware_client
from .clients.postgres_client import get_postgres_client, close_postgres_client

# Import tool registration functions
from .tools.topic_mappings import register_mapping_tools
from .tools.key_transforms import register_transform_tools
from .tools.unmapped_topics import register_unmapped_tools
from .tools.similarity_search import register_similarity_tools
from .tools.hierarchical import register_hierarchical_tools
from .tools.monitoring import register_monitoring_tools

# Import REST API wrapper
from .rest_api import create_rest_app

logging.basicConfig(level=getattr(logging, config.server.log_level))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize clients on startup, cleanup on shutdown."""
    logger.info("Initializing MCP server clients...")
    await get_postgres_client()
    await get_ingestor_client()
    await get_middleware_client()
    logger.info("MCP server ready")
    yield
    logger.info("Shutting down MCP server...")
    await close_postgres_client()
    await close_ingestor_client()
    await close_middleware_client()
    logger.info("MCP server shutdown complete")


# Create FastMCP server
mcp = FastMCP(
    name="mqtt-middleware-mcp",
    instructions="MCP server for MQTT topic mapping management and similarity search",
    host=config.server.host,
    port=config.server.port,
    lifespan=lifespan
)

# Register all tools
register_mapping_tools(mcp)
register_transform_tools(mcp)
register_unmapped_tools(mcp)
register_similarity_tools(mcp)
register_hierarchical_tools(mcp)
register_monitoring_tools(mcp)


def run_rest_api():
    """Run the REST API server in a separate thread."""
    rest_port = int(os.getenv("REST_API_PORT", "8081"))
    rest_app = create_rest_app()
    logger.info(f"Starting REST API wrapper on port {rest_port}")
    uvicorn.run(
        rest_app,
        host=config.server.host,
        port=rest_port,
        log_level="info"
    )


def main():
    """Entry point supporting multiple transports."""
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport in ("http", "streamable-http"):
        # Start REST API in a background thread
        rest_thread = threading.Thread(target=run_rest_api, daemon=True)
        rest_thread.start()
        logger.info("REST API thread started")

        # Run MCP server in main thread
        mcp.run(transport="streamable-http")
    else:
        # Default: stdio for Claude Desktop (no REST API)
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
