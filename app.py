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

# Create a cache version without relying on app.state
cache_version = str(int(time.time()))
logger.info(f"Initializing app with cache version: {cache_version}")

# Mount static files with cache busting
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Store cache version in app state for template access
@app.middleware("http")
async def add_cache_version(request: Request, call_next):
    request.state.cache_version = cache_version
    response = await call_next(request)
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

    async def update_task_step(
        self, task_id: str, step: int, result: str, step_type: str = "step"
    ):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            
            # First, add the step to the task's step list
            task.steps.append({"step": step, "result": result, "type": step_type})
            
            # Generate a unique ID for deduplication
            event_id = str(uuid.uuid4())
            
            # Only send the primary event, not the duplicate status update
            # Include the unique ID to help with frontend deduplication
            await self.queues[task_id].put(
                {
                    "type": step_type, 
                    "step": step, 
                    "result": result,
                    "content": result, 
                    "id": event_id, 
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
            )
            
            # DO NOT send the redundant status update - that's what's causing duplicates
            # REMOVED: await self.queues[task_id].put(
            #    {"type": "status", "status": task.status, "steps": task.steps}
            # )

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

@app.post("/tasks")
async def create_task(
    prompt: str = Body(..., embed=True),
    current_user: UserInDB = Depends(get_current_active_user),
    request: Request = None
):
    # Get a unique identifier for the request - either from headers or generate one
    request_id = request.headers.get("X-Request-ID") if request else None
    if not request_id:
        request_id = str(uuid.uuid4())
    
    # Get user identifier for per-user deduplication
    user_id = current_user.id if current_user else "anonymous"
    
    # Create a composite key for request deduplication
    dedup_key = f"{user_id}:{prompt}"
    current_time = time.time()
    
    # Use a lock to prevent race conditions in deduplication check
    async with _task_request_lock:
        # Check if this is a duplicate request
        if dedup_key in _recent_task_requests:
            last_request_time, task_id = _recent_task_requests[dedup_key]
            
            # If within dedupe window, return the existing task ID
            if current_time - last_request_time < _TASK_DEDUPE_WINDOW_SECONDS:
                logger.info(f"Duplicate task request detected. Returning existing task ID: {task_id}")
                return {"task_id": task_id, "deduped": True}
        
        # Not a duplicate or outside window, create new task
        task = task_manager.create_task(prompt)
        
        # Store this request for future deduplication
        _recent_task_requests[dedup_key] = (current_time, task.id)
        
        # Clean up old entries
        cleanup_keys = []
        for key, (timestamp, _) in _recent_task_requests.items():
            if current_time - timestamp > _TASK_DEDUPE_WINDOW_SECONDS:
                cleanup_keys.append(key)
                
        for key in cleanup_keys:
            _recent_task_requests.pop(key, None)
    
    # Start the task processing
    asyncio.create_task(run_task(task.id, prompt))
    return {"task_id": task.id}


async def run_task(task_id: str, prompt: str):
    try:
        task_manager.tasks[task_id].status = "running"

        server_reference = "app.mcp.server"
        agent = MCPAgent()
        await agent.initialize(
                connection_type="stdio",
                command=sys.executable,
                args=["-m", server_reference],
            )

        async def on_think(thought):
            await task_manager.update_task_step(task_id, 0, thought, "think")

        async def on_tool_execute(tool, input):
            await task_manager.update_task_step(
                task_id, 0, f"Executing tool: {tool}\nInput: {input}", "tool"
            )

        async def on_action(action):
            await task_manager.update_task_step(
                task_id, 0, f"Executing action: {action}", "act"
            )

        async def on_run(step, result):
            await task_manager.update_task_step(task_id, step, result, "run")

        from app.logger import logger

        class SSELogHandler:
            def __init__(self, task_id):
                self.task_id = task_id
                # Store the handler ID when added to logger
                self.handler_id = None

            async def __call__(self, message):
                import re

                # Extract - Subsequent Content
                cleaned_message = re.sub(r"^.*? - ", "", message)

                event_type = "log"
                if "✨ Manus's thoughts:" in cleaned_message or "✨ mcp_agent's thoughts:" in cleaned_message:
                    event_type = "think"
                elif "🛠️ Manus selected" in cleaned_message or "🛠️ mcp_agent selected" in cleaned_message:
                    event_type = "tool"
                elif "🎯 Tool" in cleaned_message:
                    event_type = "act"
                    
                    # Process tool results for visualization data
                    if "Observed output of cmd" in cleaned_message and "executed:" in cleaned_message:
                        try:
                            # Extract JSON tool result data
                            output_match = re.search(r'executed:\s*(\{.*\})', cleaned_message)
                            if output_match:
                                tool_output = output_match.group(1).strip()
                                # Ensure the output includes visualization metadata
                                if "visualization_type" not in tool_output and '"output"' in tool_output:
                                    # Try to enhance with visualization type if possible
                                    if '|' in tool_output and '+--' in tool_output:
                                        import json
                                        tool_data = json.loads(tool_output)
                                        # Add visualization type for tables
                                        tool_data["visualization_type"] = "table"
                                        # Replace the original JSON with enhanced version
                                        cleaned_message = cleaned_message.replace(tool_output, json.dumps(tool_data))
                        except Exception as e:
                            logger.error(f"Error processing tool output: {e}")
                elif "📝 Oops!" in cleaned_message:
                    event_type = "error"
                elif "🏁 Special tool" in cleaned_message:
                    event_type = "complete"

                await task_manager.update_task_step(
                    self.task_id, 0, cleaned_message, event_type
                )

        # Create a function to add and properly track the handler
        def add_sse_handler(handler):
            # Get a proper handler ID as an integer
            handler_id = logger.add(handler)
            # Store the ID in the handler for later removal
            handler.handler_id = handler_id
            return handler_id

        # Create a function to safely remove the handler
        def remove_sse_handler(handler):
            if handler and hasattr(handler, 'handler_id') and handler.handler_id is not None:
                try:
                    logger.remove(handler.handler_id)
                    return True
                except Exception as e:
                    logger.error(f"Error removing log handler: {e}")
            return False

        # Create handler and properly add it to logger
        sse_handler = SSELogHandler(task_id)
        add_sse_handler(sse_handler)

        try:
            result = await agent.run(prompt)
            # Add a minimal result without duplicate status updates
            await task_manager.update_task_step(task_id, 1, result, "result")
            await task_manager.complete_task(task_id)
        except Exception as e:
            await task_manager.fail_task(task_id, str(e))
        finally:
            # Make sure to remove the logger handler properly
            remove_sse_handler(sse_handler)
    except Exception as e:
        await task_manager.fail_task(task_id, str(e))


# Track events by task ID to prevent duplicates
_task_events = {}

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
        if task_id not in task_manager.queues:
            sse_logger.debug(f"SSE task {task_id} not found")
            yield f"event: error\ndata: {dumps({'message': 'Task not found'})}\n\n"
            return
        
        queue = task_manager.queues[task_id]
        
        task = task_manager.tasks.get(task_id)
        task_status = "running"
        if task:
            task_status = task.status
            status_id = f"initial-status-{task_id}"
            sse_logger.debug(f"SSE sending initial status for task {task_id}: {task_status}")
            yield f"event: status\ndata: {dumps({'type': 'status', 'status': task_status, 'steps': task.steps, 'id': status_id})}\n\n"
            task_tracking["event_ids"].add(status_id)
        
        # If task is already complete or failed, send a final event and stop
        if task_status in ["complete", "failed"]:
            status_type = "complete" if task_status == "complete" else "error"
            sse_logger.debug(f"SSE task {task_id} already in {task_status} state")
            yield f"event: {status_type}\ndata: {dumps({'message': f'Task already {task_status}', 'id': task_id})}\n\n"
            sse_logger.debug(f"SSE ending stream for completed task {task_id}")
            return
        
        # Send an initial connection success message with unique ID 
        conn_id = f"connected-{str(uuid.uuid4())[:8]}"
        sse_logger.debug(f"SSE sending connected event: {conn_id}")
        yield f"event: connected\ndata: {dumps({'message': 'Connected to event stream', 'id': conn_id})}\n\n"
        task_tracking["event_ids"].add(conn_id)
        task_tracking["event_counter"]["connected"] += 1
        
        # Create a clean closure flag
        clean_closure = False
        
        try:
            while True:
                try:
                    # Use a timeout to allow for clean cancellation
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    # Skip events without type
                    if 'type' not in event:
                        sse_logger.debug(f"SSE skipping event without type")
                        continue
                    
                    # Generate a unique ID for each event if not present
                    if "id" not in event:
                        event["id"] = str(uuid.uuid4())
                    
                    # Check for duplicate event IDs
                    event_id = event.get("id")
                    if event_id in task_tracking["event_ids"]:
                        sse_logger.debug(f"SSE skipping duplicate event ID: {event_id}")
                        continue
                    
                    # Track this event ID to prevent duplicates
                    task_tracking["event_ids"].add(event_id)
                    
                    # Handle step number deduplication
                    if event["type"] == "step" and "step" in event:
                        step_num = event["step"]
                        if step_num in task_tracking["step_numbers"]:
                            sse_logger.debug(f"SSE skipping duplicate step number: {step_num}")
                            continue
                        task_tracking["step_numbers"].add(step_num)
                    
                    # Track event type
                    event_type = event.get("type", "unknown")
                    if event_type in task_tracking["event_counter"]:
                        task_tracking["event_counter"][event_type] += 1
                    
                    # Add timestamp if not present
                    if "timestamp" not in event:
                        event["timestamp"] = datetime.now().strftime("%H:%M:%S")
                    
                    sse_logger.debug(f"SSE processing event: {event_type} #{task_tracking['event_counter'].get(event_type, 0)} - ID: {event_id}")
                    
                    formatted_event = dumps(event)
                    
                    # Heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
                    
                    if event["type"] == "complete":
                        sse_logger.debug(f"SSE task {task_id} completed, sending complete event and ending stream")
                        logger.info(f"[SSE] Task {task_id} completed, sending complete event and ending stream")
                        yield f"event: complete\ndata: {formatted_event}\n\n"
                        clean_closure = True
                        break
                    elif event["type"] == "error":
                        sse_logger.debug(f"SSE task {task_id} failed, sending error event and ending stream")
                        logger.error(f"[SSE] Task {task_id} failed, sending error event and ending stream")
                        yield f"event: error\ndata: {formatted_event}\n\n"
                        clean_closure = True
                        break
                    elif event["type"] == "step":
                        task = task_manager.tasks.get(task_id)
                        if task:
                            # Only send status updates periodically, not with every step
                            if task_tracking["event_counter"]["step"] % 5 == 0:
                                status_update_id = f"status-{event_id}"
                                sse_logger.debug(f"SSE sending periodic status update for step #{task_tracking['event_counter']['step']}")
                                yield f"event: status\ndata: {dumps({'type': 'status', 'status': task.status, 'steps': task.steps, 'id': status_update_id})}\n\n"
                                task_tracking["event_ids"].add(status_update_id)
                        
                        sse_logger.debug(f"SSE sending step event #{task_tracking['event_counter']['step']}")
                        yield f"event: {event['type']}\ndata: {formatted_event}\n\n"
                    else:
                        sse_logger.debug(f"SSE sending {event['type']} event #{task_tracking['event_counter'].get(event['type'], 0)}")
                        yield f"event: {event['type']}\ndata: {formatted_event}\n\n"
                
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    sse_logger.debug(f"SSE sending heartbeat for task {task_id}")
                    yield ": heartbeat\n\n"
                    
                    # Check if task is still in the queue system
                    if task_id not in task_manager.queues:
                        sse_logger.debug(f"SSE task {task_id} queue no longer exists")
                        yield f"event: complete\ndata: {dumps({'message': 'Task processing completed', 'id': task_id})}\n\n"
                        clean_closure = True
                        break
                        
                    # Check if task is marked as complete but we missed the event
                    task = task_manager.tasks.get(task_id)
                    if task and task.status in ["complete", "failed"]:
                        status_type = "complete" if task.status == "complete" else "error"
                        sse_logger.debug(f"SSE task {task_id} is {task.status} but no event was sent")
                        yield f"event: {status_type}\ndata: {dumps({'message': f'Task {task.status}', 'id': task_id})}\n\n"
                        clean_closure = True
                        break
                
                except asyncio.CancelledError:
                    sse_logger.debug(f"SSE stream cancelled for task {task_id}")
                    logger.error(f"[SSE] Stream cancelled for task {task_id}")
                    yield f"event: error\ndata: {dumps({'message': 'Stream cancelled'})}\n\n"
                    break
                
                except Exception as e:
                    sse_logger.debug(f"SSE error in event stream for task {task_id}: {str(e)}")
                    logger.error(f"[SSE] Error in event stream for task {task_id}: {str(e)}")
                    yield f"event: error\ndata: {dumps({'message': str(e)})}\n\n"
                    break
        
        finally:
            # Clean up on exit
            if not clean_closure:
                sse_logger.debug(f"SSE stream ended for task {task_id} without clean closure")
                # Only yield final message if we didn't have a clean closure
                yield f"event: error\ndata: {dumps({'message': 'Stream ended unexpectedly'})}\n\n"
            
            # Log final event counts
            sse_logger.debug(f"SSE final event counts for task {task_id}: {task_tracking['event_counter']}")
            
            # Clean up event tracking when stream ends
            # Don't remove it entirely as other connections may still be active
            # Just reset counters and allow for new connections
            if task_id in _task_events and clean_closure:
                _task_events[task_id]["event_counter"] = {
                    "connected": 0,
                    "status": 0,
                    "step": 0,
                    "think": 0, 
                    "tool": 0,
                    "result": 0,
                    "complete": 0,
                    "error": 0
                }
    
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


@app.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
):
    if task_id not in task_manager.tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_manager.tasks[task_id]


@app.get("/config/status")
async def check_config_status(
    current_user: UserInDB = Depends(get_current_admin_user)
):
    config_path = Path(__file__).parent / "config" / "config.toml"
    example_config_path = Path(__file__).parent / "config" / "config.example.toml"

    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                current_config = tomllib.load(f)
            return {"status": "exists", "config": current_config}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    elif example_config_path.exists():
        try:
            with open(example_config_path, "rb") as f:
                example_config = tomllib.load(f)
            return {"status": "missing", "example_config": example_config}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    else:
        return {"status": "no_example"}


@app.post("/config/save")
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

        if not config_path.exists():
            return {"host": "localhost", "port": 5172}

        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        return {"host": config["server"]["host"], "port": config["server"]["port"]}
    except FileNotFoundError:
        return {"host": "localhost", "port": 5172}
    except KeyError as e:
        logger.error(
            f"The configuration file is missing necessary fields: {str(e)}, use default configuration"
        )
        return {"host": "localhost", "port": 5172}


if __name__ == "__main__":
    import uvicorn

    config = load_config()
    open_with_config = partial(open_local_browser, config)
    threading.Timer(3, open_with_config).start()
    uvicorn.run(app, host=config["host"], port=config["port"])
