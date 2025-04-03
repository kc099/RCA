from pydantic import Field

from app.agent.excel_agent import ExcelAgent
from app.config import config
from app.prompt.browser import NEXT_STEP_PROMPT as BROWSER_NEXT_STEP_PROMPT
from app.prompt.manus import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.browser_use_tool import BrowserUseTool
from app.tool.excel_tool import ExcelTool
from app.tool.python_execute import PythonExecute
from app.tool.str_replace_editor import StrReplaceEditor


class Manus(ExcelAgent):
    """
    A versatile general-purpose agent that uses planning to solve various tasks.

    This agent extends ExcelAgent with a comprehensive set of tools and capabilities,
    including Python execution, web browsing, Excel manipulation, file operations, 
    and information retrieval to handle a wide range of user requests.
    """

    name: str = "Manus"
    description: str = (
        "A versatile agent that can solve various tasks using multiple tools"
    )

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 10000
    max_steps: int = 20

    # Add general-purpose tools to the tool collection
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            PythonExecute(), BrowserUseTool(), ExcelTool(), StrReplaceEditor(), Terminate()
        )
    )

    async def run(self, request: str) -> str:
        """Process the request after moderation check."""
        # Check if request is allowed by the moderator
        is_allowed, reason = DataAnalyticsModerator.is_data_analytics_request(request)
        
        if not is_allowed:
            return f"Request denied: {reason}. Please provide a data analytics related request."
            
        # Process allowed request
        return await super().run(request)

    async def think(self) -> bool:
        """Process current state and decide next actions with appropriate context."""
        # Store original prompt
        original_prompt = self.next_step_prompt

        # Only check recent messages (last 3) for browser activity
        recent_messages = self.memory.messages[-3:] if self.memory.messages else []
        browser_in_use = any(
            "browser_use" in msg.content.lower()
            for msg in recent_messages
            if hasattr(msg, "content") and isinstance(msg.content, str)
        )

        # If browser is being used, switch to browser-specific prompt
        if browser_in_use:
            self.next_step_prompt = BROWSER_NEXT_STEP_PROMPT

        # Execute think with appropriate context
        result = await super().think()

        # Restore original prompt for next interaction
        self.next_step_prompt = original_prompt

        return result
