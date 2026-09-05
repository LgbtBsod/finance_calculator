"""
API модуль - предоставляет HTTP интерфейс.
Работает через ядро, не обращается к другим модулям напрямую.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime


class APIModule:
    """
    API модуль для предоставления HTTP endpoints.
    Все операции выполняет через ядро, не обращаясь к другим модулям напрямую.
    """
    
    def __init__(self):
        self._core = None
    
    def set_core(self, core) -> None:
        """Установка ссылки на ядро."""
        self._core = core
    
    # === Employee endpoints ===
    
    def create_employee(self, name: str, position: str = None,
                       department: str = None, salary: float = 0.0,
                       birth_date: str = None) -> Dict[str, Any]:
        """Создание сотрудника через API."""
        birth_dt = None
        if birth_date:
            birth_dt = datetime.fromisoformat(birth_date)
        
        result = self._core.request_db(
            'create_employee',
            name=name,
            position=position,
            department=department,
            salary=salary,
            birth_date=birth_dt
        )
        
        return {
            'success': True,
            'data': result,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_employee(self, employee_id: int) -> Dict[str, Any]:
        """Получение сотрудника по ID через API."""
        # Проверка кэша
        cache_key = f"employee_{employee_id}"
        cached = self._core.cache_get(cache_key)
        if cached is not None:
            return {
                'success': True,
                'data': cached,
                'from_cache': True,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Запрос к БД через ядро
        employee = self._core.request_db('get_employee', employee_id=employee_id)
        
        if not employee:
            return {
                'success': False,
                'error': 'Employee not found',
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Сохранение в кэш
        self._core.cache_set(cache_key, employee, ttl=300)
        
        return {
            'success': True,
            'data': employee,
            'from_cache': False,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_all_employees(self) -> Dict[str, Any]:
        """Получение всех сотрудников через API."""
        # Проверка кэша
        cached = self._core.cache_get("employees_list")
        if cached is not None:
            return {
                'success': True,
                'data': cached,
                'from_cache': True,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Запрос к БД через ядро
        employees = self._core.request_db('get_all_employees')
        
        # Сохранение в кэш
        self._core.cache_set("employees_list", employees, ttl=60)
        
        return {
            'success': True,
            'data': employees,
            'from_cache': False,
            'count': len(employees),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def update_employee(self, employee_id: int, **kwargs) -> Dict[str, Any]:
        """Обновление сотрудника через API."""
        result = self._core.request_db(
            'update_employee',
            employee_id=employee_id,
            **kwargs
        )
        
        if not result:
            return {
                'success': False,
                'error': 'Employee not found',
                'timestamp': datetime.utcnow().isoformat()
            }
        
        return {
            'success': True,
            'data': result,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def delete_employee(self, employee_id: int) -> Dict[str, Any]:
        """Удаление сотрудника через API."""
        success = self._core.request_db('delete_employee', employee_id=employee_id)
        
        return {
            'success': success,
            'message': 'Employee deleted' if success else 'Employee not found',
            'timestamp': datetime.utcnow().isoformat()
        }
    
    # === Calculator endpoints ===
    
    def calculate_salary(self, employee_id: int, 
                        bonus: float = 0.0,
                        tax_rate: float = 0.13) -> Dict[str, Any]:
        """Расчёт зарплаты через API."""
        result = self._core.execute(
            'calculator',
            'calculate_salary',
            employee_id=employee_id,
            bonus=bonus,
            tax_rate=tax_rate
        )
        
        if not result:
            return {
                'success': False,
                'error': 'Employee not found',
                'timestamp': datetime.utcnow().isoformat()
            }
        
        return {
            'success': True,
            'data': result,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_department_salaries(self, department: str,
                               bonus: float = 0.0,
                               tax_rate: float = 0.13) -> Dict[str, Any]:
        """Расчёт зарплат департамента через API."""
        results = self._core.execute(
            'calculator',
            'calculate_department_salaries',
            department=department,
            bonus=bonus,
            tax_rate=tax_rate
        )
        
        return {
            'success': True,
            'data': results,
            'count': len(results),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_total_payroll(self, department: str = None) -> Dict[str, Any]:
        """Получение общего фонда оплаты труда через API."""
        result = self._core.execute(
            'calculator',
            'get_total_payroll',
            department=department
        )
        
        return {
            'success': True,
            'data': result,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    # === Cache management endpoints ===
    
    def clear_cache(self) -> Dict[str, Any]:
        """Очистка кэша через API."""
        self._core.cache_clear()
        
        return {
            'success': True,
            'message': 'Cache cleared',
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Получение статистики кэша через API."""
        cache_module = self._core.get_cache_module()
        if not cache_module:
            return {
                'success': False,
                'error': 'Cache module not initialized',
                'timestamp': datetime.utcnow().isoformat()
            }
        
        stats = cache_module.stats()
        
        return {
            'success': True,
            'data': stats,
            'timestamp': datetime.utcnow().isoformat()
        }
