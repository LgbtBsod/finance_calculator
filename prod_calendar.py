"""prod_calendar.py — Производственный календарь РФ.

Архитектура (Strategy + Decorator):
  CalendarProvider (ABC)        — интерфейс + общая реализация
  └─ WorkalendarAdapter        — main: данные с consultant.ru (библиотека work-calendar)
  └─ CorrectedCalendar         — декоратор: ручные поправки поверх

PDFParser                     — опциональный парсер PDF (для верификации / доп. годов)
CalendarService               — фасад: собирает провайдера, кэширует в БД
"""

from __future__ import annotations

import calendar as cal_lib
import json
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

from config import (
    MONTH_NAMES_GENITIVE,
    MONTH_NAMES_NOMINATIVE,
    RU_BASE_HOLIDAYS,
)
from models import (
    CalendarRow,
    CorrectionKind,
    CorrectionRow,
    DayInfo,
    DayKind,
    PDFParseResult,
)

logger = logging.getLogger(__name__)

__all__ = [
    "CalendarProvider",
    "WorkalendarAdapter",
    "CorrectedCalendar",
    "PDFParser",
    "CalendarService",
]


# ═══════════════════════════════════════════════════════════════
#  CalendarProvider — интерфейс + общая реализация
# ═══════════════════════════════════════════════════════════════


class CalendarProvider(ABC):
    """Протокол поставщика данных о производственном календаре.

    Подклассы обязаны реализовать только classify().
    build_year() и working_days_in_range() имеют общую реализацию
    на основе classify().
    """

    @abstractmethod
    def classify(self, d: date) -> DayKind:
        """Вернуть тип дня."""

    def build_year(self, year: int) -> list[DayInfo]:
        """Построить полный календарь на год."""
        result: list[DayInfo] = []
        for m in range(1, 13):
            _, dim = cal_lib.monthrange(year, m)
            for day in range(1, dim + 1):
                d = date(year, m, day)
                result.append(DayInfo(date=d, kind=self.classify(d)))
        return result

    def working_days_in_range(
        self,
        year: int,
        month: int,
        day_start: int,
        day_end: int,
        *,
        count_shortened_as_full: bool = True,
        shortened_factor: float = 0.875,
    ) -> float:
        """Рабочие дни в диапазоне [day_start, day_end]."""
        total = 0.0
        _, dim = cal_lib.monthrange(year, month)
        lo = max(day_start, 1)
        hi = min(day_end, dim)
        for day in range(lo, hi + 1):
            d = date(year, month, day)
            k = self.classify(d)
            if k in (DayKind.WORKING, DayKind.SHORTENED):
                if count_shortened_as_full:
                    total += 1.0
                else:
                    total += (
                        shortened_factor
                        if k == DayKind.SHORTENED
                        else 1.0
                    )
        return total


# ═══════════════════════════════════════════════════════════════
#  WorkalendarAdapter — данные с consultant.ru
# ═══════════════════════════════════════════════════════════════


class WorkalendarAdapter(CalendarProvider):
    """Обёртка над библиотекой work-calendar.

    Данные получены с consultant.ru — включают ВСЕ правительственные
    переносы выходных дней. Покрывает 2021-2027.

    Предпраздничные (сокращённые) дни определяются автоматически:
    если завтра — выходной/праздник, а сегодня — рабочий -> shortened.
    """

    def __init__(self) -> None:
        import work_calendar as _wc

        self._is_workday = _wc.is_workday
        self._days_off_cache: dict[int, set[date]] = {}

    def _get_days_off(self, year: int) -> set[date]:
        """Кэшируем множество выходных дней для года."""
        if year not in self._days_off_cache:
            days_off: set[date] = set()
            for m in range(1, 13):
                _, mdim = cal_lib.monthrange(year, m)
                for d in range(1, mdim + 1):
                    dt = date(year, m, d)
                    try:
                        if not self._is_workday(dt):
                            days_off.add(dt)
                    except Exception:
                        logger.warning(
                            "work-calendar: нет данных для %s",
                            dt,
                        )
            self._days_off_cache[year] = days_off
        return self._days_off_cache[year]

    def classify(self, d: date) -> DayKind:
        try:
            is_work = self._is_workday(d)
        except Exception:
            logger.warning("work-calendar: fallback для %s", d)
            return self._classify_fallback(d)

        if is_work:
            tomorrow = d + timedelta(days=1)
            try:
                if not self._is_workday(tomorrow):
                    return DayKind.SHORTENED
            except Exception:
                pass
            return DayKind.WORKING
        return DayKind.HOLIDAY

    def _classify_fallback(self, d: date) -> DayKind:
        """Fallback: базовые праздники РФ + выходные."""
        if (d.month, d.day) in RU_BASE_HOLIDAYS:
            return DayKind.HOLIDAY
        if d.weekday() >= 5:
            return DayKind.WEEKEND
        return DayKind.WORKING

    def available_years(self) -> list[int]:
        """Какие годы есть в данных work-calendar."""
        try:
            import work_calendar as _wc

            data_path = Path(_wc.__file__).parent / "total.json"
            with open(data_path) as f:
                data = json.load(f)
            return sorted(int(k) for k in data if k.isdigit())
        except Exception:
            logger.warning(
                "Не удалось получить список доступных годов из work-calendar"
            )
            return []


# ═══════════════════════════════════════════════════════════════
#  CorrectedCalendar — декоратор с ручными поправками
# ═══════════════════════════════════════════════════════════════


class CorrectedCalendar(CalendarProvider):
    """Декоратор: накладывает поверх base-провайдера набор поправок.

    Поправки хранятся как словарь {date -> CorrectionKind}.
    Нужны только для ручных корректировок или годов, не покрытых work-calendar.
    """

    def __init__(
        self,
        base: CalendarProvider,
        corrections: dict[date, CorrectionKind] | None = None,
    ) -> None:
        self._base = base
        self._corr = corrections or {}

    def classify(self, d: date) -> DayKind:
        if d in self._corr:
            match self._corr[d]:
                case CorrectionKind.EXTRA_HOLIDAY:
                    return DayKind.HOLIDAY
                case CorrectionKind.EXTRA_WORKING:
                    return DayKind.WORKING
                case CorrectionKind.SHORTENED:
                    return DayKind.SHORTENED
        return self._base.classify(d)


# ═══════════════════════════════════════════════════════════════
#  PDFParser — опциональный парсер PDF (верификация / доп. годы)
# ═══════════════════════════════════════════════════════════════


class PDFParser:
    """Парсит PDF производственного календаря с consultant.ru.

    Опциональный инструмент — нужен только если:
      - Год не покрыт work-calendar (до 2021 или после 2027)
      - Нужна верификация данных
      - Требуется точная таблица рабочих часов

    Требует: pip install pdfplumber
    """

    # ── pre-compiled regex (class-level, компилируются один раз) ──
    _RE_TRANSFER = re.compile(
        r"на\s+"
        r"(?:понедельник|вторник|среду|четверг|пятницу|субботу|воскресенье)"
        r"\s+(\d{1,2})\s+"
        r"(января|февраля|марта|апреля|мая|июня|июля|августа|"
        r"сентября|октября|ноября|декабря)",
        re.IGNORECASE,
    )
    _RE_SHORTENED = re.compile(
        r"(\d{1,2})\s+"
        r"(января|февраля|марта|апреля|мая|июня|июля|августа|"
        r"сентября|октября|ноября|декабря)",
        re.IGNORECASE,
    )
    _RE_YEAR = re.compile(
        r"ПРОИЗВОДСТВЕННЫЙ\s+КАЛЕНДАРЬ\s+НА\s+(\d{4})\s+ГОД",
        re.IGNORECASE,
    )

    def parse(self, pdf_path: str | Path) -> PDFParseResult | None:
        try:
            import pdfplumber
        except ImportError:
            return None

        try:
            return self._do_parse(pdfplumber, str(pdf_path))
        except Exception:
            logger.warning(
                "Ошибка при парсинге PDF: %s", pdf_path, exc_info=True
            )
            return None

    def _do_parse(self, pdfplumber: object, pdf_path: str) -> PDFParseResult | None:
        """Реализация парсинга (выделена для тестируемости)."""
        with pdfplumber.open(pdf_path) as pdf:  # type: ignore[operator]
            pages_text: dict[int, str] = {}
            for i, page in enumerate(pdf.pages):
                pages_text[i + 1] = page.extract_text() or ""

            # Год
            year = self._extract_year(pages_text)
            if year is None:
                return None

            # Переносы
            transfers_raw = self._extract_transfers(pages_text)
            extra_holidays = self._parse_transfer_dates(
                year, transfers_raw
            )

            # Сокращённые дни
            shortened = self._extract_shortened(year, pages_text)

            # Сводная таблица
            monthly_wd, monthly_h = self._extract_summary_table(pdf)

            return PDFParseResult(
                year=year,
                extra_holidays=frozenset(extra_holidays),
                shortened_days=frozenset(shortened),
                monthly_working_days=monthly_wd,
                monthly_hours_40=monthly_h,
                transfers_raw=transfers_raw,
            )

    # ── приватные шаги парсинга ──────────────────────────────

    @classmethod
    def _extract_year(cls, pages: dict[int, str]) -> int | None:
        for text in pages.values():
            m = cls._RE_YEAR.search(text)
            if m:
                return int(m.group(1))
        return None

    @classmethod
    def _extract_transfers(cls, pages: dict[int, str]) -> list[str]:
        """Извлекает строки с переносами из PDF."""
        transfers_raw: list[str] = []
        in_block = False
        for text in pages.values():
            for line in text.split("\n"):
                stripped = line.strip()
                if "перенесены" in stripped:
                    in_block = True
                    continue
                if in_block:
                    if stripped.startswith("Следовательно") or stripped.startswith(
                        "Дополнительно"
                    ):
                        in_block = False
                        continue
                    if stripped.endswith("дней:") or stripped.endswith("дни:"):
                        continue
                    if ("на" in stripped and "января" in stripped) or "декабря" in stripped:
                        transfers_raw.append(stripped)
                    elif re.search(r"на\s+\d", stripped):
                        transfers_raw.append(stripped)
        return transfers_raw

    @classmethod
    def _parse_transfer_dates(
        cls, year: int, transfers: list[str]
    ) -> list[date]:
        """Парсит даты переносов из строк."""
        extra_holidays: list[date] = []
        for line in transfers:
            for m in cls._RE_TRANSFER.finditer(line):
                day = int(m.group(1))
                month = MONTH_NAMES_GENITIVE.get(m.group(2).lower())
                if month:
                    try:
                        extra_holidays.append(date(year, month, day))
                    except ValueError:
                        pass
        return extra_holidays

    @classmethod
    def _extract_shortened(
        cls, year: int, pages: dict[int, str]
    ) -> list[date]:
        """Извлекает сокращённые дни."""
        shortened: list[date] = []
        for text in pages.values():
            lower = text.lower()
            idx = lower.find("на один час меньше")
            if idx < 0:
                continue
            fragment = text[idx:]
            paren = fragment.find("(накануне")
            if paren > 0:
                fragment = fragment[:paren]
            period = fragment.find(". Также")
            if period > 0:
                fragment = fragment[:period]
            for m in cls._RE_SHORTENED.finditer(fragment):
                day = int(m.group(1))
                month = MONTH_NAMES_GENITIVE.get(m.group(2).lower())
                if month:
                    try:
                        shortened.append(date(year, month, day))
                    except ValueError:
                        pass
        return shortened

    @classmethod
    def _extract_summary_table(
        cls, pdf: object,
    ) -> tuple[dict[int, int], dict[int, float]]:
        """Извлекает сводную таблицу рабочих дней/часов."""
        monthly_wd: dict[int, int] = {}
        monthly_h: dict[int, float] = {}
        pages = getattr(pdf, "pages", [])
        if len(pages) < 2:
            return monthly_wd, monthly_h

        tables = pages[1].extract_tables()  # type: ignore[union-attr]
        month_map = {
            name.lower(): num
            for name, num in MONTH_NAMES_NOMINATIVE.items()
        }
        for table in tables:
            for row in table:
                if not row or not row[0]:
                    continue
                mn = row[0].strip().split("\n")[0].strip().lower()
                month_num = month_map.get(mn)
                if month_num is None:
                    continue
                try:
                    if row[2]:
                        monthly_wd[month_num] = int(
                            row[2].strip()
                            .replace("\n", "")
                            .replace(" ", "")
                        )
                    if row[4]:
                        val = (
                            row[4].strip()
                            .replace("\n", "")
                            .replace(" ", "")
                            .replace(",", ".")
                        )
                        monthly_h[month_num] = float(val)
                except (ValueError, IndexError):
                    pass
        return monthly_wd, monthly_h


# ═══════════════════════════════════════════════════════════════
#  CalendarService — фасад
# ═══════════════════════════════════════════════════════════════


class CalendarService:
    """Фасад: собирает провайдера, кэширует в БД.

    Жизненный цикл:
      1. Создаётся WorkalendarAdapter (данные с consultant.ru).
      2. Из БД читаются corrections -> CorrectedCalendar.
      3. build_year() кэшируется в таблицу calendar_data.
      4. PDF-загрузка -> parse -> сохранить corrections -> пересбросить кэш.
    """

    def __init__(
        self,
        get_setting: Callable[[str], str],
        set_setting: Callable[[str, str], None],
        get_corrections: Callable[[], list[CorrectionRow]],
        save_corrections: Callable[[int, list[tuple]], None],
        clear_calendar_cache: Callable[[int], None],
        calendar_needs_fill: Callable[[int], bool],
        save_calendar_data: Callable[[int, list[tuple]], None],
        get_calendar_month: Callable[[int, int], list[CalendarRow]],
    ) -> None:
        self._get_setting = get_setting
        self._set_setting = set_setting
        self._get_corrections = get_corrections
        self._save_corrections = save_corrections
        self._clear_calendar_cache = clear_calendar_cache
        self._calendar_needs_fill = calendar_needs_fill
        self._save_calendar_data = save_calendar_data
        self._get_calendar_month = get_calendar_month

        self._base = WorkalendarAdapter()
        self._provider: CorrectedCalendar | None = None

    def _get_provider(self, year: int) -> CorrectedCalendar:
        if self._provider is None:
            corr_dict: dict[date, CorrectionKind] = {}
            for c in self._get_corrections():
                try:
                    d = date.fromisoformat(c["date"])
                    corr_dict[d] = CorrectionKind(c["kind"])
                except (ValueError, KeyError):
                    pass
            self._provider = CorrectedCalendar(self._base, corr_dict)
        return self._provider

    def refresh_provider(self) -> None:
        self._provider = None

    # ── публичный API ─────────────────────────────────────────

    def get_working_days(
        self, year: int, month: int
    ) -> tuple[float, float, float]:
        """(total, half_1, half_2) с учётом настройки сокращённых дней."""
        provider = self._get_provider(year)
        cutoff = int(self._get_setting("advance_cutoff_day") or 15)
        account_short = self._get_setting("account_shortened") == "1"
        std_hours = float(self._get_setting("standard_hours") or 40)
        factor = (
            max(0.0, (std_hours / 5 - 1) / (std_hours / 5))
            if std_hours > 0
            else 0.875
        )

        _, dim = cal_lib.monthrange(year, month)
        total = provider.working_days_in_range(
            year, month, 1, dim,
            count_shortened_as_full=not account_short,
            shortened_factor=factor,
        )
        h1 = provider.working_days_in_range(
            year, month, 1, cutoff,
            count_shortened_as_full=not account_short,
            shortened_factor=factor,
        )
        h2 = provider.working_days_in_range(
            year, month, cutoff + 1, dim,
            count_shortened_as_full=not account_short,
            shortened_factor=factor,
        )
        return total, h1, h2

    def classify_day(self, d: date) -> DayKind:
        return self._get_provider(d.year).classify(d)

    def build_and_cache_year(self, year: int) -> None:
        """Построить и сохранить календарь в БД."""
        if not self._calendar_needs_fill(year):
            return
        provider = self._get_provider(year)
        days = provider.build_year(year)
        rows = []
        for di in days:
            is_working = di.kind in (DayKind.WORKING, DayKind.SHORTENED)
            is_holiday = di.kind == DayKind.HOLIDAY
            is_short = di.kind == DayKind.SHORTENED
            rows.append((
                di.date.isoformat(),
                int(is_working),
                int(is_holiday),
                int(is_short),
            ))
        self._save_calendar_data(year, rows)

    def available_years(self) -> list[int]:
        """Годы, покрытые данными work-calendar."""
        return self._base.available_years()

    # ── загрузка PDF (опционально) ────────────────────────────

    def import_pdf(self, pdf_path: str | Path) -> PDFParseResult | None:
        """Парсит PDF и сохраняет corrections в БД."""
        result = PDFParser().parse(pdf_path)
        if result is None:
            return None

        correction_rows: list[tuple[str, str, str]] = []
        for d in result.extra_holidays:
            correction_rows.append(
                (d.isoformat(), CorrectionKind.EXTRA_HOLIDAY, "pdf")
            )
        for d in result.shortened_days:
            correction_rows.append(
                (d.isoformat(), CorrectionKind.SHORTENED, "pdf")
            )
        self._save_corrections(result.year, correction_rows)

        self._clear_calendar_cache(result.year)
        self.refresh_provider()
        return result

    def get_monthly_info(self, year: int, month: int) -> list[CalendarRow]:
        return self._get_calendar_month(year, month)
