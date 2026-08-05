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
]


# ── Константы ────────────────────────────────────────────────

KIND_LABELS: dict[str, str] = {
    "extra_holiday": "🔴 выходной",
    "extra_working": "🟢 рабочий",
    "shortened": "⏱️ сокращённый",
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
