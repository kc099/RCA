import io
import base64
from typing import Optional
from PIL import Image, ImageDraw
from app.tool.base import BaseTool, ToolResult

class ImageGenTool(BaseTool):
    name: str = "image_gen_tool"
    description: str = "Generate a simple image and return it as base64 for visualization."
    parameters: dict = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to display on the image."},
            "width": {"type": "integer", "default": 400},
            "height": {"type": "integer", "default": 200}
        },
        "required": ["text"]
    }

    async def execute(self, text: str, width: int = 400, height: int = 200) -> ToolResult:
        # Ensure width and height are valid integers and not None
        width = int(width) if width is not None else 400
        height = int(height) if height is not None else 200
        # Generate a simple image with PIL
        img = Image.new('RGB', (width, height), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((10, 10), text, fill=(0, 0, 0))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        base64_img = base64.b64encode(buffer.getvalue()).decode('utf-8')
        data_url = f"data:image/png;base64,{base64_img}"
        return ToolResult(output="Image generated.", base64_image=data_url, system="image")
