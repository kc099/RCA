import asyncio
import os
import threading
import tomllib
import uuid
import webbrowser
import pkg_resources
import sys
import time
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from functools import partial
from json import dumps
from pathlib import Path
from typing import Optional, Dict, List, Any

from fastapi import (
    FastAPI,
    Request,
    Depends,
    HTTPException,
    status,
    Body,
    Response,
    Cookie,
)
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import pytz
import json
import logging
import asyncio
import uuid
import webbrowser
import pkg_resources
import sys

# Configure logging - minimal and clean
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Import MySQL-based authentication
from app.auth.models import UserInDB
from app.auth.jwt import get_current_active_user, get_current_admin_user, get_user_from_token
from app.auth.mysql_repository import setup_db, create_initial_admin
from app.agent.mcp import MCPAgent
from app.auth import router as auth_router


# Define lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create the initial admin user if no users exist
    await setup_db()
    await create_initial_admin()
    yield


# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

# Mount static files with cache busting
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Store cache version in app state for template access
@app.middleware("http")
async def add_cache_version(request: Request, call_next):
    # Generate a unique cache version for each request to ensure no caching
    request.state.cache_version = str(int(time.time()))
    response = await call_next(request)
    return response

# Add CORS headers for EventSource compatibility
@app.middleware("http")
async def add_cors_for_sse(request: Request, call_next):
    # Generate a cache version for each request
    request.state.cache_version = str(int(time.time()))
    
    # Continue processing the request
    response = await call_next(request)
    
    # Add CORS headers for event-stream endpoints
    if "text/event-stream" in response.headers.get("content-type", ""):
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["X-Accel-Buffering"] = "no"  # Important for nginx
    
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include auth router
app.include_router(auth_router.router)


class Task(BaseModel):
    id: str
    prompt: str
    created_at: datetime
    status: str
    steps: list = []

    def model_dump(self, *args, **kwargs):
        data = super().model_dump(*args, **kwargs)
        data["created_at"] = self.created_at.isoformat()
        return data


class TaskManager:
    def __init__(self):
        self.tasks = {}
        self.queues = {}

    def create_task(self, prompt: str) -> Task:
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id, prompt=prompt, created_at=datetime.now(), status="pending"
        )
        self.tasks[task_id] = task
        self.queues[task_id] = asyncio.Queue()
        return task

    async def debug_queue_event(self, task_id, event_type, data):
        """Debug helper to log events being pushed to the queue"""
        logger.info(f"[DEBUG] Queueing {event_type} event for task {task_id}: {data}")
        
        # Create a JSON-serializable version for debugging
        debug_data = {
            "type": "debug",
            "original_type": event_type,
            "message": f"Debug: {event_type} event queued",
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        
        # Queue the debug event
        if task_id in self.queues:
            await self.queues[task_id].put(debug_data)

    async def update_task_step(
        self, task_id: str, step: int, result: str, step_type: str = "step"
    ):
        if task_id in self.tasks:
            task = self.tasks[task_id]

            # First, add the step to the task's step list
            task.steps.append({"step": step, "result": result, "type": step_type})

            # Generate a unique ID for deduplication
            event_id = str(uuid.uuid4())
            
            # Debug log the step update
            logger.info(f"[TaskManager] Updating task {task_id} with {step_type} step #{step}")
            
            # Special handling for tool results
            if step_type == "tool" and isinstance(result, dict):
                logger.info(f"[TaskManager] Found tool result: {result}")
                
                # Send tool step event
                tool_event = {
                    "type": "tool",
                    "step": step,
                    "content": f"Using tool: {result.get('name', 'unknown tool')}",
                    "id": f"tool-{event_id}",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
                
                await self.queues[task_id].put(tool_event)
                await self.debug_queue_event(task_id, "tool", tool_event)
                
                # Send tool result as a separate 'result' event
                result_event = {
                    "type": "result",
                    "step": step,
                    "result": result,
                    "content": str(result.get("output", "")),
                    "visualization_type": result.get("visualization_type", ""),
                    "id": result.get("id", f"result-{event_id}"),
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
                
                await self.queues[task_id].put(result_event)
                await self.debug_queue_event(task_id, "result", result_event)
            else:
                # Handle regular step events
                step_event = {
                    "type": step_type,
                    "step": step,
                    "result": result,
                    "content": result,
                    "id": event_id,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
                
                await self.queues[task_id].put(step_event)
                await self.debug_queue_event(task_id, step_type, step_event)

    async def complete_task(self, task_id: str):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = "completed"

            # Generate a unique ID for the completion event
            event_id = str(uuid.uuid4())

            # Send final status update with the completion state
            await self.queues[task_id].put(
                {"type": "status", "status": task.status, "steps": task.steps, "id": f"status-complete-{event_id}"}
            )

            # Send completion event with the same ID for correlation
            await self.queues[task_id].put(
                {"type": "complete", "id": event_id, "timestamp": datetime.now().strftime("%H:%M:%S")}
            )

    async def fail_task(self, task_id: str, error: str):
        if task_id in self.tasks:
            self.tasks[task_id].status = f"failed: {error}"

            # Generate a unique ID for the error event
            event_id = str(uuid.uuid4())

            # Send error event with an ID for deduplication
            await self.queues[task_id].put(
                {"type": "error", "message": error, "id": event_id, "timestamp": datetime.now().strftime("%H:%M:%S")}
            )


task_manager = TaskManager()


# Create a helper function to check and enhance tool results
def enhance_tool_result(result):
    """Add visualization type for tool results that look like tables or charts"""
    if isinstance(result, dict) and 'output' in result:
        output = result['output']
        
        # First, check if result already has a visualization_type
        if 'visualization_type' in result:
            return result
            
        # Check if output looks like a table (has pipe characters and plus signs)
        if isinstance(output, str) and '|' in output and '+' in output:
            # This looks like a table output from a database query
            result['visualization_type'] = 'table'
            return result
            
        # Check if output looks like chart data from dashboard_viz tool
        if isinstance(output, dict):
            # If output has chart-related keys like 'type', 'x', 'y', etc.
            chart_indicators = ['type', 'title', 'x', 'y', 'xaxis', 'yaxis', 'labels', 'values']
            if any(key in output for key in chart_indicators):
                result['visualization_type'] = 'chart'
                return result
                
        # Check for dashboard data (multiple charts)
        if isinstance(output, dict) and 'charts' in output and isinstance(output['charts'], list):
            result['visualization_type'] = 'dashboard'
            return result
            
    # Check for JSON string results that might be from dashboard_viz tool
    if isinstance(result, str):
        try:
            # Try to parse as JSON
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                # Check for visualization_type in the parsed result
                if 'visualization_type' in parsed:
                    return parsed
                # Check if it has output field with chart data
                if 'output' in parsed:
                    return enhance_tool_result(parsed)  # Recursively check the parsed output
        except json.JSONDecodeError:
            pass
            
    return result


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html", {"request": request, "cache_version": request.state.cache_version}
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html", {"request": request, "cache_version": request.state.cache_version}
    )


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(
        "register.html", {"request": request, "cache_version": request.state.cache_version}
    )


@app.get("/download")
async def download_file(
    file_path: str,
    current_user: UserInDB = Depends(get_current_active_user)
):
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return Response(content=open(file_path, "rb").read(), media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename={os.path.basename(file_path)}"})


# Task creation deduplication tracking
_recent_task_requests = {}
_task_request_lock = asyncio.Lock()
_TASK_DEDUPE_WINDOW_SECONDS = 5  # Dedupe window of 5 seconds

class TaskRequest(BaseModel):
    prompt: str

@app.post("/tasks")
async def create_task(
    request: Request, task_request: TaskRequest, current_user: UserInDB = Depends(get_current_active_user)
):
    prompt = task_request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    # Create a new task
    task = task_manager.create_task(prompt)
    
    # Log task creation
    logger.info(f"Task created: {task.id} by user {current_user.username}")
    
    # Start task processing in background
    asyncio.create_task(process_task(task.id, prompt, current_user))
    
    return {"task_id": task.id}


async def process_task(task_id: str, prompt: str, user: UserInDB):
    """Process a task in the background"""
    try:
        # Update task status to running
        task_manager.tasks[task_id].status = "running"
        
        # Add the initial event
        await task_manager.queues[task_id].put({
            "type": "step",
            "step": 0,
            "content": f"Processing: {prompt}",
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        # Execute the agent here
        # This is a placeholder for your actual agent execution logic
        try:
            from app.agent.mcp import MCPAgent
            from app.logger import logger
            
            # Create MCP agent
            agent = MCPAgent()
            
            # Create a handler for logging events
            class SSELogHandler:
                def __init__(self, task_id):
                    self.task_id = task_id
                    self.handler_id = None
                
                async def __call__(self, message):
                    import re
                    import json
                    
                    # Extract content after timestamp/level indicator
                    cleaned_message = re.sub(r"^.*? - ", "", message)
                    
                    event_type = "log"
                    if "✨ Manus's thoughts:" in cleaned_message or "✨ mcp_agent's thoughts:" in cleaned_message:
                        event_type = "think"
                    elif "🛠️ Manus selected" in cleaned_message or "🛠️ mcp_agent selected" in cleaned_message:
                        event_type = "tool"
                    elif "🎯 Tool" in cleaned_message:
                        event_type = "act"
                        
                        # Process tool results for database queries
                        if "mysql_rw" in cleaned_message and "executed:" in cleaned_message:
                            try:
                                # Extract JSON tool result data
                                output_match = re.search(r'executed:\s*(\{.*\})', cleaned_message)
                                if output_match:
                                    tool_output_str = output_match.group(1).strip()
                                    tool_data = json.loads(tool_output_str)
                                    
                                    # Enhance with visualization type if it looks like a table
                                    enhanced_result = enhance_tool_result(tool_data)
                                    
                                    # Send as a result event for UI display
                                    await task_manager.queues[self.task_id].put({
                                        "type": "result",
                                        "step": 0,
                                        "content": "Database query result:",
                                        "result": enhanced_result,
                                        "visualization_type": enhanced_result.get("visualization_type", "table"),
                                        "id": enhanced_result.get("id", f"result-{uuid.uuid4()}"),
                                        "timestamp": datetime.now().strftime("%H:%M:%S")
                                    })
                            except Exception as e:
                                logger.error(f"Error processing database result: {e}")
                        
                        # Process tool results for dashboard visualizations
                        elif "dashboard_viz" in cleaned_message and "executed:" in cleaned_message:
                            try:
                                # Extract JSON tool result data
                                output_match = re.search(r'executed:\s*(\{.*\})', cleaned_message)
                                if output_match:
                                    tool_output_str = output_match.group(1).strip()
                                    tool_data = json.loads(tool_output_str)
                                    
                                    # Enhance with visualization type
                                    enhanced_result = enhance_tool_result(tool_data)
                                    
                                    # Determine visualization type from the result
                                    viz_type = "chart"  # Default to chart
                                    if "visualization_type" in enhanced_result:
                                        viz_type = enhanced_result["visualization_type"]
                                    elif isinstance(enhanced_result.get("output"), dict):
                                        output_obj = enhanced_result["output"]
                                        if "charts" in output_obj:
                                            viz_type = "dashboard"
                                    
                                    # Send as a result event for UI display
                                    await task_manager.queues[self.task_id].put({
                                        "type": "result",
                                        "step": 0,
                                        "content": "Data visualization:",
                                        "result": enhanced_result,
                                        "visualization_type": viz_type,
                                        "id": enhanced_result.get("id", f"viz-{uuid.uuid4()}"),
                                        "timestamp": datetime.now().strftime("%H:%M:%S")
                                    })
                                    
                                    logger.info(f"Sent visualization event of type {viz_type} to client")
                            except Exception as e:
                                logger.error(f"Error processing dashboard visualization result: {e}")
                    elif "📝 Oops!" in cleaned_message:
                        event_type = "error"
                    elif "🏁 Special tool" in cleaned_message:
                        event_type = "complete"
                    
                    await task_manager.update_task_step(self.task_id, 0, cleaned_message, event_type)
            
            # Create function to add and remove handlers
            def add_sse_handler(handler):
                handler_id = logger.add(handler)
                handler.handler_id = handler_id
                return handler_id
            
            def remove_sse_handler(handler):
                if handler and hasattr(handler, 'handler_id') and handler.handler_id is not None:
                    try:
                        logger.remove(handler.handler_id)
                        return True
                    except Exception as e:
                        logger.error(f"Error removing log handler: {e}")
                return False
            
            # Add the handler for this task
            sse_handler = SSELogHandler(task_id)
            add_sse_handler(sse_handler)
            
            # Initialize with connection details first
            await agent.initialize(
                connection_type="stdio",
                command=sys.executable,
                args=["-m", "app.mcp.server"],
            )
            
            # Then run with the prompt
            try:
                agent_result = await agent.run(prompt)
                await task_manager.complete_task(task_id)
            finally:
                # Make sure to remove the handler
                remove_sse_handler(sse_handler)
            
        except Exception as e:
            logger.error(f"Error executing agent for task {task_id}: {str(e)}")
            await task_manager.fail_task(task_id, str(e))
            
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}")
        await task_manager.fail_task(task_id, str(e))


# Track events by task ID to prevent duplicates
_task_events = {}

async def task_event_generator(task_id):
    """
    Generate SSE events for a specific task, with improved formatting for EventSource compatibility.
    """
    logger.info(f"[SSE] Starting event generator for task {task_id}")
    
    if task_id not in task_manager.queues:
        logger.error(f"[SSE] Task {task_id} not found in queue system")
        yield f"data: {dumps({'message': 'Task not found'})}\n\n"
        return

    queue = task_manager.queues[task_id]
    task = task_manager.tasks.get(task_id)
    
    # Send initial status
    if task:
        initial_data = dumps({
            'id': f'init-{task_id}',
            'type': 'status',
            'status': task.status,
            'steps': task.steps
        })
        logger.info(f"[SSE] Sending initial status for task {task_id}")
        yield f"event: status\ndata: {initial_data}\n\n"
        
        # If already complete, send completion event
        if task.status == "completed":
            complete_data = dumps({
                'id': f'complete-{task_id}',
                'message': 'Task completed'
            })
            yield f"event: complete\ndata: {complete_data}\n\n"
            return

    try:
        # Process events from the task queue
        while True:
            try:
                # Wait for an event from the queue with timeout
                event = await asyncio.wait_for(queue.get(), timeout=300)  # 5 minutes timeout
                
                # Log the event for debugging
                logger.info(f"[SSE] Processing event for task {task_id}: {event.get('type', 'unknown')}")
                
                # Extract event type and ensure proper formatting
                event_type = event.get('type', 'message')
                
                # Format for EventSource
                formatted_data = dumps(event)
                sse_message = f"event: {event_type}\ndata: {formatted_data}\n\n"
                logger.info(f"[SSE] Sending event: {event_type} for task {task_id}")
                yield sse_message
                
                # If this is a completion event, stop streaming
                if event_type == 'complete' or event_type == 'error':
                    logger.info(f"[SSE] Ending stream after {event_type} event for task {task_id}")
                    break
                    
            except asyncio.TimeoutError:
                # Send keepalive after timeout
                logger.debug(f"[SSE] Sending keepalive for task {task_id}")
                yield f":keepalive\n\n"
                
    except asyncio.CancelledError:
        # Handle cancellation
        logger.warning(f"[SSE] Stream cancelled for task {task_id}")
        yield f"event: error\ndata: {dumps({'message': 'Stream cancelled'})}\n\n"
        
    except Exception as e:
        # Send error event on exceptions
        logger.error(f"[SSE] Error in event stream for task {task_id}: {str(e)}")
        error_data = dumps({
            'message': f'Error in event stream: {str(e)}',
            'id': f'error-{task_id}'
        })
        yield f"event: error\ndata: {error_data}\n\n"


@app.get("/tasks/{task_id}/events")
async def task_events(
    task_id: str,
    request: Request,
    token: Optional[str] = None,
    current_user: Optional[UserInDB] = None
):
    """
    Stream events for a specific task to the client via SSE with deduplication.
    """
    # Configure SSE logger to be quiet (only critical errors)
    sse_logger = logging.getLogger("sse_debug")
    sse_logger.setLevel(logging.CRITICAL)  # Only log critical errors
    formatter = logging.Formatter('%(levelname)s: %(message)s')

    # Add a handler if not already present
    if not sse_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        sse_logger.addHandler(handler)

    sse_logger.debug(f"SSE connection request for task {task_id}")

    # Allow authentication via URL token parameter (for EventSource connections)
    if token and not current_user:
        try:
            user = await get_user_from_token(token)
            if user:
                current_user = user
                sse_logger.debug(f"SSE authenticated user {user.username} via token parameter")
                logger.info(f"[SSE] Authenticated user {user.username} via token parameter")
            else:
                sse_logger.debug(f"SSE invalid token provided in URL parameter")
                logger.error(f"[SSE] Invalid token provided in URL parameter")
                return StreamingResponse(
                    iter([f"event: error\ndata: {dumps({'message': 'Invalid or expired token'})}\n\n"]),
                    media_type="text/event-stream",
                )
        except Exception as e:
            sse_logger.debug(f"SSE token authentication error: {str(e)}")
            logger.error(f"[SSE] Token authentication error: {str(e)}")
            return StreamingResponse(
                iter([f"event: error\ndata: {dumps({'message': 'Authentication failed'})}\n\n"]),
                media_type="text/event-stream",
            )

    # If no user is authenticated by any method, return error
    if not current_user:
        sse_logger.debug(f"SSE authentication required for task {task_id}")
        return StreamingResponse(
            iter([f"event: error\ndata: {dumps({'message': 'Authentication required'})}\n\n"]),
            media_type="text/event-stream",
        )

    # Initialize task event tracking if not already present
    if task_id not in _task_events:
        _task_events[task_id] = {
            "event_ids": set(),
            "step_numbers": set(),
            "event_counter": {
                "connected": 0,
                "status": 0,
                "step": 0,
                "think": 0,
                "tool": 0,
                "result": 0,
                "complete": 0,
                "error": 0
            }
        }

    task_tracking = _task_events[task_id]

    async def event_generator():
        async for event in task_event_generator(task_id):
            yield event

    sse_logger.debug(f"SSE starting event generator for task {task_id}")
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/tasks")
async def get_tasks(
    current_user: UserInDB = Depends(get_current_active_user)
):
    sorted_tasks = sorted(
        task_manager.tasks.values(), key=lambda task: task.created_at, reverse=True
    )
    return JSONResponse(
        content=[task.model_dump() for task in sorted_tasks],
        headers={"Content-Type": "application/json"},
    )


@app.get("/tasks/active")
async def get_active_task(current_user: UserInDB = Depends(get_current_active_user)):
    """Get the latest active task for the user"""
    # Find the most recent task
    active_tasks = [
        task for task in task_manager.tasks.values()
        if task.status != "completed" and task.status != "failed"
    ]
    
    if not active_tasks:
        return {"status": "no_active_task"}
    
    # Sort by creation time, newest first
    active_tasks.sort(key=lambda t: t.created_at, reverse=True)
    latest_task = active_tasks[0]
    
    return {
        "id": latest_task.id,
        "prompt": latest_task.prompt,
        "status": latest_task.status,
        "created_at": latest_task.created_at.isoformat()
    }


@app.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
):
    if task_id not in task_manager.tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_manager.tasks[task_id]


@app.get("/api/config/status")
async def check_config_status(
    current_user: UserInDB = Depends(get_current_admin_user)
):
    config_path = Path(__file__).parent / "config" / "config.toml"
    example_config_path = Path(__file__).parent / "config" / "config.example.toml"

    # Get server config from environment variables
    server_host = os.environ.get("SERVER_HOST", "localhost")
    server_port = int(os.environ.get("SERVER_PORT", 5172))

    # Prepare server config dict
    server_config = {
        "host": server_host,
        "port": server_port
    }

    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                current_config = tomllib.load(f)

            # Add server config if missing
            if "server" not in current_config:
                current_config["server"] = server_config

            return {"status": "exists", "config": current_config, "configRequired": False}
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            return {"status": "error", "message": str(e), "configRequired": True}
    elif example_config_path.exists():
        try:
            with open(example_config_path, "rb") as f:
                example_config = tomllib.load(f)

            # Add server config to example
            if "server" not in example_config:
                example_config["server"] = server_config

            return {"status": "missing", "example_config": example_config, "config": example_config, "configRequired": True}
        except Exception as e:
            logger.error(f"Error loading example config: {str(e)}")
            return {"status": "error", "message": str(e), "configRequired": True}
    else:
        # Create a minimal config with server info
        minimal_config = {"server": server_config}
        return {"status": "no_example", "config": minimal_config, "configRequired": True}


@app.post("/api/config/save")
async def save_config(
    config_data: dict = Body(...),
    current_user: UserInDB = Depends(get_current_admin_user)
):
    try:
        config_dir = Path(__file__).parent / "config"
        config_dir.mkdir(exist_ok=True)

        config_path = config_dir / "config.toml"

        toml_content = ""

        if "llm" in config_data:
            toml_content += "# Global LLM configuration\n[llm]\n"
            llm_config = config_data["llm"]
            for key, value in llm_config.items():
                if key != "vision":
                    if isinstance(value, str):
                        toml_content += f'{key} = "{value}"\n'
                    else:
                        toml_content += f"{key} = {value}\n"

        if "server" in config_data:
            toml_content += "\n# Server configuration\n[server]\n"
            server_config = config_data["server"]
            for key, value in server_config.items():
                if isinstance(value, str):
                    toml_content += f'{key} = "{value}"\n'
                else:
                    toml_content += f"{key} = {value}\n"

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(toml_content)

        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/auth/log")
async def auth_log_endpoint(request: Request):
    try:
        body = await request.json()
        message = body.get("message", "No message")
        details = body.get("details", {})

        logger.info(f"[AUTH LOG] {message}")
        if details:
            logger.info(f"[AUTH LOG] Details: {details}")
        return {"status": "logged"}
    except Exception as e:
        logger.error(f"[AUTH LOG ERROR] {str(e)}")
        return {"status": "error", "message": str(e)}


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500, content={"message": f"Server error: {str(exc)}"}
    )


def open_local_browser(config):
    webbrowser.open_new_tab(f"http://{config['host']}:{config['port']}")


def load_config():
    try:
        config_path = Path(__file__).parent / "config" / "config.toml"
        
        # Get server config from environment variables as a fallback
        server_host = os.environ.get("SERVER_HOST", "localhost")
        server_port = int(os.environ.get("SERVER_PORT", 5172))
        
        # Default config
        default_config = {"host": server_host, "port": server_port}

        if not config_path.exists():
            logger.info("Config file not found, using default configuration")
            return default_config

        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        
        # Check if the server section exists in the config
        if "server" not in config:
            logger.warning("Server configuration missing in config file, using environment variables")
            return default_config
            
        # Get server host and port from config file
        try:
            host = config["server"]["host"]
            port = config["server"]["port"]
            return {"host": host, "port": port}
        except KeyError as e:
            # Missing fields within server section
            logger.warning(f"Missing field in server configuration: {str(e)}, using defaults")
            return default_config
            
    except FileNotFoundError:
        logger.info("Config file not found, using default configuration")
        return {"host": "localhost", "port": 5172}
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}, using default configuration")
        return {"host": "localhost", "port": 5172}


if __name__ == "__main__":
    import uvicorn

    config = load_config()
    open_with_config = partial(open_local_browser, config)
    threading.Timer(3, open_with_config).start()
    uvicorn.run(app, host=config["host"], port=config["port"])
