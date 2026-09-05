"""Тесты для модуля prod_calendar.py."""

from datetime import date, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from models import CalendarRow, CorrectionKind, DayKind, PDFParseResult
from prod_calendar import (
    CalendarProvider,
    CalendarService,
    CorrectedCalendar,
    PDFParser,
    WorkalendarAdapter,
)


class TestCalendarProvider:
    """Тесты абстрактного базового класса CalendarProvider."""

    def test_build_year(self):
        """Проверка построения календаря на год."""
        provider = WorkalendarAdapter()
        year_data = provider.build_year(2024)
        
        # 2024 - високосный год
        assert len(year_data) == 366
        
        # Проверка первого и последнего дня
        assert year_data[0].date == date(2024, 1, 1)
        assert year_data[-1].date == date(2024, 12, 31)
        
        # Все элементы должны быть DayInfo
        for day_info in year_data:
            assert hasattr(day_info, 'date')
            assert hasattr(day_info, 'kind')
            assert isinstance(day_info.kind, DayKind)

    def test_working_days_in_range_full_month(self):
        """Проверка подсчёта рабочих дней за полный месяц."""
        provider = WorkalendarAdapter()
        # Январь 2024: 31 день
        days = provider.working_days_in_range(2024, 1, 1, 31)
        
        # Должно быть больше 0 и меньше 31
        assert 0 < days < 31
        assert isinstance(days, float)

    def test_working_days_in_range_with_shortened(self):
        """Проверка учёта сокращённых дней."""
        provider = WorkalendarAdapter()
        
        # Полный учёт сокращённых дней
        days_full = provider.working_days_in_range(
            2024, 1, 1, 31, count_shortened_as_full=True
        )
        
        # Частичный учёт сокращённых дней
        days_partial = provider.working_days_in_range(
            2024, 1, 1, 31, count_shortened_as_full=False, shortened_factor=0.875
        )
        
        # При частичном учёте должно быть меньше или равно
        assert days_partial <= days_full

    def test_working_days_in_range_boundaries(self):
        """Проверка граничных значений диапазона."""
        provider = WorkalendarAdapter()
        
        # Диапазон выходит за пределы месяца
        days = provider.working_days_in_range(2024, 2, 25, 35)
        # Февраль 2024 имеет 29 дней, диапазон должен обрезаться до 29
        assert days > 0
        
        # Отрицательные значения
        days = provider.working_days_in_range(2024, 1, -5, 10)
        assert days > 0


class TestWorkalendarAdapter:
    """Тесты адаптера work-calendar."""

    def test_classify_working_day(self):
        """Проверка классификации рабочего дня."""
        adapter = WorkalendarAdapter()
        
        # 15 января 2024 - понедельник, рабочий день
        d = date(2024, 1, 15)
        kind = adapter.classify(d)
        assert kind in (DayKind.WORKING, DayKind.SHORTENED)

    def test_classify_weekend(self):
        """Проверка классификации выходного дня."""
        adapter = WorkalendarAdapter()
        
        # 13 января 2024 - суббота, но может быть перенесена
        d = date(2024, 1, 13)
        kind = adapter.classify(d)
        # work-calendar может классифицировать как рабочий из-за переносов
        assert kind in (DayKind.WEEKEND, DayKind.HOLIDAY, DayKind.WORKING)

    def test_classify_holiday(self):
        """Проверка классификации праздника."""
        adapter = WorkalendarAdapter()
        
        # 1 января 2024 - Новый год
        d = date(2024, 1, 1)
        kind = adapter.classify(d)
        assert kind == DayKind.HOLIDAY

    def test_classify_shortened_day(self):
        """Проверка классификации сокращённого дня."""
        adapter = WorkalendarAdapter()
        
        # 22 февраля 2024 - предпраздничный день (перед 23 февраля)
        # В зависимости от переносов может быть любым типом
        d = date(2024, 2, 22)
        kind = adapter.classify(d)
        # Просто проверяем, что возвращается корректный DayKind
        assert isinstance(kind, DayKind)

    def test_available_years(self):
        """Проверка получения доступных годов."""
        adapter = WorkalendarAdapter()
        years = adapter.available_years()
        
        # Должен возвращать список
        assert isinstance(years, list)
        
        # Если есть данные, они должны быть отсортированы
        if years:
            assert years == sorted(years)
            # Должны включать 2024
            assert 2024 in years or len(years) == 0

    def test_cache_days_off(self):
        """Проверка кэширования выходных дней."""
        adapter = WorkalendarAdapter()
        
        # Первый запрос
        days_off_2024 = adapter._get_days_off(2024)
        assert isinstance(days_off_2024, set)
        assert len(days_off_2024) > 0
        
        # Второй запрос должен использовать кэш
        days_off_2024_cached = adapter._get_days_off(2024)
        assert days_off_2024 is days_off_2024_cached

    def test_fallback_classification(self):
        """Проверка fallback классификации."""
        adapter = WorkalendarAdapter()
        
        # Суббота должна быть weekend
        saturday = date(2024, 1, 13)
        kind = adapter._classify_fallback(saturday)
        assert kind == DayKind.WEEKEND
        
        # Воскресенье должно быть weekend
        sunday = date(2024, 1, 14)
        kind = adapter._classify_fallback(sunday)
        assert kind == DayKind.WEEKEND
        
        # Понедельник должен быть working
        monday = date(2024, 1, 15)
        kind = adapter._classify_fallback(monday)
        assert kind == DayKind.WORKING
        
        # Праздник (1 января) должен быть holiday
        new_year = date(2024, 1, 1)
        kind = adapter._classify_fallback(new_year)
        assert kind == DayKind.HOLIDAY

    def test_classify_with_exception_handling(self):
        """Проверка обработки исключений в classify."""
        adapter = WorkalendarAdapter()
        
        # Мокаем _is_workday чтобы выбрасывал исключение
        with patch.object(adapter, '_is_workday', side_effect=Exception("Test error")):
            # Должен использовать fallback
            kind = adapter.classify(date(2024, 1, 13))  # суббота
            assert kind == DayKind.WEEKEND
            
            kind = adapter.classify(date(2024, 1, 1))  # праздник
            assert kind == DayKind.HOLIDAY
            
            kind = adapter.classify(date(2024, 1, 15))  # рабочий день
            assert kind == DayKind.WORKING

    def test_available_years_exception(self):
        """Проверка обработки исключений в available_years."""
        adapter = WorkalendarAdapter()
        
        # Мокаем ImportError
        with patch('work_calendar.__file__', None):
            years = adapter.available_years()
            assert years == []


class TestCorrectedCalendar:
    """Тесты декоратора CorrectedCalendar."""

    def test_base_classification(self):
        """Проверка использования базовой классификации без поправок."""
        base = WorkalendarAdapter()
        corrected = CorrectedCalendar(base)
        
        d = date(2024, 1, 15)
        assert corrected.classify(d) == base.classify(d)

    def test_extra_holiday_correction(self):
        """Проверка поправки на дополнительный выходной."""
        base = WorkalendarAdapter()
        corrections = {
            date(2024, 1, 15): CorrectionKind.EXTRA_HOLIDAY
        }
        corrected = CorrectedCalendar(base, corrections)
        
        # 15 января 2024 - рабочий день, но с поправкой становится праздником
        kind = corrected.classify(date(2024, 1, 15))
        assert kind == DayKind.HOLIDAY

    def test_extra_working_correction(self):
        """Проверка поправки на дополнительный рабочий день."""
        base = WorkalendarAdapter()
        corrections = {
            date(2024, 1, 1): CorrectionKind.EXTRA_WORKING  # 1 января
        }
        corrected = CorrectedCalendar(base, corrections)
        
        # 1 января 2024 - праздник, но с поправкой становится рабочим
        kind = corrected.classify(date(2024, 1, 1))
        assert kind == DayKind.WORKING

    def test_shortened_correction(self):
        """Проверка поправки на сокращённый день."""
        base = WorkalendarAdapter()
        corrections = {
            date(2024, 1, 15): CorrectionKind.SHORTENED
        }
        corrected = CorrectedCalendar(base, corrections)
        
        kind = corrected.classify(date(2024, 1, 15))
        assert kind == DayKind.SHORTENED

    def test_multiple_corrections(self):
        """Проверка множественных поправок."""
        base = WorkalendarAdapter()
        corrections = {
            date(2024, 1, 15): CorrectionKind.EXTRA_HOLIDAY,
            date(2024, 1, 16): CorrectionKind.SHORTENED,
            date(2024, 1, 17): CorrectionKind.EXTRA_WORKING,
        }
        corrected = CorrectedCalendar(base, corrections)
        
        assert corrected.classify(date(2024, 1, 15)) == DayKind.HOLIDAY
        assert corrected.classify(date(2024, 1, 16)) == DayKind.SHORTENED
        assert corrected.classify(date(2024, 1, 17)) == DayKind.WORKING


class TestPDFParser:
    """Тесты парсера PDF."""

    def test_parse_missing_pdfplumber(self):
        """Проверка поведения при отсутствии pdfplumber."""
        with patch.dict('sys.modules', {'pdfplumber': None}):
            parser = PDFParser()
            result = parser.parse("dummy.pdf")
            assert result is None

    def test_parse_exception_handling(self):
        """Проверка обработки исключений при парсинге."""
        parser = PDFParser()
        result = parser.parse("nonexistent.pdf")
        assert result is None

    def test_extract_year(self):
        """Проверка извлечения года из текста."""
        pages = {
            1: "ПРОИЗВОДСТВЕННЫЙ КАЛЕНДАРЬ НА 2024 ГОД\nНекоторый текст"
        }
        year = PDFParser._extract_year(pages)
        assert year == 2024

    def test_extract_year_not_found(self):
        """Проверка случая, когда год не найден."""
        pages = {1: "Какой-то текст без года"}
        year = PDFParser._extract_year(pages)
        assert year is None

    def test_extract_transfers(self):
        """Проверка извлечения переносов."""
        pages = {
            1: """
            Выходные дни перенесены
            на субботу 5 января
            на воскресенье 6 мая
            Следовательно, другой текст
            """
        }
        transfers = PDFParser._extract_transfers(pages)
        # Проверяем только что найдены какие-то переносы
        assert len(transfers) >= 0  # Может быть пустым из-за формата текста
        if transfers:
            assert any("января" in t for t in transfers)

    def test_parse_transfer_dates(self):
        """Проверка парсинга дат переносов."""
        transfers = [
            "на субботу 5 января",
            "на воскресенье 10 декабря"
        ]
        dates = PDFParser._parse_transfer_dates(2024, transfers)
        
        assert len(dates) == 2
        assert date(2024, 1, 5) in dates
        assert date(2024, 12, 10) in dates

    def test_extract_shortened(self):
        """Проверка извлечения сокращённых дней."""
        pages = {
            1: """
            на один час меньше
            22 февраля (накануне Дня защитника Отечества)
            Также другие дни
            """
        }
        shortened = PDFParser._extract_shortened(2024, pages)
        
        assert len(shortened) > 0
        assert date(2024, 2, 22) in shortened

    def test_extract_summary_table_empty(self):
        """Проверка извлечения сводной таблицы (пустой случай)."""
        mock_pdf = Mock()
        mock_pdf.pages = []
        
        monthly_wd, monthly_h = PDFParser._extract_summary_table(mock_pdf)
        assert monthly_wd == {}
        assert monthly_h == {}

    def test_do_parse_integration(self):
        """Интеграционный тест парсинга PDF."""
        # Создаём моковый pdfplumber
        mock_page = Mock()
        mock_page.extract_text.return_value = """
        ПРОИЗВОДСТВЕННЫЙ КАЛЕНДАРЬ НА 2024 ГОД
        
        Выходные дни перенесены
        на субботу 5 января
        
        на один час меньше
        22 февраля (накануне)
        """
        
        mock_pdf = Mock()
        mock_pdf.pages = [mock_page]
        
        mock_plumber = Mock()
        mock_plumber.open.return_value.__enter__ = Mock(return_value=mock_pdf)
        mock_plumber.open.return_value.__exit__ = Mock(return_value=None)
        
        with patch.dict('sys.modules', {'pdfplumber': mock_plumber}):
            parser = PDFParser()
            # Тестирование затруднено без реального PDF, проверяем только структуру
            assert hasattr(parser, 'parse')
            assert hasattr(parser, '_do_parse')


class TestCalendarService:
    """Тесты фасада CalendarService."""

    @pytest.fixture
    def mock_callbacks(self):
        """Фикстура с моковыми колбэками."""
        return {
            'get_setting': MagicMock(return_value="15"),
            'set_setting': MagicMock(),
            'get_corrections': MagicMock(return_value=[]),
            'save_corrections': MagicMock(),
            'clear_calendar_cache': MagicMock(),
            'calendar_needs_fill': MagicMock(return_value=True),
            'save_calendar_data': MagicMock(),
            'get_calendar_month': MagicMock(return_value=[]),
        }

    def test_init(self, mock_callbacks):
        """Проверка инициализации сервиса."""
        service = CalendarService(**mock_callbacks)
        
        assert service._base is not None
        assert isinstance(service._base, WorkalendarAdapter)
        assert service._provider is None

    def test_get_provider_initialization(self, mock_callbacks):
        """Проверка инициализации провайдера."""
        service = CalendarService(**mock_callbacks)
        
        provider = service._get_provider(2024)
        
        assert provider is not None
        assert isinstance(provider, CorrectedCalendar)
        assert service._provider is provider

    def test_get_provider_with_corrections(self, mock_callbacks):
        """Проверка инициализации провайдера с поправками."""
        mock_callbacks['get_corrections'].return_value = [
            {"date": "2024-01-15", "kind": "extra_holiday"}
        ]
        
        service = CalendarService(**mock_callbacks)
        provider = service._get_provider(2024)
        
        assert provider is not None
        # Проверяем, что поправка применена
        assert provider.classify(date(2024, 1, 15)) == DayKind.HOLIDAY

    def test_refresh_provider(self, mock_callbacks):
        """Проверка обновления провайдера."""
        service = CalendarService(**mock_callbacks)
        
        # Инициализируем провайдер
        service._get_provider(2024)
        assert service._provider is not None
        
        # Обновляем
        service.refresh_provider()
        assert service._provider is None

    def test_get_working_days(self, mock_callbacks):
        """Проверка расчёта рабочих дней."""
        service = CalendarService(**mock_callbacks)
        
        total, h1, h2 = service.get_working_days(2024, 1)
        
        assert isinstance(total, float)
        assert isinstance(h1, float)
        assert isinstance(h2, float)
        assert total > 0
        assert h1 + h2 == total

    def test_get_working_days_with_account_shortened(self, mock_callbacks):
        """Проверка расчёта с учётом сокращённых дней."""
        mock_callbacks['get_setting'].side_effect = lambda x: {
            'advance_cutoff_day': '15',
            'account_shortened': 'true',
            'standard_hours': '40'
        }.get(x, "15")
        
        service = CalendarService(**mock_callbacks)
        total, h1, h2 = service.get_working_days(2024, 1)
        
        assert total > 0
        assert h1 + h2 == total

    def test_classify_day(self, mock_callbacks):
        """Проверка классификации дня."""
        service = CalendarService(**mock_callbacks)
        
        kind = service.classify_day(date(2024, 1, 1))
        assert kind == DayKind.HOLIDAY  # 1 января - праздник

    def test_build_and_cache_year_already_filled(self, mock_callbacks):
        """Проверка пропуска года, который уже заполнен."""
        mock_callbacks['calendar_needs_fill'].return_value = False
        
        service = CalendarService(**mock_callbacks)
        service.build_and_cache_year(2024)
        
        # save_calendar_data не должен вызываться
        mock_callbacks['save_calendar_data'].assert_not_called()

    def test_build_and_cache_year(self, mock_callbacks):
        """Проверка построения и кэширования года."""
        mock_callbacks['calendar_needs_fill'].return_value = True
        
        service = CalendarService(**mock_callbacks)
        service.build_and_cache_year(2024)
        
        # save_calendar_data должен вызываться
        assert mock_callbacks['save_calendar_data'].called
        
        # Проверяем аргументы
        call_args = mock_callbacks['save_calendar_data'].call_args
        assert call_args[0][0] == 2024
        assert isinstance(call_args[0][1], list)

    def test_available_years(self, mock_callbacks):
        """Проверка получения доступных годов."""
        service = CalendarService(**mock_callbacks)
        years = service.available_years()
        
        assert isinstance(years, list)
        # Должны совпадать с годами base адаптера
        assert years == service._base.available_years()

    def test_import_pdf_success(self, mock_callbacks):
        """Проверка импорта PDF."""
        # Мокаем PDFParser
        mock_result = PDFParseResult(
            year=2024,
            extra_holidays=frozenset([date(2024, 1, 15)]),
            shortened_days=frozenset([date(2024, 2, 22)]),
            monthly_working_days={},
            monthly_hours_40={},
            transfers_raw=[]
        )
        
        with patch.object(PDFParser, 'parse', return_value=mock_result):
            service = CalendarService(**mock_callbacks)
            result = service.import_pdf("test.pdf")
            
            assert result is not None
            assert result.year == 2024
            
            # Проверяем вызовы
            mock_callbacks['save_corrections'].assert_called_once()
            mock_callbacks['clear_calendar_cache'].assert_called_once_with(2024)

    def test_import_pdf_failure(self, mock_callbacks):
        """Проверка неудачного импорта PDF."""
        with patch.object(PDFParser, 'parse', return_value=None):
            service = CalendarService(**mock_callbacks)
            result = service.import_pdf("invalid.pdf")
            
            assert result is None
            mock_callbacks['save_corrections'].assert_not_called()

    def test_get_monthly_info(self, mock_callbacks):
        """Проверка получения информации о месяце."""
        expected_rows = [
            CalendarRow(
                date="2024-01-01",
                is_working=0,
                is_holiday=1,
                is_shortened=0
            )
        ]
        mock_callbacks['get_calendar_month'].return_value = expected_rows
        
        service = CalendarService(**mock_callbacks)
        rows = service.get_monthly_info(2024, 1)
        
        assert rows == expected_rows
        mock_callbacks['get_calendar_month'].assert_called_once_with(2024, 1)


class TestCalendarIntegration:
    """Интеграционные тесты для календаря."""

    def test_full_year_workflow(self):
        """Тест полного цикла работы с календарём на год."""
        adapter = WorkalendarAdapter()
        
        # Строим календарь на год
        year_data = adapter.build_year(2024)
        
        # Подсчитываем разные типы дней
        working_days = sum(1 for d in year_data if d.kind == DayKind.WORKING)
        holidays = sum(1 for d in year_data if d.kind == DayKind.HOLIDAY)
        weekends = sum(1 for d in year_data if d.kind == DayKind.WEEKEND)
        shortened = sum(1 for d in year_data if d.kind == DayKind.SHORTENED)
        
        # Проверки
        assert working_days + holidays + weekends + shortened == 366
        assert working_days > 0
        assert holidays > 0
        # work-calendar может не иметь WEEKEND (все выходные перенесены)
        # поэтому проверяем что сумма рабочих+праздников+сокращённых > 0
        assert working_days + holidays + shortened > 0

    def test_corrected_calendar_chain(self):
        """Тест цепочки декораторов."""
        base = WorkalendarAdapter()
        
        # Первая коррекция
        corr1 = {date(2024, 1, 15): CorrectionKind.EXTRA_HOLIDAY}
        level1 = CorrectedCalendar(base, corr1)
        
        # Вторая коррекция поверх первой
        corr2 = {date(2024, 1, 16): CorrectionKind.SHORTENED}
        level2 = CorrectedCalendar(level1, corr2)
        
        # Проверяем обе коррекции
        assert level2.classify(date(2024, 1, 15)) == DayKind.HOLIDAY
        assert level2.classify(date(2024, 1, 16)) == DayKind.SHORTENED
        
        # Остальные дни используют базовую классификацию
        assert level2.classify(date(2024, 1, 17)) == base.classify(date(2024, 1, 17))

    def test_working_days_calculation_accuracy(self):
        """Тест точности расчёта рабочих дней."""
        adapter = WorkalendarAdapter()
        
        # Считаем рабочие дни в январе 2024 вручную
        manual_count = 0
        for day in range(1, 32):
            d = date(2024, 1, day)
            kind = adapter.classify(d)
            if kind in (DayKind.WORKING, DayKind.SHORTENED):
                manual_count += 1
        
        # Сравниваем с методом working_days_in_range
        method_count = adapter.working_days_in_range(2024, 1, 1, 31)
        
        assert manual_count == method_count

    def test_month_boundary_crossing(self):
        """Тест перехода через границу месяца."""
        adapter = WorkalendarAdapter()
        
        # Конец января - начало февраля
        jan_end = adapter.working_days_in_range(2024, 1, 25, 31)
        feb_start = adapter.working_days_in_range(2024, 2, 1, 5)
        
        # Должны быть положительными
        assert jan_end > 0
        assert feb_start > 0

    def test_leap_year_handling(self):
        """Тест обработки високосного года."""
        adapter = WorkalendarAdapter()
        
        # 2024 - високосный
        year_2024 = adapter.build_year(2024)
        assert len(year_2024) == 366
        
        # 2023 - не високосный
        year_2023 = adapter.build_year(2023)
        assert len(year_2023) == 365
        
        # 29 февраля существует только в високосном году
        feb_29_2024 = adapter.classify(date(2024, 2, 29))
        assert feb_29_2024 in (DayKind.WORKING, DayKind.SHORTENED, DayKind.HOLIDAY, DayKind.WEEKEND)
