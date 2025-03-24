# Adapting OpenManus for HTTP Transport in EKS

This guide explains how to modify OpenManus to use HTTP transport instead of stdio when deployed on AWS EKS.

## 1. Create an HTTP Server for MCP

First, let's create a new file to implement an HTTP server for the MCP protocol:

```python
# app/mcp/http_server.py

import asyncio
import json
import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.logger import logger
from app.mcp.server import MCPServer

app = FastAPI(title="OpenManus MCP Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global server instance
mcp_server: Optional[MCPServer] = None

class ToolRequest(BaseModel):
    tool: str
    params: Dict[str, Any]

@app.on_event("startup")
async def startup_event():
    global mcp_server
    logger.info("Initializing MCP Server for HTTP transport")
    mcp_server = MCPServer()
    await mcp_server.register_all_tools()
    logger.info("MCP Server initialized for HTTP transport")

@app.on_event("shutdown")
async def shutdown_event():
    global mcp_server
    if mcp_server:
        logger.info("Cleaning up MCP Server resources")
        await mcp_server.cleanup_resources()
        logger.info("MCP Server resources cleaned up")

@app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes probes."""
    return {"status": "healthy"}

@app.get("/tools")
async def list_tools():
    """List all available tools and resources."""
    if not mcp_server:
        raise HTTPException(status_code=503, detail="Server not initialized")
    
    tools = list(mcp_server.tools.keys())
    resources = list(mcp_server.resources.keys())
    
    return {
        "tools": tools,
        "resources": resources
    }

@app.post("/execute")
async def execute_tool(request: ToolRequest):
    """Execute a tool or access a resource."""
    if not mcp_server:
        raise HTTPException(status_code=503, detail="Server not initialized")
    
    tool_name = request.tool
    params = request.params
    
    # Check if tool exists
    if tool_name in mcp_server.tools:
        logger.info(f"Executing tool: {tool_name} with params: {params}")
        try:
            result = await mcp_server.tools[tool_name].execute(**params)
            return {"result": result}
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error executing tool: {str(e)}")
    
    # Check if resource exists
    elif tool_name in mcp_server.resources:
        logger.info(f"Accessing resource: {tool_name} with params: {params}")
        try:
            result = await mcp_server.resources[tool_name].access(**params)
            return {"result": result}
        except Exception as e:
            logger.error(f"Error accessing resource {tool_name}: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error accessing resource: {str(e)}")
    
    else:
        raise HTTPException(status_code=404, detail=f"Tool or resource not found: {tool_name}")

# WebSocket connection for streaming results
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            request = json.loads(data)
            
            tool_name = request.get("tool")
            params = request.get("params", {})
            
            if not tool_name:
                await websocket.send_json({"error": "Tool name is required"})
                continue
            
            # Execute tool or access resource
            try:
                if tool_name in mcp_server.tools:
                    result = await mcp_server.tools[tool_name].execute(**params)
                    await websocket.send_json({"result": result})
                elif tool_name in mcp_server.resources:
                    result = await mcp_server.resources[tool_name].access(**params)
                    await websocket.send_json({"result": result})
                else:
                    await websocket.send_json({"error": f"Tool or resource not found: {tool_name}"})
            except Exception as e:
                await websocket.send_json({"error": str(e)})
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
```

## 2. Create a Run Script for HTTP Server

```python
# run_http_server.py

import uvicorn
import argparse
from app.logger import logger

def parse_args():
    parser = argparse.ArgumentParser(description="Run OpenManus MCP HTTP Server")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)",
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    logger.info(f"Starting OpenManus HTTP server on {args.host}:{args.port}")
    uvicorn.run(
        "app.mcp.http_server:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info",
    )
```

## 3. Update Dockerfile for HTTP Transport

```dockerfile
FROM python:3.12-slim

WORKDIR /app/OpenManus

RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/* \
    && (command -v uv >/dev/null 2>&1 || pip install --no-cache-dir uv)

COPY . .

RUN uv pip install --system -r requirements.txt

# Expose port for HTTP server
EXPOSE 8000

# Run HTTP server instead of stdio
CMD ["python", "run_http_server.py"]
```

## 4. Update Requirements.txt

Add FastAPI and Uvicorn to your requirements:

```
# Add to requirements.txt
fastapi>=0.95.0
uvicorn>=0.21.0
websockets>=11.0.0
```

## 5. Update MCPAgent to Support HTTP Transport

Modify the MCPAgent class to support HTTP transport:

```python
# app/agent/mcp.py (partial update)

import aiohttp
import json
from typing import Dict, Any, Optional, List

class MCPAgent:
    # ... existing code ...
    
    async def initialize(
        self,
        connection_type: str,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        server_url: Optional[str] = None,
    ) -> None:
        """Initialize the MCP agent with the appropriate connection."""
        self.connection_type = connection_type
        
        if connection_type == "stdio":
            # ... existing stdio initialization ...
        elif connection_type == "http":
            if not server_url:
                raise ValueError("server_url is required for HTTP connection")
            self.server_url = server_url
            # Create HTTP session
            self.http_session = aiohttp.ClientSession()
            # Get available tools
            await self._refresh_tools_http()
        else:
            raise ValueError(f"Unsupported connection type: {connection_type}")
    
    async def _refresh_tools_http(self) -> None:
        """Refresh the list of available tools via HTTP."""
        try:
            async with self.http_session.get(f"{self.server_url}/tools") as response:
                if response.status == 200:
                    data = await response.json()
                    tools = data.get("tools", [])
                    resources = data.get("resources", [])
                    
                    # Combine tools and resources for the agent
                    all_tools = tools + resources
                    
                    self.tools = all_tools
                    logger.info(f"Added MCP tools: {self.tools}")
                else:
                    logger.error(f"Failed to get tools: {response.status}")
        except Exception as e:
            logger.error(f"Error refreshing tools: {str(e)}")
    
    async def run(self, prompt: str) -> str:
        """Run the agent with a prompt."""
        # ... existing code ...
        
        # Execute the tool
        if self.connection_type == "stdio":
            # ... existing stdio execution ...
        elif self.connection_type == "http":
            return await self._execute_tool_http(tool_name, parameters)
    
    async def _execute_tool_http(self, tool_name: str, parameters: Dict[str, Any]) -> str:
        """Execute a tool via HTTP."""
        try:
            payload = {
                "tool": tool_name,
                "params": parameters
            }
            
            async with self.http_session.post(
                f"{self.server_url}/execute", 
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("result", "")
                else:
                    error_text = await response.text()
                    logger.error(f"Error executing tool: {error_text}")
                    return f"Error executing tool: {error_text}"
        except Exception as e:
            logger.error(f"Error executing tool: {str(e)}")
            return f"Error executing tool: {str(e)}"
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.connection_type == "http" and hasattr(self, "http_session"):
            await self.http_session.close()
```

## 6. Update run_mcp.py to Support HTTP Transport

```python
# run_mcp.py (partial update)

async def initialize(
    self,
    connection_type: str,
    server_url: str | None = None,
) -> None:
    """Initialize the MCP agent with the appropriate connection."""
    logger.info(f"Initializing MCPAgent with {connection_type} connection...")

    if connection_type == "stdio":
        await self.agent.initialize(
            connection_type="stdio",
            command=sys.executable,
            args=["-m", self.server_reference],
        )
    elif connection_type == "http":
        if not server_url:
            server_url = "http://localhost:8000"  # Default local URL
        await self.agent.initialize(
            connection_type="http",
            server_url=server_url,
        )
    else:
        raise ValueError(f"Unsupported connection type: {connection_type}")

    logger.info(f"Connected to MCP server via {connection_type}")
```

## 7. Update Kubernetes Deployment

```yaml
# deploy/eks/deployment.yaml (partial)
containers:
- name: openmanus
  image: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/openmanus:latest
  ports:
  - containerPort: 8000
  # ... existing configuration ...
```

## 8. Testing HTTP Transport Locally

To test the HTTP transport locally before deploying to EKS:

```bash
# Terminal 1: Run the HTTP server
python run_http_server.py

# Terminal 2: Run the MCP agent with HTTP transport
python run_mcp.py --transport http --server-url http://localhost:8000
```

## 9. Benefits of HTTP Transport in EKS

Using HTTP transport in EKS provides several advantages:

1. **Scalability**: HTTP servers can be scaled horizontally
2. **Resilience**: Kubernetes can automatically restart failed pods
3. **Load Balancing**: Traffic can be distributed across multiple instances
4. **Monitoring**: HTTP endpoints are easier to monitor with standard tools
5. **Integration**: Easier to integrate with other services and APIs

## 10. Security Considerations

When using HTTP transport in production:

1. **Use HTTPS**: Configure TLS for all communications
2. **API Authentication**: Add authentication to protect your API
3. **Rate Limiting**: Implement rate limiting to prevent abuse
4. **Input Validation**: Validate all inputs to prevent injection attacks
5. **Logging**: Implement comprehensive logging for security monitoring
