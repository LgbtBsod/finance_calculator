"""views/common.py — Общие UI-хелперы и константы.

Переиспользуемые компоненты: форматирование, удаление, стиль.
"""

from __future__ import annotations

import streamlit as st

__all__ = [
    "fmt",
    "KIND_LABELS",
    "delete_buttons",
    "memo_card",
    "inject_custom_css",
    "styled_metric",
    "error_alert",
]


# ── Константы ────────────────────────────────────────────────

KIND_LABELS: dict[str, str] = {
    "extra_holiday": "🔴 выходной",
    "extra_working": "🟢 рабочий",
    "shortened": "⏱️ сокращённый",
}

# Цветовая схема
COLOR_SCHEME = {
    "primary": "#2E86AB",
    "success": "#28a745",
    "warning": "#ffc107",
    "danger": "#dc3545",
    "info": "#17a2b8",
    "light": "#f8f9fa",
    "dark": "#343a40",
    "card_bg": "#ffffff",
    "card_border": "#e0e0e0",
}


# ── Форматирование ───────────────────────────────────────────


def fmt(amount: float) -> str:
    """Форматирование суммы: '105 272.61 ₽'."""
    if amount < 0:
        return f"− {abs(amount):,.2f} ₽".replace(",", " ")
    return f"{amount:,.2f} ₽".replace(",", " ")


# ── Кнопки удаления ─────────────────────────────────────────


def delete_buttons(
    items: list[dict],
    key_prefix: str,
    delete_fn,
) -> bool:
    """Показать кнопки удаления. Возвращает True при удалении.

    Для списков > 6 элементов — компактные кнопки в строке,
    иначе — столбцы Streamlit.
    """
    if not items:
        return False

    for item in items:
        if st.button(
            "🗑️",
            key=f"{key_prefix}_{item['id']}",
            help=str(item.get("name", "")),
        ):
            try:
                delete_fn(item["id"])
            except Exception as exc:
                st.error(f"Ошибка при удалении: {exc}")
            else:
                st.cache_data.clear()
                st.rerun()
    return False


# ── Мемо-карточка ────────────────────────────────────────────

_MEMO_CARD_CSS = (
    "background:#FFF8E1;border-left:4px solid #FF9800;"
    "padding:10px 15px;margin:5px 0;border-radius:4px"
)


def memo_card(name: str, amount: float, target_date: str) -> None:
    """Отрисовка одной памятки-карточки."""
    st.markdown(
        f'<div style="{_MEMO_CARD_CSS}">'
        f"<strong>{name}</strong> — {fmt(amount)}<br>"
        f'<span style="color:#666">📅 {target_date}</span></div>',
        unsafe_allow_html=True,
    )


# ── Кастомный CSS для улучшения визуала ───────────────────────

_CUSTOM_CSS = """
<style>
/* Улучшенные карточки метрик */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    border: 1px solid #e0e0e0;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}

/* Заголовки */
h1, h2, h3 {
    color: #2c3e50;
    font-weight: 600;
}

/* Кнопки */
.stButton > button {
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.2s ease;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

/* Поля ввода */
.stNumberInput > div > div,
.stTextInput > div > div {
    border-radius: 8px;
}

/* Таблицы */
div[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}

/* Разделители */
hr {
    border-color: #e0e0e0;
    margin: 24px 0;
}

/* Карточки для вкладок */
.block-container {
    padding-top: 2rem;
}

/* Sidebar styling */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f8f9fa 0%, #ffffff 100%);
}
</style>
"""


def inject_custom_css() -> None:
    """Внедрить кастомный CSS для улучшения UI."""
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)


def styled_metric(
    label: str,
    value: str | float,
    delta: str | None = None,
    help: str | None = None,
    color: str | None = None,
) -> None:
    """Метрика с улучшенным стилем и опциональным цветом."""
    col = st.columns(1)[0]
    with col:
        if color:
            st.markdown(
                f'<div style="color:{color};font-size:1.1em;">{label}</div>',
                unsafe_allow_html=True,
            )
        st.metric(label=label, value=value, delta=delta, help=help)


def error_alert(message: str, icon: str = "🚫") -> None:
    """Показать ошибку в стилизованном формате."""
    st.markdown(
        f'<div style="background:#ffebee;border-left:4px solid #dc3545;'
        f'padding:12px 16px;margin:12px 0;border-radius:6px;">'
        f'{icon} <strong style="color:#c62828;">{message}</strong></div>',
        unsafe_allow_html=True,
    )
