"""
Инициализация и запуск системы с модульной архитектурой.
Все модули регистрируются в ядре и общаются только через него.
"""

from core.modules.api import APIModule
from core.modules.calculator import CalculatorModule

from core.kernel import Kernel as Core
from core.kernel import get_kernel as get_core
from core.modules.cache import CacheModule
from core.modules.db_access import DBAccessModule


def initialize_system(db_url: str = "sqlite:///:memory:", echo: bool = False) -> Core:
    """
    Инициализация всей системы с модульной архитектурой.

    Args:
        db_url: URL подключения к базе данных
        echo: Логирование SQL запросов

    Returns:
        Экземпляр ядра системы
    """
    core = get_core()

    # 1. Инициализация модуля БД
    db_module = DBAccessModule(db_url=db_url, echo=echo)
    db_module.initialize()
    core.register_module("db_access", db_module)

    # 2. Инициализация модуля кэша
    cache_module = CacheModule(default_ttl=300)
    core.register_module("cache", cache_module)

    # 3. Регистрация модуля калькулятора
    calculator_module = CalculatorModule()
    core.register_module("calculator", calculator_module)

    # 4. Регистрация API модуля
    api_module = APIModule()
    core.register_module("api", api_module)

    return core


def demo():
    """Демонстрация работы модульной системы."""
    print("=" * 60)
    print("Модульная архитектура с ядром")
    print("=" * 60)

    # Инициализация системы
    core = initialize_system()

    # Получаем API модуль через ядро
    api = core.get_module("api")

    print("\n1. Создание сотрудников через API (через ядро -> db_access):")
    print("-" * 60)

    emp1 = api.create_employee(
        name="Иван Иванов", position="Разработчик", department="IT", salary=150000.0
    )
    print(f"Создан: {emp1['data']['name']} (ID: {emp1['data']['id']})")

    emp2 = api.create_employee(
        name="Петр Петров", position="Менеджер", department="Sales", salary=120000.0
    )
    print(f"Создан: {emp2['data']['name']} (ID: {emp2['data']['id']})")

    emp3 = api.create_employee(
        name="Анна Сидорова", position="Разработчик", department="IT", salary=180000.0
    )
    print(f"Создан: {emp3['data']['name']} (ID: {emp3['data']['id']})")

    print("\n2. Получение всех сотрудников (с кэшированием):")
    print("-" * 60)

    all_employees = api.get_all_employees()
    print(f"Всего сотрудников: {all_employees['count']}")
    print(f"Из кэша: {all_employees['from_cache']}")

    # Повторный запрос - должен быть из кэша
    all_employees_cached = api.get_all_employees()
    print(f"Повторный запрос из кэша: {all_employees_cached['from_cache']}")

    print("\n3. Расчёт зарплаты через калькулятор (через ядро):")
    print("-" * 60)

    salary_calc = api.calculate_salary(employee_id=1, bonus=20000.0)
    if salary_calc["success"]:
        data = salary_calc["data"]
        print(f"Сотрудник: {data['employee_name']}")
        print(f"Базовая зарплата: {data['base_salary']}")
        print(f"Бонус: {data['bonus']}")
        print(f"Налог: {data['tax_amount']}")
        print(f"На руки: {data['net_salary']}")

    print("\n4. Расчёт зарплат департамента IT:")
    print("-" * 60)

    dept_salaries = api.get_department_salaries(department="IT")
    print(f"Сотрудников в IT: {dept_salaries['count']}")
    for calc in dept_salaries["data"]:
        print(f"  - {calc['employee_name']}: {calc['net_salary']} на руки")

    print("\n5. Общий фонд оплаты труда:")
    print("-" * 60)

    payroll = api.get_total_payroll()
    data = payroll["data"]
    print(f"Всего сотрудников: {data['total_employees']}")
    print(f"Общий фонд: {data['total_base_salary']}")

    print("\n6. Статистика кэша:")
    print("-" * 60)

    cache_stats = api.get_cache_stats()
    print(f"Активных записей: {cache_stats['data']['active_entries']}")

    print("\n7. Очистка кэша:")
    print("-" * 60)

    clear_result = api.clear_cache()
    print(f"Кэш очищен: {clear_result['success']}")

    print("\n" + "=" * 60)
    print("Архитектура работает корректно!")
    print("- Модули не общаются напрямую")
    print("- Все запросы через ядро")
    print("- БД доступна только через db_access модуль")
    print("- Кэш управляется через ядро")
    print("=" * 60)


if __name__ == "__main__":
    demo()
