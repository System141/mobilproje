"""
Async task management API endpoints
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import uuid
import asyncio
from datetime import datetime

from erp_platform.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# In-memory task storage (use Redis in production)
tasks_store = {}


class TaskRequest(BaseModel):
    """Task submission request"""
    task_type: str
    parameters: Dict[str, Any] = {}
    priority: int = 5


class TaskStatus(BaseModel):
    """Task status response"""
    task_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    result: Optional[Any] = None
    error: Optional[str] = None


async def execute_task(task_id: str, task_type: str, parameters: Dict[str, Any]):
    """
    Execute a background task
    """
    try:
        tasks_store[task_id]["status"] = "running"
        tasks_store[task_id]["updated_at"] = datetime.now()
        
        # Simulate task execution
        await asyncio.sleep(5)
        
        # Task-specific logic would go here
        result = {
            "task_type": task_type,
            "parameters": parameters,
            "output": "Task completed successfully"
        }
        
        tasks_store[task_id]["status"] = "completed"
        tasks_store[task_id]["result"] = result
        tasks_store[task_id]["updated_at"] = datetime.now()
        
        logger.info(f"Task {task_id} completed successfully")
        
    except Exception as e:
        tasks_store[task_id]["status"] = "failed"
        tasks_store[task_id]["error"] = str(e)
        tasks_store[task_id]["updated_at"] = datetime.now()
        
        logger.error(f"Task {task_id} failed: {e}")


@router.post("/submit")
async def submit_task(
    request: TaskRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """
    Submit a new async task
    """
    task_id = str(uuid.uuid4())
    
    # Store task info
    tasks_store[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "task_type": request.task_type,
        "parameters": request.parameters,
        "priority": request.priority,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "result": None,
        "error": None
    }
    
    # Add to background tasks
    background_tasks.add_task(
        execute_task,
        task_id,
        request.task_type,
        request.parameters
    )
    
    logger.info(f"Task {task_id} submitted")
    
    return {"task_id": task_id}


@router.get("/status/{task_id}")
async def get_task_status(task_id: str) -> TaskStatus:
    """
    Get status of a specific task
    """
    if task_id not in tasks_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskStatus(**tasks_store[task_id])


@router.get("/list")
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 100
) -> List[TaskStatus]:
    """
    List all tasks with optional status filter
    """
    tasks = list(tasks_store.values())
    
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    
    # Sort by creation time (newest first)
    tasks.sort(key=lambda x: x["created_at"], reverse=True)
    
    # Apply limit
    tasks = tasks[:limit]
    
    return [TaskStatus(**t) for t in tasks]


@router.delete("/{task_id}")
async def cancel_task(task_id: str) -> Dict[str, str]:
    """
    Cancel a pending or running task
    """
    if task_id not in tasks_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks_store[task_id]
    
    if task["status"] in ["completed", "failed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel task in {task['status']} state"
        )
    
    task["status"] = "cancelled"
    task["updated_at"] = datetime.now()
    
    logger.info(f"Task {task_id} cancelled")
    
    return {"message": f"Task {task_id} cancelled"}


@router.delete("/cleanup/completed")
async def cleanup_completed_tasks() -> Dict[str, Any]:
    """
    Remove completed and failed tasks from storage
    """
    removed = []
    
    for task_id in list(tasks_store.keys()):
        if tasks_store[task_id]["status"] in ["completed", "failed", "cancelled"]:
            removed.append(task_id)
            del tasks_store[task_id]
    
    logger.info(f"Cleaned up {len(removed)} tasks")
    
    return {
        "removed_count": len(removed),
        "removed_tasks": removed
    }