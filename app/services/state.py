import ast
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict
import threading

from app.config import config
from app.models import const


# Base class for state management
class BaseState(ABC):
    @abstractmethod
    def update_task(self, task_id: str, state: int, progress: int = 0, **kwargs):
        pass

    @abstractmethod
    def get_task(self, task_id: str):
        pass

    @abstractmethod
    def get_all_tasks(self, page: int, page_size: int):
        pass


# Memory state management
class MemoryState(BaseState):
    def __init__(self):
        self._tasks = {}
        self.lock = threading.Lock()

    def get_all_tasks(self, page: int, page_size: int):
        start = (page - 1) * page_size
        end = start + page_size
        tasks = list(self._tasks.values())
        total = len(tasks)
        return tasks[start:end], total

    def update_task(
        self,
        task_id: str,
        state: int = const.TASK_STATE_PROCESSING,
        progress: int = 0,
        **kwargs,
    ):
        progress = int(progress)
        if progress > 100:
            progress = 100

        try:
            with self.lock:
                if task_id not in self._tasks:
                    self._tasks[task_id] = {
                        "task_id": task_id,
                        "state": state,
                        "progress": progress,
                        "error": None,
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }
                
                # Update task fields
                for key, value in kwargs.items():
                    self._tasks[task_id][key] = value
                
                # Always update the timestamp
                self._tasks[task_id]["updated_at"] = datetime.now().isoformat()
                
                # Log state changes
                if "state" in kwargs:
                    logger.info(f"Task {task_id} state changed to {kwargs['state']}")
                if "error" in kwargs and kwargs["error"]:
                    logger.error(f"Task {task_id} error: {kwargs['error']}")
                    
        except Exception as e:
            logger.error(f"Error updating task state: {str(e)}")
            raise

    def get_task(self, task_id: str):
        try:
            with self.lock:
                return self._tasks.get(task_id, None)
        except Exception as e:
            logger.error(f"Error getting task state: {str(e)}")
            return None

    def delete_task(self, task_id: str):
        try:
            with self.lock:
                if task_id in self._tasks:
                    del self._tasks[task_id]
                    logger.info(f"Task {task_id} deleted")
        except Exception as e:
            logger.error(f"Error deleting task: {str(e)}")
            raise


# Redis state management
class RedisState(BaseState):
    def __init__(self, host="localhost", port=6379, db=0, password=None):
        import redis

        self._redis = redis.StrictRedis(host=host, port=port, db=db, password=password)

    def get_all_tasks(self, page: int, page_size: int):
        start = (page - 1) * page_size
        end = start + page_size
        tasks = []
        cursor = 0
        total = 0
        while True:
            cursor, keys = self._redis.scan(cursor, count=page_size)
            total += len(keys)
            if total > start:
                for key in keys[max(0, start - total):end - total]:
                    task_data = self._redis.hgetall(key)
                    task = {
                        k.decode("utf-8"): self._convert_to_original_type(v) for k, v in task_data.items()
                    }
                    tasks.append(task)
                    if len(tasks) >= page_size:
                        break
            if cursor == 0 or len(tasks) >= page_size:
                break
        return tasks, total

    def update_task(
        self,
        task_id: str,
        state: int = const.TASK_STATE_PROCESSING,
        progress: int = 0,
        **kwargs,
    ):
        progress = int(progress)
        if progress > 100:
            progress = 100

        fields = {
            "task_id": task_id,
            "state": state,
            "progress": progress,
            **kwargs,
        }

        for field, value in fields.items():
            self._redis.hset(task_id, field, str(value))

    def get_task(self, task_id: str):
        task_data = self._redis.hgetall(task_id)
        if not task_data:
            return None

        task = {
            key.decode("utf-8"): self._convert_to_original_type(value)
            for key, value in task_data.items()
        }
        return task

    def delete_task(self, task_id: str):
        self._redis.delete(task_id)

    @staticmethod
    def _convert_to_original_type(value):
        """
        Convert the value from byte string to its original data type.
        You can extend this method to handle other data types as needed.
        """
        value_str = value.decode("utf-8")

        try:
            # try to convert byte string array to list
            return ast.literal_eval(value_str)
        except (ValueError, SyntaxError):
            pass

        if value_str.isdigit():
            return int(value_str)
        # Add more conversions here if needed
        return value_str


# Global state
_enable_redis = config.app.get("enable_redis", False)
_redis_host = config.app.get("redis_host", "localhost")
_redis_port = config.app.get("redis_port", 6379)
_redis_db = config.app.get("redis_db", 0)
_redis_password = config.app.get("redis_password", None)

state = (
    RedisState(
        host=_redis_host, port=_redis_port, db=_redis_db, password=_redis_password
    )
    if _enable_redis
    else MemoryState()
)

class StateManager:
    def __init__(self):
        self.tasks = {}
        self.lock = threading.Lock()
        
    def update_task(self, task_id: str, **kwargs):
        """Update task state with thread safety."""
        try:
            with self.lock:
                if task_id not in self.tasks:
                    self.tasks[task_id] = {
                        "id": task_id,
                        "state": const.TASK_STATE_PENDING,
                        "progress": 0,
                        "error": None,
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }
                
                # Update task fields
                for key, value in kwargs.items():
                    self.tasks[task_id][key] = value
                
                # Always update the timestamp
                self.tasks[task_id]["updated_at"] = datetime.now().isoformat()
                
                # Log state changes
                if "state" in kwargs:
                    logger.info(f"Task {task_id} state changed to {kwargs['state']}")
                if "error" in kwargs and kwargs["error"]:
                    logger.error(f"Task {task_id} error: {kwargs['error']}")
                    
        except Exception as e:
            logger.error(f"Error updating task state: {str(e)}")
            raise
            
    def get_task(self, task_id: str) -> Dict:
        """Get task state with thread safety."""
        try:
            with self.lock:
                return self.tasks.get(task_id, None)
        except Exception as e:
            logger.error(f"Error getting task state: {str(e)}")
            return None
            
    def delete_task(self, task_id: str):
        """Delete task with thread safety."""
        try:
            with self.lock:
                if task_id in self.tasks:
                    del self.tasks[task_id]
                    logger.info(f"Task {task_id} deleted")
        except Exception as e:
            logger.error(f"Error deleting task: {str(e)}")
            raise
            
    def get_all_tasks(self) -> List[Dict]:
        """Get all tasks with thread safety."""
        try:
            with self.lock:
                return list(self.tasks.values())
        except Exception as e:
            logger.error(f"Error getting all tasks: {str(e)}")
            return []
            
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Clean up tasks older than max_age_hours."""
        try:
            with self.lock:
                now = datetime.now()
                tasks_to_delete = []
                
                for task_id, task in self.tasks.items():
                    created_at = datetime.fromisoformat(task["created_at"])
                    age = now - created_at
                    
                    if age.total_seconds() > max_age_hours * 3600:
                        tasks_to_delete.append(task_id)
                
                for task_id in tasks_to_delete:
                    del self.tasks[task_id]
                    logger.info(f"Cleaned up old task: {task_id}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up old tasks: {str(e)}")
            raise
