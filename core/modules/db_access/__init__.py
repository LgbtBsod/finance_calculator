"""
Модуль работы с базой данных через SQLAlchemy.
Никто не работает с БД напрямую - только через этот модуль и ядро.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class Employee(Base):
    """Модель сотрудника."""
    __tablename__ = 'employees'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    position = Column(String(100))
    department = Column(String(50))
    salary = Column(Float, default=0.0)
    birth_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'position': self.position,
            'department': self.department,
            'salary': self.salary,
            'birth_date': self.birth_date.isoformat() if self.birth_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class DBAccessModule:
    """
    Модуль доступа к базе данных.
    Все запросы к БД проходят только через этот модуль.
    Использует SQLAlchemy для построения оптимизированных запросов.
    """
    
    def __init__(self, db_url: str = "sqlite:///:memory:", echo: bool = False):
        self._core = None
        self._engine = create_engine(db_url, echo=echo)
        self._SessionLocal = sessionmaker(bind=self._engine)
        self._initialized = False
    
    def set_core(self, core) -> None:
        """Установка ссылки на ядро."""
        self._core = core
    
    def initialize(self) -> None:
        """Инициализация таблиц БД."""
        Base.metadata.create_all(self._engine)
        self._initialized = True
    
    def _get_session(self):
        """Получение сессии БД."""
        return self._SessionLocal()
    
    # === Операции с сотрудниками ===
    
    def create_employee(self, name: str, position: str = None, 
                       department: str = None, salary: float = 0.0,
                       birth_date: datetime = None) -> Dict[str, Any]:
        """Создание сотрудника."""
        session = self._get_session()
        try:
            employee = Employee(
                name=name,
                position=position,
                department=department,
                salary=salary,
                birth_date=birth_date
            )
            session.add(employee)
            session.commit()
            session.refresh(employee)
            result = employee.to_dict()
            
            # Инвалидация кэша при изменении данных
            if self._core:
                self._core.cache_delete("employees_list")
            
            return result
        finally:
            session.close()
    
    def get_employee(self, employee_id: int) -> Optional[Dict[str, Any]]:
        """Получение сотрудника по ID."""
        session = self._get_session()
        try:
            employee = session.query(Employee).filter(Employee.id == employee_id).first()
            return employee.to_dict() if employee else None
        finally:
            session.close()
    
    def get_all_employees(self) -> List[Dict[str, Any]]:
        """Получение всех сотрудников."""
        session = self._get_session()
        try:
            employees = session.query(Employee).all()
            return [emp.to_dict() for emp in employees]
        finally:
            session.close()
    
    def update_employee(self, employee_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        """Обновление данных сотрудника."""
        session = self._get_session()
        try:
            employee = session.query(Employee).filter(Employee.id == employee_id).first()
            if not employee:
                return None
            
            for key, value in kwargs.items():
                if hasattr(employee, key):
                    setattr(employee, key, value)
            
            session.commit()
            session.refresh(employee)
            result = employee.to_dict()
            
            # Инвалидация кэша
            if self._core:
                self._core.cache_delete(f"employee_{employee_id}")
                self._core.cache_delete("employees_list")
            
            return result
        finally:
            session.close()
    
    def delete_employee(self, employee_id: int) -> bool:
        """Удаление сотрудника."""
        session = self._get_session()
        try:
            employee = session.query(Employee).filter(Employee.id == employee_id).first()
            if not employee:
                return False
            
            session.delete(employee)
            session.commit()
            
            # Инвалидация кэша
            if self._core:
                self._core.cache_delete(f"employee_{employee_id}")
                self._core.cache_delete("employees_list")
            
            return True
        finally:
            session.close()
    
    def get_employees_by_department(self, department: str) -> List[Dict[str, Any]]:
        """Получение сотрудников по департаменту."""
        session = self._get_session()
        try:
            employees = session.query(Employee).filter(
                Employee.department == department
            ).all()
            return [emp.to_dict() for emp in employees]
        finally:
            session.close()
    
    def get_employees_by_salary_range(self, min_salary: float, 
                                      max_salary: float) -> List[Dict[str, Any]]:
        """Получение сотрудников в диапазоне зарплат."""
        session = self._get_session()
        try:
            employees = session.query(Employee).filter(
                Employee.salary >= min_salary,
                Employee.salary <= max_salary
            ).all()
            return [emp.to_dict() for emp in employees]
        finally:
            session.close()
    
    def execute_query(self, query_text: str, params: Dict = None) -> List[Dict[str, Any]]:
        """Выполнение произвольного SQL-запроса (для сложных случаев)."""
        session = self._get_session()
        try:
            result = session.execute(text(query_text), params or {})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
        finally:
            session.close()
