"""
Модуль калькулятора зарплаты.
Работает через ядро, не обращается к БД напрямую.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime


class CalculatorModule:
    """
    Модуль расчёта зарплаты и связанных вычислений.
    Все данные получает через ядро от модуля db_access.
    """
    
    def __init__(self):
        self._core = None
    
    def set_core(self, core) -> None:
        """Установка ссылки на ядро."""
        self._core = core
    
    def calculate_salary(self, employee_id: int, 
                        bonus: float = 0.0, 
                        tax_rate: float = 0.13) -> Optional[Dict[str, Any]]:
        """
        Расчёт зарплаты сотрудника с учётом бонусов и налогов.
        Данные сотрудника получает через ядро из БД.
        """
        # Получение данных сотрудника через ядро
        employee = self._core.request_db('get_employee', employee_id=employee_id)
        
        if not employee:
            return None
        
        base_salary = employee.get('salary', 0.0)
        gross_salary = base_salary + bonus
        tax = gross_salary * tax_rate
        net_salary = gross_salary - tax
        
        result = {
            'employee_id': employee_id,
            'employee_name': employee.get('name'),
            'base_salary': base_salary,
            'bonus': bonus,
            'gross_salary': gross_salary,
            'tax_rate': tax_rate,
            'tax_amount': tax,
            'net_salary': net_salary,
            'calculated_at': datetime.utcnow().isoformat()
        }
        
        return result
    
    def calculate_department_salaries(self, department: str,
                                     bonus: float = 0.0,
                                     tax_rate: float = 0.13) -> List[Dict[str, Any]]:
        """
        Расчёт зарплат всех сотрудников департамента.
        """
        employees = self._core.request_db(
            'get_employees_by_department', 
            department=department
        )
        
        results = []
        for emp in employees:
            calc = self.calculate_salary(emp['id'], bonus, tax_rate)
            if calc:
                results.append(calc)
        
        return results
    
    def calculate_salary_range(self, min_salary: float, max_salary: float,
                              bonus: float = 0.0,
                              tax_rate: float = 0.13) -> List[Dict[str, Any]]:
        """
        Расчёт зарплат сотрудников в диапазоне зарплат.
        """
        employees = self._core.request_db(
            'get_employees_by_salary_range',
            min_salary=min_salary,
            max_salary=max_salary
        )
        
        results = []
        for emp in employees:
            calc = self.calculate_salary(emp['id'], bonus, tax_rate)
            if calc:
                results.append(calc)
        
        return results
    
    def get_total_payroll(self, department: str = None) -> Dict[str, Any]:
        """
        Расчёт общего фонда оплаты труда.
        """
        if department:
            employees = self._core.request_db(
                'get_employees_by_department',
                department=department
            )
        else:
            employees = self._core.request_db('get_all_employees')
        
        total_base = sum(emp.get('salary', 0.0) for emp in employees)
        total_employees = len(employees)
        
        return {
            'total_employees': total_employees,
            'total_base_salary': total_base,
            'department': department,
            'calculated_at': datetime.utcnow().isoformat()
        }
    
    def calculate_bonus_percentage(self, employee_id: int, 
                                   percentage: float) -> Optional[Dict[str, Any]]:
        """
        Расчёт бонуса в процентах от зарплаты.
        """
        employee = self._core.request_db('get_employee', employee_id=employee_id)
        
        if not employee:
            return None
        
        base_salary = employee.get('salary', 0.0)
        bonus = base_salary * (percentage / 100.0)
        
        return self.calculate_salary(employee_id, bonus)
