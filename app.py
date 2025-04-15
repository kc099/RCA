import asyncio
import os
import threading
import tomllib
import uuid
import webbrowser
from contextlib import asynccontextmanager
from datetime import datetime
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

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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
            task.steps.append({"step": step, "result": result, "type": step_type})
            await self.queues[task_id].put(
                {"type": step_type, "step": step, "result": result}
            )
            await self.queues[task_id].put(
                {"type": "status", "status": task.status, "steps": task.steps}
            )

    async def complete_task(self, task_id: str):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = "completed"
            await self.queues[task_id].put(
                {"type": "status", "status": task.status, "steps": task.steps}
            )
            await self.queues[task_id].put({"type": "complete"})

    async def fail_task(self, task_id: str, error: str):
        if task_id in self.tasks:
            self.tasks[task_id].status = f"failed: {error}"
            await self.queues[task_id].put({"type": "error", "message": error})


task_manager = TaskManager()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/download")
async def download_file(
    file_path: str,
    current_user: UserInDB = Depends(get_current_active_user)
):
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return Response(content=open(file_path, "rb").read(), media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename={os.path.basename(file_path)}"})


@app.post("/tasks")
async def create_task(
    prompt: str = Body(..., embed=True),
    current_user: UserInDB = Depends(get_current_active_user)
):
    task = task_manager.create_task(prompt)
    asyncio.create_task(run_task(task.id, prompt))
    return {"task_id": task.id}


# from app.agent.manus import Manus


async def run_task(task_id: str, prompt: str):
    try:
        task_manager.tasks[task_id].status = "running"

        # agent = Manus(
        #     name="Manus",
        #     description="A versatile agent that can solve various tasks using multiple tools",
        # )
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

            async def __call__(self, message):
                import re

                # Extract - Subsequent Content
                cleaned_message = re.sub(r"^.*? - ", "", message)

                event_type = "log"
                if "✨ Manus's thoughts:" in cleaned_message:
                    event_type = "think"
                elif "🛠️ Manus selected" in cleaned_message:
                    event_type = "tool"
                elif "🎯 Tool" in cleaned_message:
                    event_type = "act"
                elif "📝 Oops!" in cleaned_message:
                    event_type = "error"
                elif "🏁 Special tool" in cleaned_message:
                    event_type = "complete"

                await task_manager.update_task_step(
                    self.task_id, 0, cleaned_message, event_type
                )

        sse_handler = SSELogHandler(task_id)
        logger.add(sse_handler)

        result = await agent.run(prompt)
        await task_manager.update_task_step(task_id, 1, result, "result")
        await task_manager.complete_task(task_id)
    except Exception as e:
        await task_manager.fail_task(task_id, str(e))


@app.get("/tasks/{task_id}/events")
async def task_events(
    task_id: str,
    request: Request,
    token: Optional[str] = None,
    current_user: Optional[UserInDB] = None
):
    # Allow authentication via URL token parameter (for EventSource connections)
    if token and not current_user:
        try:
            user = await get_user_from_token(token)
            if user:
                current_user = user
                print(f"[SSE] Authenticated user {user.username} via token parameter")
            else:
                print(f"[SSE] Invalid token provided in URL parameter")
                return StreamingResponse(
                    iter([f"event: error\ndata: {dumps({'message': 'Invalid or expired token'})}\n\n"]),
                    media_type="text/event-stream",
                )
        except Exception as e:
            print(f"[SSE] Token authentication error: {str(e)}")
            return StreamingResponse(
                iter([f"event: error\ndata: {dumps({'message': 'Authentication failed'})}\n\n"]),
                media_type="text/event-stream",
            )
    
    # If no user is authenticated by any method, return error
    if not current_user:
        return StreamingResponse(
            iter([f"event: error\ndata: {dumps({'message': 'Authentication required'})}\n\n"]),
            media_type="text/event-stream",
        )
    
    async def event_generator():
        if task_id not in task_manager.queues:
            yield f"event: error\ndata: {dumps({'message': 'Task not found'})}\n\n"
            return
        
        queue = task_manager.queues[task_id]
        
        task = task_manager.tasks.get(task_id)
        task_status = "running"
        if task:
            task_status = task.status
            yield f"event: status\ndata: {dumps({'type': 'status', 'status': task_status, 'steps': task.steps})}\n\n"
        
        # If task is already complete or failed, send a final event and stop
        if task_status in ["complete", "failed"]:
            status_type = "complete" if task_status == "complete" else "error"
            yield f"event: {status_type}\ndata: {dumps({'message': f'Task already {task_status}', 'id': task_id})}\n\n"
            print(f"[SSE] Task {task_id} already in {task_status} state, ending stream")
            return
        
        # Send an initial connection success message
        yield f"event: connected\ndata: {dumps({'message': 'Connected to event stream'})}\n\n"
        
        # Create a clean closure flag
        clean_closure = False
        
        try:
            while True:
                try:
                    # Use a timeout to allow for clean cancellation
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    formatted_event = dumps(event)
                    
                    yield ": heartbeat\n\n"
                    
                    if event["type"] == "complete":
                        print(f"[SSE] Task {task_id} completed, sending complete event and ending stream")
                        yield f"event: complete\ndata: {formatted_event}\n\n"
                        clean_closure = True
                        break
                    elif event["type"] == "error":
                        print(f"[SSE] Task {task_id} failed, sending error event and ending stream")
                        yield f"event: error\ndata: {formatted_event}\n\n"
                        clean_closure = True
                        break
                    elif event["type"] == "step":
                        task = task_manager.tasks.get(task_id)
                        if task:
                            yield f"event: status\ndata: {dumps({'type': 'status', 'status': task.status, 'steps': task.steps})}\n\n"
                        yield f"event: {event['type']}\ndata: {formatted_event}\n\n"
                    elif event["type"] in ["think", "tool", "act", "run"]:
                        yield f"event: {event['type']}\ndata: {formatted_event}\n\n"
                    else:
                        yield f"event: {event['type']}\ndata: {formatted_event}\n\n"
                
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
                    
                    # Check if task is still in the queue system
                    if task_id not in task_manager.queues:
                        print(f"[SSE] Task {task_id} queue no longer exists, ending stream")
                        yield f"event: complete\ndata: {dumps({'message': 'Task processing completed', 'id': task_id})}\n\n"
                        clean_closure = True
                        break
                        
                    # Check if task is marked as complete but we missed the event
                    task = task_manager.tasks.get(task_id)
                    if task and task.status in ["complete", "failed"]:
                        status_type = "complete" if task.status == "complete" else "error"
                        print(f"[SSE] Task {task_id} is {task.status} but no event was sent, ending stream")
                        yield f"event: {status_type}\ndata: {dumps({'message': f'Task {task.status}', 'id': task_id})}\n\n"
                        clean_closure = True
                        break
                
                except asyncio.CancelledError:
                    print(f"[SSE] Stream cancelled for task {task_id}")
                    yield f"event: error\ndata: {dumps({'message': 'Stream cancelled'})}\n\n"
                    break
                
                except Exception as e:
                    print(f"[SSE] Error in event stream for task {task_id}: {str(e)}")
                    yield f"event: error\ndata: {dumps({'message': str(e)})}\n\n"
                    break
        
        finally:
            # Clean up on exit
            if not clean_closure:
                print(f"[SSE] Stream ended for task {task_id} without clean closure")
                # Only yield final message if we didn't have a clean closure
                yield f"event: error\ndata: {dumps({'message': 'Stream ended unexpectedly'})}\n\n"
    
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

        print(f"[AUTH LOG] {message}")
        if details:
            print(f"[AUTH LOG] Details: {details}")
        return {"status": "logged"}
    except Exception as e:
        print(f"[AUTH LOG ERROR] {str(e)}")
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
        print(
            f"The configuration file is missing necessary fields: {str(e)}, use default configuration"
        )
        return {"host": "localhost", "port": 5172}


if __name__ == "__main__":
    import uvicorn

    config = load_config()
    open_with_config = partial(open_local_browser, config)
    threading.Timer(3, open_with_config).start()
    uvicorn.run(app, host=config["host"], port=config["port"])
