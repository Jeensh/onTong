"""v2 slab manufacturing 의 namespace constants.

Lesson 1 §4.1 — Java SdConstants 의 Python mirror. namespace class 의 first-class contract.

Phase α 의 confirmed_plant_cd.py 의 8-position string set 흡수.
"""
from __future__ import annotations


class SdConstants:
    """Slab design 의 namespace class (Java SdConstants 의 Python mirror).

    Phase α 의 individual module constants (POS_SM, POS_HR 등) 를 namespace 안으로 옮김.
    Lesson 1 §2.3 의 두 의도 충돌 (α1 module constants vs α2 namespace) 해소.

    8-position plant codes — slab manufacturing 의 ERP integration convention.
    """
    # 8-position plant code constants (Phase α confirmed_plant_cd.py 의 set)
    POS_SM = "SM______"
    POS_HR = "HR______"
    POS_CR = "CR______"
    POS_BF = "BF______"
    POS_AF = "AF______"
    POS_RB = "RB______"
    POS_RH = "RH______"
    POS_PC = "PC______"

    # Position groups (for activation_check)
    ACTIVE_POSITIONS = frozenset([POS_SM, POS_HR, POS_CR, POS_BF, POS_AF, POS_RB])
    HR_POSITIONS = frozenset([POS_HR, POS_RH])

    # Sentinel
    NULL_PLANT = "________"
