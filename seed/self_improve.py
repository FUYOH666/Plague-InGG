"""
Self-improvement module for hot reload and autonomous evolution.
Provides capabilities for dynamic tool registration, performance monitoring,
and automatic system updates.
"""

import importlib
import inspect
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PROJECT_ROOT = Path(__file__).parent.parent


class SelfImprover:
    """Manages self-improvement processes including hot reload and evolution."""
    
    def __init__(self):
        self.start_time = time.time()
        self.evolution_log_path = PROJECT_ROOT / "data" / "memory" / "evolution-log.md"
        self.metrics: Dict[str, Any] = {
            "total_evolutions": 0,
            "last_evolution_time": None,
            "tools_loaded": 0,
            "performance_samples": []
        }
    
    def load_module(self, module_path: str, force_reload: bool = False) -> Dict[str, Any]:
        """
        Load or reload a Python module dynamically.
        
        Args:
            module_path: Dot-separated module path (e.g., 'seed.tools')
            force_reload: If True, forces reload even if module is already loaded
            
        Returns:
            Dictionary with module info and reload status
        """
        try:
            if force_reload and module_path in sys.modules:
                # Remove module to force reload
                del sys.modules[module_path]
            
            module = importlib.import_module(module_path)
            module_info = {
                "name": module.__name__,
                "path": inspect.getfile(module),
                "functions": [name for name, obj in inspect.getmembers(module, inspect.isfunction)],
                "classes": [name for name, obj in inspect.getmembers(module, inspect.isclass)],
                "loaded_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self.metrics["tools_loaded"] += 1
            self._log_evolution(f"Модуль {module_path} загружен с {len(module_info['functions'])} функций")
            
            return module_info
            
        except Exception as e:
            error_msg = f"Ошибка загрузки модуля {module_path}: {str(e)}"
            self._log_evolution(error_msg)
            return {"error": error_msg, "module": module_path}
    
    def register_tool(self, tool_func: Callable, tool_name: str, description: str) -> Dict[str, Any]:
        """
        Register a new tool function in the system.
        
        Args:
            tool_func: The tool function to register
            tool_name: Name of the tool (snake_case)
            description: Tool description for LLM
            
        Returns:
            Registration result with tool metadata
        """
        try:
            # Extract function signature
            sig = inspect.signature(tool_func)
            parameters = {
                name: {
                    "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "string",
                    "description": param.default.__doc__ if param.default != inspect.Parameter.empty else ""
                }
                for name, param in sig.parameters.items()
            }
            
            tool_metadata = {
                "name": tool_name,
                "description": description,
                "parameters": parameters,
                "code": inspect.getsource(tool_func),
                "registered_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self._log_evolution(f"Инструмент '{tool_name}' зарегистрирован: {description}")
            
            return {
                "success": True,
                "tool": tool_metadata,
                "message": f"Инструмент '{tool_name}' успешно зарегистрирован"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Ошибка регистрации инструмента '{tool_name}'"
            }
    
    def monitor_performance(self) -> Dict[str, Any]:
        """
        Monitor system performance metrics.
        
        Returns:
            Performance metrics including latency, errors, and resource usage
        """
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        # Sample current performance
        sample = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "uptime_seconds": elapsed,
            "metrics": self.metrics.copy()
        }
        
        self.metrics["performance_samples"].append(sample)
        
        # Calculate average latency from recent samples
        recent_samples = self.metrics["performance_samples"][-10:]
        if len(recent_samples) > 1:
            intervals = [
                recent_samples[i+1]["uptime_seconds"] - recent_samples[i]["uptime_seconds"]
                for i in range(len(recent_samples) - 1)
            ]
            avg_latency = sum(intervals) / len(intervals) if intervals else 0
        else:
            avg_latency = 0
        
        performance_report = {
            "status": "healthy",
            "uptime": f"{elapsed:.1f} секунд",
            "average_latency": f"{avg_latency:.2f} секунд",
            "total_evolutions": self.metrics["total_evolutions"],
            "tools_loaded": self.metrics["tools_loaded"],
            "last_evolution": self.metrics["last_evolution_time"],
            "recent_samples": len(recent_samples)
        }
        
        return performance_report
    
    def _log_evolution(self, message: str):
        """Log an evolution event to the evolution log."""
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"\n## {timestamp} — {message}"
        
        try:
            # Append to evolution log
            evolution_log = self.evolution_log_path.read_text()
            evolution_log += log_entry
            self.evolution_log_path.write_text(evolution_log)
            
            # Update metrics
            self.metrics["total_evolutions"] += 1
            self.metrics["last_evolution_time"] = timestamp
            
        except Exception as e:
            print(f"Ошибка логирования эволюции: {e}")
    
    def get_evolution_summary(self) -> str:
        """Generate a summary of system evolution."""
        performance = self.monitor_performance()
        
        summary = f"""
**Эволюция системы Ekaterina v2**

📊 **Статистика:**
- Время работы: {performance['uptime']}
- Средняя задержка: {performance['average_latency']}
- Всего эволюций: {performance['total_evolutions']}
- Загружено инструментов: {performance['tools_loaded']}

🔄 **Последние изменения:**
- Статус: {performance['status']}
- Последняя эволюция: {performance['last_evolution']}
- Образцов мониторинга: {performance['recent_samples']}
"""
        return summary.strip()


# Convenience functions for easier access

def self_improve(action: str, **kwargs) -> Dict[str, Any]:
    """
    Main interface for self-improvement actions.
    
    Args:
        action: Type of action ('reload', 'register', 'monitor', 'summary')
        **kwargs: Action-specific parameters
        
    Returns:
        Action result dictionary
    """
    self_improver = SelfImprover()
    
    if action == "reload":
        return self_improver.load_module(
            module_path=kwargs.get("module_path", "seed.tools"),
            force_reload=kwargs.get("force_reload", True)
        )
    
    elif action == "register":
        return self_improver.register_tool(
            tool_func=kwargs.get("tool_func"),
            tool_name=kwargs.get("tool_name"),
            description=kwargs.get("description")
        )
    
    elif action == "monitor":
        return self_improver.monitor_performance()
    
    elif action == "summary":
        return {"summary": self_improver.get_evolution_summary()}
    
    else:
        return {"error": f"Неизвестное действие: {action}"}


# Import sys for module management
import sys