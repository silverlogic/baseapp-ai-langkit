# Baseapp MCP - Integration Guide

## Overview

The `baseapp_mcp` is a Django module that provides a complete infrastructure for creating and managing MCP (Model Context Protocol) servers. It offers:

- **MCP Server** based on FastMCP with Streamable HTTP support
- **Authentication** via Google OAuth and API Key
- **Rate Limiting** configurable per user and per tool
- **Logging** of all tool calls
- **Usage tracking** for tokens and transformer calls
- **Reusable generic tools** (Search, Fetch)
- **Optional compatibility** with `baseapp_ai_langkit` for use in agents

## Installation

### 1. Install the Package

Add `baseapp-ai-langkit` with the `mcp` extra to your `requirements/base.txt`:

```txt
-e ./baseapp-ai-langkit[mcp]
```

Or if using pip directly:

```bash
pip install -e ./baseapp-ai-langkit[mcp]
```

### 2. Configure INSTALLED_APPS

In your `settings/base.py`, add the `baseapp_mcp` apps:

```python
INSTALLED_APPS = [
    # ... other apps
    "baseapp_mcp",
    "baseapp_mcp.logs",
    "baseapp_mcp.rate_limits",
]
```

### 3. Run Migrations

Run migrations to create the necessary tables:

```bash
python manage.py migrate baseapp_mcp_logs
python manage.py migrate baseapp_mcp_rate_limits
```

## Django Settings Configuration

### Required Settings

Add the following settings to your `settings/base.py`:

```python
# Application name (used in MCP server name)
APPLICATION_NAME = "MyApp"

# Base URL of the MCP server (used for OAuth redirects)
MCP_URL = env("MCP_URL", default="http://localhost:8001")

# Google OAuth credentials
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", default="")
```

### Optional Settings

#### Custom Server Instructions

```python
# Custom instructions for the MCP server
# If not defined, uses default instructions from baseapp_mcp
MCP_SERVER_INSTRUCTIONS = """
This server provides MCP (Model Context Protocol) tools for MyApp's knowledge base.
Use the search tool to find relevant documents, then use fetch to retrieve complete content.
"""
```

#### Custom Route Path

```python
# Custom route path for the MCP server endpoint
# Default: "mcp" (server will be available at /mcp)
MCP_ROUTE_PATH = "custom-mcp-path"  # Server will be available at /custom-mcp-path
```

#### Authentication Configuration

```python
# Disable OAuth authentication (API keys only)
MCP_ENABLE_OAUTH = True
```

**For custom authentication providers**, override the `get_auth()` method in a custom `DjangoFastMCP` subclass:

```python
# apps/mcp/app.py
from baseapp_mcp import DjangoFastMCP
from fastmcp.server.auth.providers.google import GoogleProvider

class MyDjangoFastMCP(DjangoFastMCP):
    @classmethod
    def get_auth(cls):
        # Your custom authentication logic
        # Return None for API keys only, or an AuthProvider instance
        return GoogleProvider(
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
            base_url=settings.MCP_URL,
            required_scopes=["openid", "email"],
        )

# Use your custom class
mcp = MyDjangoFastMCP.create(instructions=server_instructions)
```

#### Rate Limiting

```python
# General rate limiting (any server endpoint)
MCP_ENABLE_GENERAL_RATE_LIMITING = True
MCP_GENERAL_RATE_LIMIT_PERIOD = 60  # seconds
MCP_GENERAL_RATE_LIMIT_CALLS = 500  # maximum calls per period

# Tool-specific rate limiting (limit per user)
MCP_ENABLE_TOOL_RATE_LIMITING = True
MCP_TOOL_RATE_LIMIT_PERIOD = 60  # seconds
MCP_TOOL_RATE_LIMIT_CALLS = 30  # maximum calls per period
```

#### Monthly Limits

```python
# Monthly usage limits
MCP_ENABLE_MONTHLY_LIMITS = True
MCP_MONTHLY_TOKEN_LIMIT = 1000000  # token limit per month
MCP_MONTHLY_TRANSFORMER_CALL_LIMIT = 1000000  # transformer call limit per month
```

#### Email Validation (OAuth)

```python
# Regex rules for OAuth email validation
# Empty list = no validation
MCP_EMAIL_REGEX_RULES = [
    r"^[a-zA-Z0-9._%+-]+@example\.com$",  # Only allow @example.com emails
]
```

## Docker Compose Configuration

### Add web-mcp Service

Add the following service to your `docker-compose.yml`:

```yaml
services:
  # ... other services

  web-mcp:
    build:
      context: .
      dockerfile: Dockerfile
      target: dev-web-mcp
    image: ${COMPOSE_PROJECT_NAME}-web
    container_name: ${COMPOSE_PROJECT_NAME}_web_mcp
    env_file:
      - .env
    command:
      gunicorn -b 0.0.0.0:8000 apps.mcp.app:application --workers 1 --worker-class uvicorn.workers.UvicornWorker
    ports:
      - "8001:8000"
    volumes:
      - .:${APP_HOME}
      - media:/media
    depends_on:
      - web
    stdin_open: true
    tty: true
    develop:
      watch:
        - action: rebuild
          path: requirements/
```

### Configure Dockerfile

Make sure your `Dockerfile` has the `dev-web-mcp` target:

```dockerfile
FROM dev-requirements AS dev-web-mcp
ENV DEBUG on
EXPOSE 8000
WORKDIR /usr/src/app
CMD ["gunicorn", "-b", "0.0.0.0:8000", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker"]
```

## Environment Variables

Add the following variables to your `.env` file:

```bash
# MCP server URL
MCP_URL=http://localhost:8001

# Google OAuth (required for OAuth authentication)
GOOGLE_OAUTH_CLIENT_ID=your-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
```

## Creating an MCP App in Your Project

### 1. Directory Structure

Create the following structure in your project:

```
apps/
└── mcp/
    ├── __init__.py
    ├── app.py          # Tool registration and application export
    ├── utils.py        # Project-specific utilities (optional)
    ├── tools/          # Project-specific tool implementations
    │   ├── __init__.py
    │   ├── search_tool.py
    │   ├── fetch_tool.py
    │   └── ...
    └── tests/          # Tool tests
        ├── __init__.py
        ├── conftest.py
        └── ...
```

### 2. Create apps/mcp/app.py

This file creates your own MCP server instance and registers your tools:

```python
import asyncio
import logging
import typing as typ

from baseapp_mcp import (
    DjangoFastMCP,
    get_application,
    register_debug_tool,
    register_health_check_route,
)
from baseapp_mcp.utils import get_user_identifier
from fastmcp import Context

from apps.mcp.tools.search_tool import SearchTool
from apps.mcp.tools.fetch_tool import FetchTool

logger = logging.getLogger(__name__)

# Create your MCP server instance
server_instructions = """
Your custom server instructions here.
"""

mcp = DjangoFastMCP.create(instructions=server_instructions)

# Register optional helper tools/routes (optional)
register_debug_tool(mcp)
register_health_check_route(mcp)

# Register project-specific tools using the @mcp.tool decorator

@mcp.tool(
    title="Search Documents",
    description="Search documents by semantic similarity to find relevant documents.",
    annotations={"readOnlyHint": True},
)
async def search(ctx: Context, query: str) -> typ.Dict[str, typ.Any]:
    """
    Search for documents using a query string.

    Args:
        query: The search query string. Natural language queries work best.

    Returns:
        A dictionary with 'results' key containing list of matching documents.
    """
    user_identifier = get_user_identifier()

    def _search():
        tool = SearchTool(user_identifier)
        return tool.tool_func(query=query.strip())

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, _search)
    return results


@mcp.tool(annotations={"readOnlyHint": True})
async def fetch(ctx: Context, id: str) -> typ.Dict[str, typ.Any]:
    """
    Retrieve complete document content by ID.

    Args:
        id: The document ID to fetch.

    Returns:
        A dictionary containing the complete document.
    """
    user_identifier = get_user_identifier()

    def _fetch():
        tool = FetchTool(user_identifier)
        return tool.tool_func(id=id)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _fetch)
    return result


# Export the application for use with gunicorn/uvicorn
application = get_application(mcp)
```

## Creating Tools

### Example 1: Basic Tool Extending MCPTool

To create a tool from scratch, extend `MCPTool`:

```python
import logging
from typing import Any, Dict

from baseapp_mcp.tools import MCPTool
from baseapp_mcp import exceptions
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MyToolArgs(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = Field(default=10, description="Maximum number of results")


class MyTool(MCPTool):
    """
    Custom tool that performs a specific operation.
    """
    name: str = "my_tool"
    description: str = "My custom tool that does something specific"
    args_schema = MyToolArgs

    def tool_func_core(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """
        Main tool implementation.

        Args:
            query: Search query
            limit: Result limit

        Returns:
            Tuple (doc, simplified) where:
            - doc: Complete dictionary with data
            - simplified: Simplified version for logging
        """
        if not query or not query.strip():
            raise exceptions.MCPValidationError("Query cannot be empty")

        # Your logic here
        results = perform_search(query, limit)

        doc = {
            "results": results,
            "count": len(results),
        }

        simplified_response_for_logging = {
            "count": len(results),
        }

        return doc, simplified_response_for_logging
```

### Example 2: Tool Using Generic BaseSearchTool

To create a search tool, extend the generic `BaseSearchTool`:

```python
import logging
from typing import Any, Dict

from baseapp_mcp.tools import BaseSearchTool

from myapp.models import MyDocument

logger = logging.getLogger(__name__)


class MySearchTool(BaseSearchTool):
    """
    Specific SearchTool implementation for MyDocument.
    """

    def search(self, query: str) -> list[Dict[str, Any]]:
        """
        Search for documents using semantic similarity.

        Args:
            query: Search query string
        Returns:
            List of result dictionaries with at least 'id' and 'title' keys
        """
        return MyDocument.semantic_search(
            query=query,
            strip_html=True,
            use_snippets=True
        )
```

### Example 3: Tool Using Generic BaseFetchTool

To create a fetch tool, extend the generic `BaseFetchTool`:

```python
import logging
from typing import Any, Dict, Tuple

from baseapp_mcp.tools import BaseFetchTool
from baseapp_mcp import exceptions

from myapp.models import MyDocument
from myapp.utils import build_doc_from_document, strip_html

logger = logging.getLogger(__name__)


class MyFetchTool(BaseFetchTool):
    """
    Specific FetchTool implementation for MyDocument.
    """

    def fetch(self, search_term: str) -> MyDocument:
        """
        Fetch a document by ID.

        Args:
            search_term: Document ID
        Returns:
            MyDocument instance
        """
        try:
            return MyDocument.objects.get(id=int(search_term))
        except MyDocument.DoesNotExist:
            raise exceptions.MCPDataError(f"Document with ID {search_term} not found.")

    def content_processor(self, document: MyDocument) -> str:
        """
        Process document content to plain text.

        Args:
            document: MyDocument instance
        Returns:
            Plain text content
        """
        return strip_html(document.html)

    def doc_builder(
        self, document: MyDocument, content: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Build document dictionaries for full and simplified responses.

        Args:
            document: MyDocument instance
            content: Plain text content
        Returns:
            Tuple containing (full_doc_dict, simplified_doc_dict)
        """
        return build_doc_from_document(document, content)
```

### Example 4: Simple Tool Without Rate Limiting

By default tools don't have rate limiting or tracking:

```python
from baseapp_mcp.tools import MCPTool
from pydantic import BaseModel

class SimpleToolArgs(BaseModel):
    text: str

class SimpleTool(MCPTool):
    name = "simple_tool"
    description = "A simple tool"
    args_schema = SimpleToolArgs
    
    def tool_func_core(self, text: str):
        return {"result": text.upper()}, {"result": "processed"}
```

## Example 5: Simple Tool With Rate Limiting

For tools that need rate limiting or tracking:

```python
from baseapp_mcp.tools import MCPTool
from pydantic import BaseModel

class SimpleToolArgs(BaseModel):
    text: str

class SimpleTool(MCPTool):
    name = "simple_tool"
    description = "A simple tool"
    args_schema = SimpleToolArgs
    
    def __init__(self, user_identifier: str):
        # Enable rate limiting and tracking
        super().__init__(
            user_identifier,
            uses_tokens=True,
            uses_transformer_calls=True,
        )
    
    def tool_func_core(self, text: str):
        return {"result": text.upper()}, {"result": "processed"}
```

## Registering Tools on the Server

After creating your MCP server instance, register tools using the `@mcp.tool` decorator:

```python
# apps/mcp/app.py
from baseapp_mcp import DjangoFastMCP
from fastmcp import Context
from apps.mcp.tools.my_tool import MyTool
from baseapp_mcp.utils import get_user_identifier
import asyncio

# Create your MCP server instance
mcp = DjangoFastMCP.create()

@mcp.tool(
    title="My Custom Tool",
    description="Does something custom",
    annotations={"readOnlyHint": True},
)
async def my_tool(ctx: Context, query: str) -> dict:
    """
    Async wrapper for the tool.
    """
    user_identifier = get_user_identifier()
    
    def _execute():
        tool = MyTool(user_identifier)
        return tool.tool_func(query=query)
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _execute)
```

## Testing

### Test Structure

Create tests for your tools in `apps/mcp/tests/`:

```python
# apps/mcp/tests/test_my_tool.py
import pytest
from apps.mcp.tools.my_tool import MyTool
from baseapp_mcp import exceptions

@pytest.mark.django_db
def test_my_tool_success():
    tool = MyTool(user_identifier="test_user")
    result, simplified = tool.tool_func(query="test query")
    
    assert "results" in result
    assert result["count"] > 0

@pytest.mark.django_db
def test_my_tool_empty_query():
    tool = MyTool(user_identifier="test_user")
    
    with pytest.raises(exceptions.MCPValidationError):
        tool.tool_func(query="")
```

### Running Tests

```bash
# Run all MCP tests
pytest apps/mcp/tests/

# Run tests for a specific tool
pytest apps/mcp/tests/test_my_tool.py
```

## Advanced Configuration

### Customize Server Instructions

Server instructions can be customized via settings:

```python
# settings/base.py
MCP_SERVER_INSTRUCTIONS = """
This server provides MCP tools for MyApp.
Available tools:
- search: Search documents
- fetch: Retrieve document by ID
- my_tool: Custom tool for specific operations
"""
```

### Custom Lifespan Function

The lifespan function controls startup and shutdown behavior of the MCP server. By default, `baseapp_mcp` provides a `default_lifespan` that only logs startup/shutdown events.

You can create a custom lifespan function to add startup tasks (e.g., database connections, cache initialization) or cleanup tasks:

```python
# apps/mcp/app.py
from contextlib import asynccontextmanager
from baseapp_mcp import DjangoFastMCP, default_lifespan
import typing as typ
from fastmcp import FastMCP

@asynccontextmanager
async def custom_lifespan(mcp_server: FastMCP) -> typ.AsyncIterator[typ.Any]:
    """
    Custom lifespan with startup and cleanup tasks.
    """
    try:
        # Startup tasks
        logger.info("🚀 MCP Server starting up...")
        
        # Example: Initialize database connections
        # await initialize_db_pool()
        
        # Example: Load cache
        # await load_initial_cache()
        
        logger.info("✅ MCP Server startup complete")
        yield {"startup_time": "server_ready"}
        
    finally:
        # Cleanup tasks
        logger.info("🔄 MCP Server shutting down...")
        
        # Example: Close database connections
        # await close_db_pool()
        
        # Example: Save cache
        # await save_cache()
        
        logger.info("✅ MCP Server shutdown complete")

# Create server with custom lifespan
mcp = DjangoFastMCP.create(lifespan=custom_lifespan)
```

**Note**: The lifespan function receives the `FastMCP` server instance as a parameter, which can be useful for accessing server state or configuration.

### Rate Limiting per Tool

Rate limiting can be applied to tools by simply overriding some of the parameters of the `__init__` method in `MCPTool`. To enable it for a specific tool:

```python
class MyTool(MCPTool):
    def __init__(self, user_identifier: str):
        # Disable rate limiting (not recommended)
        super().__init__(
            user_identifier,
            uses_tokens=True,
            uses_transformer_calls=True,
        )
        # The tool will still be logged, but won't have rate limiting
```

### Authentication

The MCP server supports two authentication methods:

1. **Google OAuth**: Requires `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`
2. **API Key**: Requires creating an API Key in the backend and sending it in the `HTTP-API-KEY` header

### Health Check

The server exposes a health check endpoint at `/mcp/health`:

```bash
curl http://localhost:8001/mcp/health
# {"status": "Running"}
```

## Testing with MCP Inspector

The MCP Inspector provides an interactive UI to test your MCP server tools and payloads. It runs outside Python and connects to your MCP server over HTTP.

### Prerequisites

1. **Install Node.js** (if not already installed) so you have `npx` available.
2. **Start your MCP server** (e.g., via Docker Compose or directly).

### Starting the Inspector

Run the following command to start the Inspector UI:

```bash
npx @modelcontextprotocol/inspector
```

This will open the MCP Inspector in your browser.

### Connecting to Your Server

1. In the Inspector UI, configure the connection:
   - **Transport Type**: Select `Streamable HTTP`
   - **URL**: Enter your MCP server URL (e.g., `http://localhost:8001/mcp`)

2. **Configure Authentication** (choose one method):

   **Option A: API Key (Recommended for local testing)**
   
   - Create an API key in your Django backend (using your API key management system)
   - In the Inspector, expand the **Authentication** section
   - Add a custom header:
     - **Header name**: `HTTP-API-KEY`
     - **Header value**: `<your-api-key>`

   **Option B: OAuth**
   
   - Click on **Open OAuth Settings**
   - Click on **Quick OAuth Flow**
   - Use your Google account to authenticate
   - Make sure your `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` are configured correctly

3. Click **Connect** in the sidebar to establish the connection.

### Using the Inspector

Once connected, you can:

- **View available tools**: See all registered tools in the sidebar
- **Test tools**: Click on a tool to see its parameters and execute it
- **View responses**: See the full response from tool executions
- **Inspect errors**: Debug any issues with tool calls

### Example: Testing a Search Tool

1. Connect to your server using one of the authentication methods above
2. Find the `search` tool in the tools list
3. Click on it to open the tool interface
4. Enter a query parameter (e.g., `"Python Django tutorial"`)
5. Click **Execute** to run the tool
6. View the results in the response panel

## Connecting Other Clients

### Cursor

To use your MCP server with Cursor:

1. Open Cursor settings: Press `Cmd + P` (Mac) or `Ctrl + P` (Windows/Linux) and search for "MCP settings"
2. Click to add a new MCP server
3. Use the following JSON configuration (replace the API key placeholder with your actual API key):

```json
{
  "mcpServers": {
    "my-mcp-server": {
      "type": "https",
      "url": "http://localhost:8001/mcp",
      "headers": {
        "HTTP-API-KEY": "<YOUR_API_KEY_HERE>"
      }
    }
  }
}
```

4. Save the configuration
5. Restart Cursor to apply the changes

Now you can use your MCP server tools directly from Cursor's AI chat interface.

### ChatGPT

To set up a connector in ChatGPT:

1. **Prerequisites**: You must have a ChatGPT Plus account (or a plan that allows connectors)
2. **Enable Developer Mode**:
   - Click your avatar in the bottom-left corner
   - Go to `Settings` → `Apps & Connectors`
   - Scroll down and enable **Developer Mode**
3. **Create a Connector**:
   - Click `Create` to add a new connector
   - Give it a name (e.g., "My MCP Server")
   - Set the URL:
     - For production: `https://your-domain.com/mcp`
     - For local testing: Use a tunnel service like ngrok or provide a localhost URL
4. **Configure OAuth**:
   - Under Authentication, choose **OAuth**
   - Click `Create` to configure OAuth credentials
   - Add your OAuth redirect URIs to Google Console (if using local URLs)
5. **Save and Test**: Save the connector and test the connection

**Note**: If using a local URL, make sure to add it to your Google OAuth Console's allowed origins/redirect URIs for authentication to work properly.

## Module Structure

```
baseapp_mcp/
├── __init__.py
├── apps.py              # Django AppConfig
├── app.py               # Main MCP server
├── exceptions.py        # Custom exceptions
├── utils.py            # Utility functions
├── logs/               # Logging model
│   ├── models.py
│   ├── admin.py
│   └── migrations/
├── rate_limits/         # Rate limiting model
│   ├── models.py
│   ├── manager.py
│   ├── utils.py
│   └── migrations/
├── tools/              # Generic tools
│   ├── base_tool.py
│   ├── base_mcp_tool.py
│   ├── base_search_tool.py
│   ├── base_fetch_tool.py
│   └── compat.py
├── middleware/         # Authentication and rate limiting middleware
├── server/             # Server configuration
└── extensions/         # FastMCP extensions
```

## References

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Baseapp AI Langkit README](../README.md) - For information about integration with agents

## Troubleshooting

### Error: "ModuleNotFoundError: No module named 'baseapp_mcp'"

Make sure:
1. The package is installed: `pip install -e ./baseapp-ai-langkit[mcp]`
2. The app is in `INSTALLED_APPS`
3. The Python path is configured correctly

### Error: "AttributeError: 'Settings' object has no attribute 'MCP_URL'"

Add `MCP_URL` to your `settings/base.py`:
```python
MCP_URL = env("MCP_URL", default="http://localhost:8001")
```

### Server won't start

Check:
1. Migrations have been run
2. Environment variables are configured
3. The gunicorn command is correct in docker-compose.yml

### Tools don't appear on the server

Make sure:
1. Tools are registered with `@mcp.tool` in `apps/mcp/app.py`
2. The server was restarted after adding new tools
3. The application is being imported correctly (`apps.mcp.app:application`)
