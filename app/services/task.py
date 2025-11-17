"""
Task service layer
Business logic for task operations
Reference: https://fastapi.tiangolo.com/tutorial/sql-databases/
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from app.models.task import Task
from app.api.v1.schemas.task import TaskCreate, TaskUpdate


class TaskService:
    """
    Service class for task-related business logic
    Handles all database operations for tasks
    """
    
    @staticmethod
    async def get_task(db: AsyncSession, task_id: int) -> Optional[Task]:
        """
        Retrieve a single task by ID
        
        Args:
            db: Database session
            task_id: ID of the task to retrieve
            
        Returns:
            Task object if found, None otherwise
        """
        # Use select() for async queries (SQLAlchemy 2.0 style)
        # Reference: https://docs.sqlalchemy.org/en/20/tutorial/data_select.html
        result = await db.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_tasks(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        completed: Optional[bool] = None
    ) -> List[Task]:
        """
        Retrieve multiple tasks with optional filtering
        
        Args:
            db: Database session
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            completed: Optional filter by completion status
            
        Returns:
            List of Task objects
        """
        query = select(Task)
        
        # Apply filter if provided
        if completed is not None:
            query = query.where(Task.completed == completed)
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        # Order by creation date (newest first)
        query = query.order_by(Task.created_at.desc())
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def create_task(db: AsyncSession, task_data: TaskCreate) -> Task:
        """
        Create a new task
        
        Args:
            db: Database session
            task_data: Task creation data
            
        Returns:
            Created Task object
            
        Note: Don't commit here - let the get_db() dependency handle commit/rollback
        Reference: https://docs.sqlalchemy.org/en/20/orm/session_basics.html#committing
        """
        # Create new task instance from schema data
        task = Task(
            title=task_data.title,
            description=task_data.description,
            completed=task_data.completed
        )
        
        # Add to session
        db.add(task)
        # Flush to get database-generated ID (without committing)
        # This sends the INSERT to the database and gets the ID back
        # With server_default, timestamps are set by the database
        await db.flush()
        # After flush, task.id is available
        # For timestamps, we'll let the response handle it
        # The database has the values, but we don't refresh to avoid connection issues
        
        # Note: Commit will be handled by get_db() dependency
        # Timestamps will be None initially but the database has the correct values
        return task
    
    @staticmethod
    async def update_task(
        db: AsyncSession,
        task_id: int,
        task_data: TaskUpdate
    ) -> Optional[Task]:
        """
        Update an existing task
        
        Args:
            db: Database session
            task_id: ID of the task to update
            task_data: Task update data (partial)
            
        Returns:
            Updated Task object if found, None otherwise
        """
        # Get existing task
        task = await TaskService.get_task(db, task_id)
        if not task:
            return None
        
        # Update only provided fields
        update_data = task_data.model_dump(exclude_unset=True)  # Only include set fields
        for field, value in update_data.items():
            setattr(task, field, value)
        
        # Don't commit here - let the get_db() dependency handle commit/rollback
        await db.flush()  # Flush changes to database (without committing)
        # Don't refresh here - timestamps will be available after commit
        # In serverless, refreshing before commit can cause connection issues
        
        return task
    
    @staticmethod
    async def delete_task(db: AsyncSession, task_id: int) -> bool:
        """
        Delete a task
        
        Args:
            db: Database session
            task_id: ID of the task to delete
            
        Returns:
            True if task was deleted, False if not found
        """
        # Get task first
        task = await TaskService.get_task(db, task_id)
        if not task:
            return False
        
        # Delete task
        # Don't commit here - let the get_db() dependency handle commit/rollback
        await db.delete(task)
        # No need to flush for delete - commit will handle it
        
        return True

