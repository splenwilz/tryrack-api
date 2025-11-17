"""
Task API routes
CRUD endpoints for task management
Reference: https://fastapi.tiangolo.com/tutorial/sql-databases/
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from app.services.task import TaskService


# Create router for task endpoints
router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],  # Groups endpoints in API documentation
    responses={
        404: {"description": "Task not found"},
        500: {"description": "Internal server error"}
    }
)


@router.get(
    "",
    response_model=List[TaskResponse],
    summary="List tasks",
    description="Retrieve a list of tasks with optional filtering and pagination",
    status_code=status.HTTP_200_OK
)
async def get_tasks(
    skip: int = Query(0, ge=0, description="Number of tasks to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tasks to return"),
    completed: Optional[bool] = Query(None, description="Filter by completion status"),
    db: AsyncSession = Depends(get_db)
) -> List[TaskResponse]:
    """
    Get a list of tasks
    
    Supports:
    - Pagination via skip and limit parameters
    - Filtering by completion status
    
    Returns:
        List of TaskResponse objects
    """
    tasks = await TaskService.get_tasks(db, skip=skip, limit=limit, completed=completed)
    return tasks


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get task by ID",
    description="Retrieve a single task by its ID",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Task not found"}
    }
)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db)
) -> TaskResponse:
    """
    Get a single task by ID
    
    Args:
        task_id: ID of the task to retrieve
        
    Returns:
        TaskResponse object
        
    Raises:
        HTTPException: If task is not found
    """
    task = await TaskService.get_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found"
        )
    return task


@router.post(
    "",
    response_model=TaskResponse,
    summary="Create task",
    description="Create a new task",
    status_code=status.HTTP_201_CREATED
)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db)
) -> TaskResponse:
    """
    Create a new task
    
    Args:
        task_data: Task creation data
        
    Returns:
        Created TaskResponse object
    """
    task = await TaskService.create_task(db, task_data)
    return task


@router.put(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update task",
    description="Update an existing task (all fields required)",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Task not found"}
    }
)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db)
) -> TaskResponse:
    """
    Update an existing task
    
    All fields in TaskUpdate are optional, allowing partial updates.
    Only provided fields will be updated.
    
    Args:
        task_id: ID of the task to update
        task_data: Task update data
        
    Returns:
        Updated TaskResponse object
        
    Raises:
        HTTPException: If task is not found
    """
    task = await TaskService.update_task(db, task_id, task_data)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found"
        )
    return task


@router.delete(
    "/{task_id}",
    summary="Delete task",
    description="Delete a task by ID",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Task not found"},
        204: {"description": "Task deleted successfully"}
    }
)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a task
    
    Args:
        task_id: ID of the task to delete
        
    Raises:
        HTTPException: If task is not found
    """
    deleted = await TaskService.delete_task(db, task_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found"
        )
    return None  # 204 No Content

