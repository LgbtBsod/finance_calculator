"""views/sidebar.py — Боковая панель: настройки ЗП, календаря, период, PDF.

Единственная ответственность — рендеринг и обработка sidebar.
"""

from __future__ import annotations

import streamlit as st
from datetime import date

from config import DB_FILENAME, MONTH_DISPLAY, UPLOAD_DIR
from database import DatabaseManager
from prod_calendar import CalendarService

from .common import KIND_LABELS

__all__ = ["render_sidebar"]


def render_sidebar(
    db: DatabaseManager,
    cal_svc: CalendarService,
) -> tuple[int, int]:
    """Отрисовать sidebar. Возвращает (selected_month, selected_year)."""
    with st.sidebar:
        st.title("⚙️ Настройки")

        s_base = _salary_settings(db)
        _calendar_settings(db)

        st.divider()
        sel_month, sel_year = _period_selector(db)

        st.divider()
        _calendar_source(cal_svc, db, sel_year)

        st.divider()
        _save_button(db, cal_svc, s_base, sel_year)

    return sel_month, sel_year


# ── Зарплатные настройки ────────────────────────────────────


def _salary_settings(db: DatabaseManager) -> float:
    st.subheader("Зарплата")
    s_base = st.number_input(
        "Оклад (₽)",
        min_value=0.0,
        value=float(db.get_setting("base_salary") or 100000),
        step=1000.0,
        format="%g",
    )
    st.number_input(
        "НДФЛ (%)",
        min_value=0.0,
        max_value=99.0,
        value=float(db.get_setting("tax_rate") or 13),
        step=0.5,
        format="%g",
        key="s_tax",
    )
    st.number_input(
        "КЭФ",
        min_value=0.0,
        value=float(db.get_setting("kef") or 1.0),
        step=0.01,
        format="%g",
        key="s_kef",
    )
    st.number_input(
        "День отсечки аванса",
        min_value=1,
        max_value=28,
        value=int(db.get_setting("advance_cutoff_day") or 15),
        step=1,
        format="%d",
        key="s_cutoff",
    )
    return s_base


# ── Настройки календаря ─────────────────────────────────────


def _calendar_settings(db: DatabaseManager) -> None:
    st.subheader("Календарь")
    st.toggle(
        "Учитывать сокращённые дни",
        value=db.get_setting("account_shortened") == "1",
        help="Если включено, предпраздничные дни считаются как "
        "(часов-1)/часов от полного дня. По умолчанию — как обычные.",
        key="s_short",
    )
    st.number_input(
        "Норма часов в неделю",
        min_value=1,
        max_value=60,
        value=int(float(db.get_setting("standard_hours") or 40)),
        step=1,
        format="%d",
        help="Используется для расчёта коэффициента сокращённого дня.",
        key="s_hours",
    )


# ── Выбор периода ───────────────────────────────────────────


def _period_selector(db: DatabaseManager) -> tuple[int, int]:
    st.subheader("Период")
    current_year = int(db.get_setting("current_year") or date.today().year)
    sel_month = st.selectbox(
        "Месяц",
        options=list(range(1, 13)),
        index=date.today().month - 1,
        format_func=lambda m: MONTH_DISPLAY[m],
        key="sel_month",
    )
    sel_year = st.number_input(
        "Год",
        min_value=2020,
        max_value=2035,
        value=current_year,
        step=1,
        format="%d",
        key="sel_year",
    )
    return sel_month, sel_year


# ── Источник календаря + PDF ────────────────────────────────


def _calendar_source(
    cal_svc: CalendarService,
    db: DatabaseManager,
    sel_year: int,
) -> None:
    st.subheader("📁 Производственный календарь")

    avail_years = cal_svc.available_years()
    st.caption(
        f"📊 Источник: **work-calendar** (consultant.ru). "
        f"Доступны годы: {avail_years}"
    )

    corrections = db.get_corrections_for_year(sel_year)
    if corrections:
        st.caption(f"Загружены поправки для {sel_year}:")
        for c in corrections:
            kind_label = KIND_LABELS.get(c["kind"], c["kind"])
            st.caption(f"  {c['date']} — {kind_label} ({c['source']})")
        if st.button("🗑️ Удалить поправки", key="del_corrections"):
            try:
                db.save_corrections(sel_year, [])
                cal_svc.refresh_provider()
                cal_svc.build_and_cache_year(sel_year)
            except Exception as exc:
                st.error(f"Ошибка удаления поправок: {exc}")
            else:
                st.cache_data.clear()
                st.rerun()

    with st.expander("📂 Загрузить PDF (опционально)"):
        st.caption(
            "Для годов, покрытых work-calendar (2021–2027), PDF не нужен. "
            "Загрузка PDF добавляет ручные поправки — требует `pdfplumber`."
        )
        uploaded = st.file_uploader(
            "PDF с consultant.ru",
            type=["pdf"],
            help="Формат: consultant.ru/law/ref/calendar/proizvodstvennye/",
            key="pdf_upload",
        )
        if uploaded:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            save_path = UPLOAD_DIR / uploaded.name
            with open(save_path, "wb") as f:
                f.write(uploaded.getbuffer())
            result = cal_svc.import_pdf(save_path)
            if result:
                st.success(
                    f"PDF {result.year} обработан! "
                    f"Доп. выходные: {len(result.extra_holidays)}, "
                    f"Сокращённые: {len(result.shortened_days)}"
                )
                for line in result.transfers_raw:
                    st.caption(f"  → {line}")
                cal_svc.build_and_cache_year(result.year)
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(
                    "Не удалось распознать PDF. Установите pdfplumber: "
                    "`pip install pdfplumber`"
                )


# ── Кнопка сохранения ───────────────────────────────────────


def _save_button(
    db: DatabaseManager,
    cal_svc: CalendarService,
    s_base: float,
    sel_year: int,
) -> None:
    if st.button("💾 Сохранить настройки", use_container_width=True):
        try:
            db.set_setting("base_salary", s_base)
            db.set_setting("tax_rate", st.session_state.get("s_tax", 13))
            db.set_setting("kef", st.session_state.get("s_kef", 1.0))
            db.set_setting(
                "advance_cutoff_day",
                str(int(st.session_state.get("s_cutoff", 15))),
            )
            db.set_setting(
                "account_shortened",
                "1" if st.session_state.get("s_short", False) else "0",
            )
            db.set_setting(
                "standard_hours",
                str(int(st.session_state.get("s_hours", 40))),
            )
            db.set_setting("current_year", str(sel_year))
            cal_svc.refresh_provider()
        except Exception as exc:
            st.error(f"Ошибка сохранения настроек: {exc}")
        else:
            st.cache_data.clear()
            st.success("Настройки сохранены!")
