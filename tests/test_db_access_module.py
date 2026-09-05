"""
Модульные тесты для модуля работы с БД (DBAccessModule).
Тестируют CRUD операции, фильтрацию и работу через SQLAlchemy.
"""

import pytest
from datetime import datetime, timedelta
from core.modules.db_access import DBAccessModule, Employee


class TestDBAccessModule:
    """Тесты для модуля доступа к базе данных."""
    
    def setup_method(self):
        """Создание нового экземпляра БД перед каждым тестом."""
        self.db = DBAccessModule(db_url="sqlite:///:memory:")
        self.db.initialize()
    
    def test_create_employee(self):
        """Тест создания сотрудника."""
        employee = self.db.create_employee(
            name="Иван Иванов",
            position="Разработчик",
            department="IT",
            salary=150000.0
        )
        
        assert employee['id'] is not None
        assert employee['name'] == "Иван Иванов"
        assert employee['position'] == "Разработчик"
        assert employee['department'] == "IT"
        assert employee['salary'] == 150000.0
    
    def test_create_employee_with_birth_date(self):
        """Тест создания сотрудника с датой рождения."""
        birth_date = datetime(1990, 5, 15)
        employee = self.db.create_employee(
            name="Петр Петров",
            birth_date=birth_date
        )
        
        assert employee['birth_date'] == birth_date.isoformat()
    
    def test_get_employee_by_id(self):
        """Тест получения сотрудника по ID."""
        emp1 = self.db.create_employee(name="Иван Иванов", salary=100000.0)
        emp2 = self.db.create_employee(name="Петр Петров", salary=120000.0)
        
        retrieved = self.db.get_employee(emp1['id'])
        
        assert retrieved is not None
        assert retrieved['name'] == "Иван Иванов"
        assert retrieved['salary'] == 100000.0
        
        # Проверка что не возвращается другой сотрудник
        retrieved2 = self.db.get_employee(emp2['id'])
        assert retrieved2['name'] == "Петр Петров"
    
    def test_get_nonexistent_employee(self):
        """Тест получения несуществующего сотрудника."""
        result = self.db.get_employee(9999)
        assert result is None
    
    def test_get_all_employees(self):
        """Тест получения всех сотрудников."""
        self.db.create_employee(name="Иван Иванов")
        self.db.create_employee(name="Петр Петров")
        self.db.create_employee(name="Анна Сидорова")
        
        employees = self.db.get_all_employees()
        
        assert len(employees) == 3
        names = [emp['name'] for emp in employees]
        assert "Иван Иванов" in names
        assert "Петр Петров" in names
        assert "Анна Сидорова" in names
    
    def test_update_employee(self):
        """Тест обновления данных сотрудника."""
        employee = self.db.create_employee(
            name="Иван Иванов",
            salary=100000.0,
            position="Разработчик"
        )
        
        updated = self.db.update_employee(
            employee['id'],
            salary=150000.0,
            position="Senior Разработчик"
        )
        
        assert updated is not None
        assert updated['salary'] == 150000.0
        assert updated['position'] == "Senior Разработчик"
        
        # Проверка в БД
        retrieved = self.db.get_employee(employee['id'])
        assert retrieved['salary'] == 150000.0
    
    def test_update_nonexistent_employee(self):
        """Тест обновления несуществующего сотрудника."""
        result = self.db.update_employee(9999, salary=200000.0)
        assert result is None
    
    def test_delete_employee(self):
        """Тест удаления сотрудника."""
        employee = self.db.create_employee(name="Иван Иванов")
        
        success = self.db.delete_employee(employee['id'])
        
        assert success is True
        assert self.db.get_employee(employee['id']) is None
    
    def test_delete_nonexistent_employee(self):
        """Тест удаления несуществующего сотрудника."""
        success = self.db.delete_employee(9999)
        assert success is False
    
    def test_get_employees_by_department(self):
        """Тест получения сотрудников по департаменту."""
        self.db.create_employee(name="Иван Иванов", department="IT")
        self.db.create_employee(name="Петр Петров", department="IT")
        self.db.create_employee(name="Анна Сидорова", department="Sales")
        
        it_employees = self.db.get_employees_by_department("IT")
        
        assert len(it_employees) == 2
        assert all(emp['department'] == "IT" for emp in it_employees)
        
        sales_employees = self.db.get_employees_by_department("Sales")
        assert len(sales_employees) == 1
        assert sales_employees[0]['name'] == "Анна Сидорова"
    
    def test_get_employees_by_empty_department(self):
        """Тест получения сотрудников из несуществующего департамента."""
        self.db.create_employee(name="Иван Иванов", department="IT")
        
        result = self.db.get_employees_by_department("Marketing")
        
        assert len(result) == 0
    
    def test_get_employees_by_salary_range(self):
        """Тест получения сотрудников в диапазоне зарплат."""
        self.db.create_employee(name="Junior", salary=50000.0)
        self.db.create_employee(name="Middle", salary=100000.0)
        self.db.create_employee(name="Senior", salary=200000.0)
        self.db.create_employee(name="Lead", salary=300000.0)
        
        employees = self.db.get_employees_by_salary_range(
            min_salary=80000.0,
            max_salary=250000.0
        )
        
        assert len(employees) == 2
        salaries = [emp['salary'] for emp in employees]
        assert 100000.0 in salaries
        assert 200000.0 in salaries
    
    def test_employee_to_dict(self):
        """Тест конвертации модели сотрудника в словарь."""
        birth_date = datetime(1990, 1, 1)
        employee = Employee(
            id=1,
            name="Тест",
            position="Тестовая",
            department="Тест",
            salary=100.0,
            birth_date=birth_date
        )
        
        data = employee.to_dict()
        
        assert data['id'] == 1
        assert data['name'] == "Тест"
        assert data['position'] == "Тестовая"
        assert data['department'] == "Тест"
        assert data['salary'] == 100.0
        assert data['birth_date'] == birth_date.isoformat()
    
    def test_employee_to_dict_without_birth_date(self):
        """Тест конвертации без даты рождения."""
        employee = Employee(
            id=1,
            name="Тест",
            birth_date=None
        )
        
        data = employee.to_dict()
        
        assert data['birth_date'] is None
    
    def test_multiple_operations_transaction_isolation(self):
        """Тест изоляции транзакций при множественных операциях."""
        # Создаем нескольких сотрудников
        emp1 = self.db.create_employee(name="Emp1", salary=100000.0)
        emp2 = self.db.create_employee(name="Emp2", salary=200000.0)
        
        # Обновляем первого
        self.db.update_employee(emp1['id'], salary=150000.0)
        
        # Получаем всех
        all_emps = self.db.get_all_employees()
        
        assert len(all_emps) == 2
        emp1_updated = self.db.get_employee(emp1['id'])
        assert emp1_updated['salary'] == 150000.0
    
    def test_execute_query_raw_sql(self):
        """Тест выполнения произвольного SQL запроса."""
        self.db.create_employee(name="Иван Иванов", salary=100000.0)
        self.db.create_employee(name="Петр Петров", salary=200000.0)
        
        result = self.db.execute_query(
            "SELECT * FROM employees WHERE salary > :min_salary",
            params={"min_salary": 150000}
        )
        
        assert len(result) == 1
        assert result[0]['name'] == "Петр Петров"
    
    def test_db_module_core_integration(self):
        """Тест интеграции модуля БД с ядром."""
        from core.kernel import Kernel as Core, get_kernel as get_core, reset_kernel
        reset_kernel()
        
        from modules.cache.cache_manager import CacheManager
        
        core = get_core()
        cache = CacheManager()
        core.set_cache_module(cache)
        core.set_db_kernel(self.db)
        
        # Создаем сотрудника
        emp = self.db.create_employee(name="Test", salary=100000.0)
        
        # Кэш должен быть очищен после записи
        assert core.cache_get("employees_list") is None
        
        # Читаем через ядро
        result = core.request_db('get_employee', employee_id=emp['id'])
        assert result['name'] == "Test"
