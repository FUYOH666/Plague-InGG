import json
from datetime import datetime
from typing import List, Dict, Any, Optional

class AutomationTool:
    """Инструмент для автоматизации процессов и задач"""
    
    def __init__(self):
        self.tasks = []
        self.workflows = []
        self.automation_log = []
        
    def create_task(self, task_id: str, name: str, priority: str, 
                   deadline: str, description: str = "") -> Dict[str, Any]:
        """Создание новой задачи"""
        task = {
            'task_id': task_id,
            'name': name,
            'description': description,
            'priority': priority,
            'deadline': deadline,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat()
        }
        self.tasks.append(task)
        self._log_action(f"Task created: {name}", task_id)
        return task
    
    def execute_workflow(self, workflow_name: str, steps: List[Dict], 
                        dependencies: List[str] = None) -> Dict[str, Any]:
        """Выполнение рабочего процесса"""
        workflow = {
            'workflow_id': f"WF-{len(self.workflows) + 1}",
            'workflow_name': workflow_name,
            'steps': steps,
            'dependencies': dependencies or [],
            'execution_date': datetime.now().isoformat(),
            'status': 'completed',
            'duration_hours': self._calculate_duration(steps)
        }
        self.workflows.append(workflow)
        self._log_action(f"Workflow executed: {workflow_name}", workflow['workflow_id'])
        return workflow
    
    def update_task_status(self, task_id: str, new_status: str, 
                          notes: str = "") -> Dict[str, Any]:
        """Обновление статуса задачи"""
        for task in self.tasks:
            if task['task_id'] == task_id:
                task['status'] = new_status
                task['last_updated'] = datetime.now().isoformat()
                if notes:
                    task['notes'] = notes
                self._log_action(f"Task {task_id} status updated to {new_status}", task_id)
                return task
        return {"error": f"Task {task_id} not found"}
    
    def _log_action(self, action: str, reference_id: str):
        """Логирование действий"""
        self.automation_log.append({
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'reference_id': reference_id,
            'type': 'automation'
        })
    
    def _calculate_duration(self, steps: List[Dict]) -> float:
        """Расчёт продолжительности рабочего процесса"""
        total_duration = sum(step.get('estimated_hours', 1) for step in steps)
        return total_duration
    
    def generate_report(self) -> str:
        """Генерация отчёта о проделанной работе"""
        report = {
            'total_tasks': len(self.tasks),
            'total_workflows': len(self.workflows),
            'total_actions': len(self.automation_log),
            'completion_rate': self._calculate_completion_rate(),
            'recent_activities': self._get_recent_activities(),
            'generated_at': datetime.now().isoformat()
        }
        return json.dumps(report, indent=2, ensure_ascii=False)
    
    def _calculate_completion_rate(self) -> float:
        """Расчёт процента выполнения"""
        completed_tasks = len([t for t in self.tasks if t['status'] == 'completed'])
        return (completed_tasks / len(self.tasks) * 100) if self.tasks else 0
    
    def _get_recent_activities(self) -> List[Dict]:
        """Получение последних активностей"""
        return self.automation_log[-10:] if self.automation_log else []
    
    def get_task_by_id(self, task_id: str) -> Optional[Dict]:
        """Получение задачи по ID"""
        for task in self.tasks:
            if task['task_id'] == task_id:
                return task
        return None
    
    def get_workflow_by_id(self, workflow_id: str) -> Optional[Dict]:
        """Получение рабочего процесса по ID"""
        for workflow in self.workflows:
            if workflow['workflow_id'] == workflow_id:
                return workflow
        return None

# Инициализация инструмента
automation = AutomationTool()

# Функция для выполнения задач
async def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Основная функция для обработки запросов"""
    # Создание задачи
    task = automation.create_task(
        task_id='AUTO-001',
        name='Автоматизация процессов',
        priority='high',
        deadline='2026-04-16',
        description='Управление и автоматизация повторяющихся задач'
    )
    
    # Выполнение рабочего процесса
    workflow = automation.execute_workflow(
        workflow_name='Эволюция систем',
        steps=[
            {'step': 'Анализ', 'status': 'completed', 'estimated_hours': 2},
            {'step': 'Разработка', 'status': 'completed', 'estimated_hours': 4},
            {'step': 'Тестирование', 'status': 'completed', 'estimated_hours': 3}
        ],
        dependencies=['analyzer', 'explorer', 'reflection_tool']
    )
    
    # Обновление статуса задачи
    automation.update_task_status('AUTO-001', 'completed', 'Все задачи выполнены успешно')
    
    # Генерация отчёта
    report = automation.generate_report()
    
    return {
        'status': 'success',
        'task': task,
        'workflow': workflow,
        'report': report,
        'message': 'Автоматизация успешно завершена'
    }

# Запуск при инициализации
if __name__ == '__main__':
    result = execute({'action': 'system_automation'})
    print(result['message'])
    print(f"\nОтчёт:\n{result['report']}")
