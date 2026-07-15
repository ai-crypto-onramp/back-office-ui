"""Back Office UI dashboard modules — one per dashboard stage."""

from __future__ import annotations

from typing import Any

import streamlit as st


def section(title: str, explanation: str, *, icon: str | None = None) -> None:
    """Render a section header followed by a collapsed plain-language explanation.

    The header itself is always visible on the page; immediately underneath it a
    collapsed ``st.expander`` describes, in simple terms, what the section does so
    operators can decide whether they need to expand the related action button /
    dialog without wading through jargon.

    ``title`` may already include an emoji prefix; ``icon`` is an optional extra
    emoji shown before the "What does this do?" label.
    """
    header = f"{icon} {title}" if icon else title
    st.subheader(header)
    with st.expander("What does this do?", expanded=False):
        st.caption(explanation)


def action_button(label: str, dialog_func: Any, *, key: str | None = None) -> None:
    """Render an always-visible action button that opens ``dialog_func`` in a dialog.

    ``dialog_func`` must be a function decorated with ``@st.dialog``. The button is
    placed directly on the page (never under a collapsed section) so the primary
    action is always reachable.
    """
    if st.button(label, type="primary", key=key):
        dialog_func()
