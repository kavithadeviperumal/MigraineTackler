import os
import streamlit.components.v1 as components
from datetime import time

_DIR = os.path.dirname(os.path.abspath(__file__))
_component = components.declare_component("time_picker", path=_DIR)


def time_picker(label: str, value: time = time(0, 0), key: str | None = None) -> time:
    default = value.strftime("%H:%M")
    result = _component(label=label, value=default, key=key, default=default)
    try:
        h, m = map(int, (result or default).split(":"))
        return time(h, m)
    except Exception:
        return value
