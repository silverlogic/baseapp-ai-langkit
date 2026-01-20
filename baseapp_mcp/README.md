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
import logging

import django

from baseapp_mcp import (
    DjangoFastMCP,
    get_application,
    register_debug_tool,
    register_health_check_route,
)

logger = logging.getLogger(__name__)

if not django.apps.apps.ready:
    django.setup(set_prefix=False)

# Create your MCP server instance
server_instructions = """
Your custom server instructions here.
"""

mcp = DjangoFastMCP.create(instructions=server_instructions)

def register_tools():
    logger.info("Registering MCP tools and routes...")

    register_debug_tool(mcp)
    register_health_check_route(mcp)

    # Register project-specific tools 
    # Any imports relying on django setup need to come below django.setup(...), so cannot be at the top
    from somewhere import YourTool, AnotherTool
    mcp.register_tool(YourTool)
    mcp.register_tool(AnotherTool)

register_tools()

# Export the application for use with gunicorn/uvicorn
application = get_application(mcp)
```

## Creating Tools

### Example 1: Basic Tool Extending MCPTool

To create a tool from scratch, extend `MCPTool`:

```python
import logging
from typing import Annotated, Any, Dict

from baseapp_mcp.tools import MCPTool
from baseapp_mcp import exceptions

logger = logging.getLogger(__name__)


class MyTool(MCPTool):
    """
    Custom tool that performs a specific operation.
    """
    name: str = "my_tool"
    description: str = "My custom tool that does something specific"

    def tool_func_core(
        self, 
        query: Annotated[str, "The search query"],
        limit: Annotated[int, "Result limit"] = 10
    ) -> Dict[str, Any]:
        """
        Main tool implementation.
        Name ("my_tool") and description ("My custom tool ...") are defined above
        The args schema is extracted from the annotations and automatically appended to the description.
        """
        if not query or not query.strip():
            raise exceptions.MCPValidationError("Query cannot be empty")

        # Your logic here
        results = perform_search(query, limit)

        doc = {
            "results": results,
            "count": len(results),
        }

        return doc
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
    name = "search"
    description = "Searches for XYZ objects in the database."

    def tool_func_core(
        self, title: Annotated[str, "The title to search for"]
    ) -> dict[str, Any]:
        # This just renames the parameter from query to title and changes the annotation
        return super().tool_func_core(title)

    def search(self, title: str) -> list[Dict[str, Any]]:
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
    name: str = "fetch"
    description: str = "Fetch documents of type XYZ by url."

    def tool_func_core(
        self, url: Annotated[str, "URL of the document to fetch."]
    ) -> dict[str, Any]:
        # This just renames the parameter from search_term to url and changes the annotation
        return super().tool_func_core(url)

    def fetch(self, url: str) -> MyDocument:
        """
        Fetch a document by URL.

        Args:
            url: Document URL
        Returns:
            MyDocument instance
        """
        try:
            return MyDocument.objects.get(url=url)
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

### Example 4: Simple Tool Without Token Limiting

By default, token limiting is disabled for MCP tools, so you do not need to do anything specific:

```python
from baseapp_mcp.tools import MCPTool

class SimpleTool(MCPTool):
    name = "simple_tool"
    description = "A simple tool"
    
    def tool_func_core(self, text: Annotated[str, "Text to capitalize"]) -> Dict[str, Any]:
        return {"result": text.upper()}
```

### Example 5: Simple Tool With Token Limiting

For tools that need token limiting:

```python
from baseapp_mcp.tools import MCPTool

class SimpleTool(MCPTool):
    name = "simple_tool"
    description = "A simple tool"
    
    uses_tokens = True # Enables token tracking
    uses_transformer_calls = True # Enables transformer call tracking
    
    def tool_func_core(self) -> Dict[str, Any]:
        # If you do an operation using a transformer call, call
        # add_transformer_calls to track it
        something_using_a_transformer()
        self.add_transformer_calls()

        # If you invoke an LLM using Langchain, call add_token_usage
        # with its response to track the tokens used
        response = llm.invoke(prompt)
        self.add_token_usage(response)
        
        return {"result": "succeeded"}
```
This will automatically keep track of the tokens consumed by each user. If token limits are enabled in the settings, the tool will throw a `RateLimitException` when exceeded.

## Registering Tools on the Server

After creating your MCP server instance, register tools using `mcp.register_tool`:

```python
# apps/mcp/app.py
from baseapp_mcp import DjangoFastMCP
from apps.mcp.tools.my_tool import MyTool

# Create your MCP server instance
mcp = DjangoFastMCP.create()

# Register your tool
mcp.register_tool(MyTool)
```

If you create tools from scratch (not deriving `MCPTool`), you can use the `@mcp.tool()` decorator to register them. The `register_tool` method from above will ensure that name, description, and argument schema are correctly copied from your `MCPTool` class.

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

### Limits

You can enforce rate and token limits. Here, rate limits bound the number of times users can call tools in certain periods, while token limits bound the number of tokens that users can spend calling tools.

#### Rate Limiting

There are two kinds of rate limits you can enforce: any interactions with the server by a user (including all requests, configured as a middleware) and number of tool calls. For the first, define the limits as follows: 
```python
# settings/base.py
MCP_ENABLE_GENERAL_RATE_LIMITING = True
MCP_GENERAL_RATE_LIMIT_PERIOD = 60  # seconds
MCP_GENERAL_RATE_LIMIT_CALLS = 500  # max calls per period
```
This will limit any requests that a user can make to the server to the specified number.

To limit the number of tool calls only, you can use these settings (applying to all tools):
```python
# settings/base.py
MCP_ENABLE_TOOL_RATE_LIMITING = True
MCP_TOOL_RATE_LIMIT_PERIOD = 60  # seconds
MCP_TOOL_RATE_LIMIT_CALLS = 30  # max calls per period
```
Any tool calls count towards this limit. If you need further customization on a per tool basis, you can exempt a single tool from the global rate limits
```python
from baseapp_mcp.tools import MCPTool

class MyTool(MCPTool):
    ...
    # Allow calling this tool even if the tool rate limit is exceeded
    def is_rate_limit_enabled(self) -> bool:
        return False
```
or change the rate limiter on a per tool basis:
```python
from baseapp_mcp.rate_limits.utils import RateLimiter
from baseapp_mcp.tools import MCPTool

class MyRateLimiter(RateLimiter):
    pass

_my_rate_limiter = MyRateLimiter()

class MyTool(MCPTool):
    ...
    # Use a custom rate limiter for this tool
    def get_rate_limiter(self) -> RateLimiter:
        return _my_rate_limiter
```

#### Token Limits

There are different steps for limiting the amount of tokens that are available to users when calling tools.
1. To enable token tracking, set `uses_tokens = True` or `uses_transformer_calls = True` on your tool class. This configuration just indicates that the tool is using tokens/transformer calls, so that
   - token/transformer usage is tracked and logged in the Django admin (without these settings, token usage is omitted from some logs)
   - the tool might be disabled if limits are enforced (without these settings, it is assumed that the tool does not need tokens/transformer calls, so keeps working even if any token/transformer limits are exceeded)
2. To enable token/transformer limits globally for all tools (so that tools using tokens/transformers stop working when these limits are exceeded and tools not using tokens/transformers keep functioning), define
```python
# settings/base.py
MCP_ENABLE_MONTHLY_LIMITS = True
MCP_MONTHLY_TOKEN_LIMIT = 1000000
MCP_MONTHLY_TRANSFORMER_CALL_LIMIT = 1000000
```
3. You can override this setting on a per tool bases by `is_monthly_limit_enabled`
```python
from baseapp_mcp.tools import MCPTool

class MyTool(MCPTool):
    ...
    # Override global MCP_ENABLE_MONTHLY_LIMITS per tool
    def is_monthly_limit_enabled(self):
        return True
```
Different limits for different tools (e.g. 1,000 tokens for tool A and 1,000,000 tokens for tool B) are currently not supported out of the box. For this, we recommend customizing the token tracking on the tools to save `token_a` and `token_b` and enforce different limits for those.

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

### Copilot in VSCode

To use your MCP server with Copilot in VSCode (assuming VSCode is installed and Copilot is already enabled):
1. Create a folder `.vscode` if it does not exist yet.
2. In that folder, create an `mcp.json` file with the same content as in Step 3 of the Cursor setup.
3. Save the file. VSCode will automatically show options to Stop or Restart the MCP server within this file. Make sure the server is running.

Now you can use your MCP server tools directly from Copilots chat interface.

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
