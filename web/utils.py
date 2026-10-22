import re
from web.config import UNIT_SCALE

def format_value(val):
    val = float(val)
    for name, scale in reversed(list(UNIT_SCALE.items())):
        if val >= scale:
            return f"{val / scale:.2f} {name}"
    return f"{int(val):,}"

def parse_bet(input_str, balance):
    s = str(input_str).strip()
    if s in ["オールベット", "全額", "allbet", "AllBet"]:
        return balance
    for unit, scale in UNIT_SCALE.items():
        if unit in s:
            try:
                num_part = s.replace(unit, "").strip()
                return int(float(num_part) * scale)
            except Exception:
                return None
    try:
        return int(float(s))
    except Exception:
        return None
