# Python version check: 3.11-3.13
import sys


if sys.version_info < (3, 11) or sys.version_info > (3, 13):
    print(
        "Warning: Unsupported Python version {ver}, please use 3.11-3.13".format(
            ver=".".join(map(str, sys.version_info))
        )
    )

# Import TaskManager and task_manager to expose it in the app module
import importlib.util
import os

# Need to handle circular imports by lazily importing task_manager when needed
_task_manager = None

def get_task_manager():
    """Get the task_manager instance from the main app.py file."""
    global _task_manager
    if _task_manager is None:
        try:
            # Use importlib to import task_manager from app.py
            module_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")
            spec = importlib.util.spec_from_file_location("app_main", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Get the task_manager from the loaded module
            _task_manager = module.task_manager
        except Exception as e:
            print(f"Error importing task_manager: {e}")
            raise
    return _task_manager

# Make task_manager accessible via property for lazy loading
class TaskManagerProxy:
    def __getattr__(self, name):
        return getattr(get_task_manager(), name)

task_manager = TaskManagerProxy()
