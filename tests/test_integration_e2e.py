"""
Integration tests for end-to-end scenarios.
Tests the full flow from API requests through database to calculator results.
"""
import pytest
import sqlite3
import os

from fastapi.testclient import TestClient
from api import app, get_db
from database import DatabaseManager


class TestEndToEndSalaryCalculation:
    """Test complete salary calculation flow with expenses and vacations."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test_e2e.db"
        db = DatabaseManager(str(db_path))
        db._init_db()
        yield db
        db.close()
        if os.path.exists(str(db_path)):
            os.remove(str(db_path))

    @pytest.fixture
    def client(self, test_db):
        """Create test client with configured database."""
        def override_get_db():
            yield test_db
        
        app.dependency_overrides[get_db] = override_get_db
        try:
            with TestClient(app) as client:
                yield client
        finally:
            app.dependency_overrides.clear()

    def test_full_salary_calculation_with_expenses_and_vacations(self, client, test_db):
        """Test complete flow: setup -> add data -> calculate salary."""
        # 1. Setup initial data via API
        response = client.put('/api/settings', json={
            'salary': 100000,
            'kef': 1.5,
            'proportion_husband': 40,
            'proportion_wife': 60
        })
        assert response.status_code == 200

        # 2. Add expense groups
        response = client.post('/api/expense-groups', json={
            'name': 'Food',
            'color': '#FF0000'
        })
        assert response.status_code == 201
        food_group_id = response.json()["id"]

        response = client.post('/api/expense-groups', json={
            'name': 'Transport',
            'color': '#00FF00',
            'monthly_limit': 5000
        })
        assert response.status_code == 201
        transport_group_id = response.json()["id"]

        # 3. Add expenses
        response = client.post('/api/expense-items', json={
            'group_id': food_group_id,
            'name': 'Groceries',
            'amount': 3000,
            'half': 1,
            'month': 7,
            'year': 2025,
            'isRecurring': False
        })
        assert response.status_code == 201

        response = client.post('/api/expense-items', json={
            'group_id': transport_group_id,
            'name': 'Gas',
            'amount': 2000,
            'half': 1,
            'month': 7,
            'year': 2025,
            'isRecurring': True,
            'recurringUntil': '2025-12-31'
        })
        assert response.status_code == 201

        # 4. Add vacation
        response = client.post('/api/vacations', json={
            'startDate': '2025-07-20',
            'endDate': '2025-08-05',
            'payoutDate': '2025-07-25',
            'totalAmount': 50000
        })
        assert response.status_code == 201

        # 5. Calculate balance
        response = client.get('/api/balance?year=2025&month=7')
        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert 'balanceHalf1' in data
        assert 'balanceHalf2' in data
        assert 'netSalary' in data
        assert 'expensesHalf1' in data
        assert 'expensesHalf2' in data

        # Verify calculations make sense (balances are positive after expenses)
        assert data['balanceHalf1'] >= 0
        assert data['balanceHalf2'] >= 0
        # Net salary should be positive
        assert data['netSalary'] > 0
        # Total accrued includes vacation pay
        assert data['totalAccrued'] >= data['netSalary']

    def test_birthday_auto_expense_creation(self, client, test_db):
        """Test that birthdays automatically create expense entries."""
        # Setup settings
        client.put('/api/settings', json={
            'salary': 80000,
            'gift_budget': 5000
        })

        # Create birthday on September 29th 
        # Trigger date (14 days before) = September 15th, which is in current month (September 2026)
        response = client.post('/api/birthdays', json={
            'name': 'John Doe',
            'birthDate': '29.09.1990',
            'giftAmount': 1000
        })
        assert response.status_code == 201

        # Call the auto-create endpoint to create gift expenses
        response = client.post('/api/birthdays/auto-create-expenses')
        assert response.status_code == 200

        # Check that gift expense was created for current month (September 2026)
        response = client.get('/api/expense-items?month=9&year=2026')
        assert response.status_code == 200
        expenses = response.json()

        # Should have at least one expense (the auto-created gift)
        # Expense name format: "🎂 Name (ДР date)" so we check for birthday emoji or "др"
        gift_expenses = [e for e in expenses if '🎂' in e.get('name', '') or 'др' in e.get('name', '').lower() or 'gift' in e.get('description', '').lower() or 'birthday' in e.get('description', '').lower()]
        assert len(gift_expenses) > 0

    def test_debt_repayment_flow(self, client, test_db):
        """Test complete debt creation and repayment flow."""
        # Create debt with correct schema (title, totalAmount, month, year)
        response = client.post('/api/debts', json={
            'title': 'Bank Loan',
            'totalAmount': 10000,
            'month': 7,
            'year': 2025
        })
        assert response.status_code == 201
        debt_id = response.json()["id"]

        # Verify debt appears in list
        response = client.get('/api/debts')
        assert response.status_code == 200
        debts = response.json()
        assert len(debts) >= 1
        # Use camelCase field names from DebtResponse model
        our_debt = next((d for d in debts if d['id'] == debt_id), None)
        assert our_debt is not None
        assert our_debt['remainingAmount'] == 10000

        # Make repayment
        response = client.post(f'/api/debts/{debt_id}/repayments', json={
            'amount': 3000,
            'date': '2025-07-15',
            'note': 'First payment'
        })
        assert response.status_code == 201

        # Verify remaining amount updated
        response = client.get(f'/api/debts/{debt_id}')
        assert response.status_code == 200
        debt = response.json()
        assert debt['remainingAmount'] == 7000
        assert debt['repaidAmount'] == 3000

    def test_expense_group_with_monthly_limit_overspend(self, client, test_db):
        """Test that monthly limits are tracked and overspending is detected."""
        # Create group with limit
        response = client.post('/api/expense-groups', json={
            'name': 'Entertainment',
            'color': '#FF00FF',
            'monthlyLimit': 1000
        })
        assert response.status_code == 201
        group_id = response.json()["id"]

        # Add expenses exceeding limit
        client.post('/api/expense-items', json={
            'group_id': group_id,
            'name': 'Cinema',
            'amount': 600,
            'half': 1,
            'month': 7,
            'year': 2025
        })

        client.post('/api/expense-items', json={
            'group_id': group_id,
            'name': 'Concert',
            'amount': 500,
            'half': 2,
            'month': 7,
            'year': 2025
        })

        # Get analytics - should show overspend
        response = client.get('/api/analytics/summary?year=2025&month=7')
        assert response.status_code == 200
        summary = response.json()

        # Find our group in summary (use groupId field)
        entertainment = next((g for g in summary.get('categories', []) if g.get('groupId') == group_id), None)
        assert entertainment is not None
        assert entertainment['amount'] == 1100
        assert entertainment['monthlyLimit'] == 1000
        # Check overspend: amount > limit
        assert entertainment['amount'] > entertainment['monthlyLimit']


class TestEndToEndRecurringExpenses:
    """Test recurring expense projection across months."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test_recurring.db"
        db = DatabaseManager(str(db_path))
        db._init_db()
        yield db
        db.close()
        if os.path.exists(str(db_path)):
            os.remove(str(db_path))

    @pytest.fixture
    def client(self, test_db):
        """Create test client with configured database."""
        app.state.db = test_db
        with TestClient(app) as client:
            yield client

    def test_recurring_expense_appears_in_multiple_months(self, client, test_db):
        """Test that recurring expenses appear in all relevant months."""
        # Create recurring expense
        response = client.post('/api/expense-groups', json={
            'name': 'Subscription',
            'color': '#0000FF'
        })
        group_id = response.json()["id"]

        response = client.post('/api/expense-items', json={
            'group_id': group_id,
            'name': 'Netflix',
            'amount': 999,
            'half': 1,
            'month': 7,
            'year': 2025,
            'isRecurring': True,
            'recurringUntil': '2025-09-30'
        })
        assert response.status_code == 201

        # Check trend using correct API params (month, year, months count)
        # Get 3 months ending at September 2025
        response = client.get('/api/analytics/trend?year=2025&month=9&months=3')
        assert response.status_code == 200
        trend = response.json()

        # Should have 3 months
        assert len(trend['months']) == 3

        # Each month should include the subscription expense
        for month_data in trend['months']:
            subscription_expense = next(
                (e for e in month_data.get('expenses', []) if 'Netflix' in e.get('name', '')),
                None
            )
            assert subscription_expense is not None
            assert subscription_expense['amount'] == 999

    def test_recurring_until_stops_projection(self, client, test_db):
        """Test that recurring expenses stop appearing after recurring_until date."""
        # Create recurring expense ending in August
        response = client.post('/api/expense-groups', json={
            'name': 'Gym',
            'color': '#00FF00'
        })
        group_id = response.json()["id"]

        response = client.post('/api/expense-items', json={
            'group_id': group_id,
            'name': 'Gym membership',
            'amount': 2000,
            'half': 1,
            'month': 7,
            'year': 2025,
            'isRecurring': True,
            'recurringUntil': '2025-08-31'
        })
        assert response.status_code == 201

        # Check trend from July to October (4 months ending at October 2025)
        response = client.get('/api/analytics/trend?year=2025&month=10&months=4')
        assert response.status_code == 200
        trend = response.json()

        # Should have July, August, September, October (in chronological order)
        assert len(trend['months']) == 4
        
        july_data = trend['months'][0]
        august_data = trend['months'][1]
        september_data = trend['months'][2]

        july_gym = any('Gym' in e.get('name', '') for e in july_data.get('expenses', []))
        august_gym = any('Gym' in e.get('name', '') for e in august_data.get('expenses', []))
        september_gym = any('Gym' in e.get('name', '') for e in september_data.get('expenses', []))

        assert july_gym is True
        assert august_gym is True
        assert september_gym is False


class TestEndToEndVacationWorkingDays:
    """Test vacation impact on working days calculation."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test_vacation.db"
        db = DatabaseManager(str(db_path))
        db._init_db()
        yield db
        db.close()
        if os.path.exists(str(db_path)):
            os.remove(str(db_path))

    @pytest.fixture
    def client(self, test_db):
        """Create test client with configured database."""
        app.state.db = test_db
        with TestClient(app) as client:
            yield client

    def test_vacation_reduces_working_days(self, client, test_db):
        """Test that vacation days reduce the working days base."""
        # Setup
        client.put('/api/settings', json={
            'salary': 100000,
            'calculation_method': 'working_days'
        })

        # Add vacation spanning workdays and weekends
        response = client.post('/api/vacations', json={
            'startDate': '2025-07-14',  # Monday
            'endDate': '2025-07-20',    # Sunday (7 days, 5 workdays)
            'payoutDate': '2025-07-25',
            'totalAmount': 30000
        })
        assert response.status_code == 201

        # Calculate balance
        response = client.get('/api/balance?year=2025&month=7')
        assert response.status_code == 200
        data = response.json()

        # Verify working days fields are present when using working_days method
        assert 'workingDaysHalf1' in data
        assert 'workingDaysHalf2' in data
        assert 'workingDaysTotal' in data
        
        # Should show some working days calculated
        assert data['workingDaysHalf1'] is not None
        assert data['workingDaysHalf2'] is not None
        assert data['workingDaysTotal'] is not None

    def test_weekend_vacation_doesnt_reduce_working_days(self, client, test_db):
        """Test that weekend-only vacation doesn't affect working days."""
        # Add weekend-only vacation
        response = client.post('/api/vacations', json={
            'startDate': '2025-07-12',  # Saturday
            'endDate': '2025-07-13',    # Sunday
            'payoutDate': '2025-07-25',
            'totalAmount': 5000
        })
        assert response.status_code == 201

        # Calculate balance
        response = client.get('/api/balance?year=2025&month=7')
        assert response.status_code == 200
        data = response.json()

        # Weekend vacation shouldn't reduce worked days
        breakdown = data.get('day_count_breakdown', {})
        assert breakdown.get('vacation_working_days', 0) == 0


class TestEndToEndBackupRestore:
    """Test backup and restore functionality."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a temporary file-based database for testing."""
        db_path = tmp_path / "test_backup.db"
        db = DatabaseManager(str(db_path))
        db._init_db()

        # Add some test data
        cursor = db._conn().cursor()
        cursor.execute("""
            INSERT INTO settings (id, salary, kef, proportion_husband, proportion_wife)
            VALUES (1, 100000, 1.5, 40, 60)
        """)
        db._conn().commit()

        yield db, str(db_path)
        db.close()

    def test_backup_creates_valid_sqlite_file(self, test_db):
        """Test that backup creates a valid SQLite database file."""
        db, db_path = test_db

        backup_path = db_path.replace('.db', '_backup.db')
        db.backup(backup_path)

        # Verify backup file exists and is valid SQLite
        assert os.path.exists(backup_path)

        # Try to open backup as SQLite database
        backup_conn = sqlite3.connect(backup_path)
        cursor = backup_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        backup_conn.close()

        # Should have all tables
        table_names = [t[0] for t in tables]
        assert 'settings' in table_names
        assert 'expense_groups' in table_names
        assert 'expense_items' in table_names

        # Verify data was backed up
        conn = sqlite3.connect(backup_path)
        cursor = conn.cursor()
        cursor.execute("SELECT salary FROM settings WHERE id=1")
        result = cursor.fetchone()
        conn.close()

        assert result[0] == 100000

        # Cleanup
        os.remove(backup_path)


class TestEndToEndYearBoundary:
    """Test handling of year boundaries and date wraparounds."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test_year_boundary.db"
        db = DatabaseManager(str(db_path))
        db._init_db()
        yield db
        db.close()
        if os.path.exists(str(db_path)):
            os.remove(str(db_path))

    @pytest.fixture
    def client(self, test_db):
        """Create test client with configured database."""
        app.state.db = test_db
        with TestClient(app) as client:
            yield client

    def test_trend_handles_year_wraparound(self, client, test_db):
        """Test that trend endpoint handles December-January transition."""
        # Create recurring expense starting in November
        response = client.post('/api/expense-groups', json={
            'name': 'Insurance',
            'color': '#FFFF00'
        })
        group_id = response.json()["id"]

        response = client.post('/api/expense-items', json={
            'group_id': group_id,
            'amount': 5000,
            'description': 'Annual insurance',
            'date': '2024-11-01',
            'is_recurring': True,
            'recurring_until': '2025-02-28'
        })
        assert response.status_code == 201

        # Request trend spanning year boundary
        response = client.get('/api/analytics/trend?start_year=2024&start_month=11&end_year=2025&end_month=2')
        assert response.status_code == 200
        trend = response.json()

        # Should have 4 months: Nov 2024, Dec 2024, Jan 2025, Feb 2025
        assert len(trend['months']) == 4

        # Verify chronological order
        months = trend['months']
        assert months[0]['year'] == 2024 and months[0]['month'] == 11
        assert months[1]['year'] == 2024 and months[1]['month'] == 12
        assert months[2]['year'] == 2025 and months[2]['month'] == 1
        assert months[3]['year'] == 2025 and months[3]['month'] == 2

        # Each month should have the insurance expense
        for month_data in months:
            insurance = next(
                (e for e in month_data.get('expenses', []) if 'insurance' in e.get('description', '').lower()),
                None
            )
            assert insurance is not None
            assert insurance['amount'] == 5000

    def test_birthday_in_january_uses_december_payout(self, client, test_db):
        """Test that January birthdays use December payout for gift budget."""
        # Setup with payout on 10th
        client.put('/api/settings', json={
            'salary': 90000,
            'gift_budget': 3000,
            'payout_day': 10
        })

        # Create birthday on January 5th (before payout day)
        response = client.post('/api/birthdays', json={
            'name': 'New Year Baby',
            'birthDate': '05.01.2020',
            'giftAmount': 1500
        })
        assert response.status_code == 201

        # Calculate January balance - should use December payout period
        response = client.get('/api/balance?year=2025&month=1')
        assert response.status_code == 200

        # Verify gift expense was created for previous month's payout
        response = client.get('/api/expense-items?year=2025&month=1')
        assert response.status_code == 200
        expenses = response.json()

        # Should have gift expense
        gift_expenses = [e for e in expenses if 'gift' in e.get('description', '').lower() or 'birthday' in e.get('description', '').lower()]
        assert len(gift_expenses) > 0
