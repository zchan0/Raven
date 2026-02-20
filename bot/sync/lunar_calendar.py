"""Lunar calendar and solar term utilities (1900-2100)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

# Standard lunar data table (1900-2100), commonly used with HKO-based encoding.
# Encoding per year:
# - low 4 bits: leap month (0 means no leap month)
# - bit 16 (0x10000): leap month length (1 -> 30 days, 0 -> 29 days)
# - bits 15..4: month lengths for months 1..12 (1 -> 30 days, 0 -> 29 days)
LUNAR_DATA = [
    0x04BD8,
    0x04AE0,
    0x0A570,
    0x054D5,
    0x0D260,
    0x0D950,
    0x16554,
    0x056A0,
    0x09AD0,
    0x055D2,
    0x04AE0,
    0x0A5B6,
    0x0A4D0,
    0x0D250,
    0x1D255,
    0x0B540,
    0x0D6A0,
    0x0ADA2,
    0x095B0,
    0x14977,
    0x04970,
    0x0A4B0,
    0x0B4B5,
    0x06A50,
    0x06D40,
    0x1AB54,
    0x02B60,
    0x09570,
    0x052F2,
    0x04970,
    0x06566,
    0x0D4A0,
    0x0EA50,
    0x06E95,
    0x05AD0,
    0x02B60,
    0x186E3,
    0x092E0,
    0x1C8D7,
    0x0C950,
    0x0D4A0,
    0x1D8A6,
    0x0B550,
    0x056A0,
    0x1A5B4,
    0x025D0,
    0x092D0,
    0x0D2B2,
    0x0A950,
    0x0B557,
    0x06CA0,
    0x0B550,
    0x15355,
    0x04DA0,
    0x0A5D0,
    0x14573,
    0x052D0,
    0x0A9A8,
    0x0E950,
    0x06AA0,
    0x0AEA6,
    0x0AB50,
    0x04B60,
    0x0AAE4,
    0x0A570,
    0x05260,
    0x0F263,
    0x0D950,
    0x05B57,
    0x056A0,
    0x096D0,
    0x04DD5,
    0x04AD0,
    0x0A4D0,
    0x0D4D4,
    0x0D250,
    0x0D558,
    0x0B540,
    0x0B6A0,
    0x195A6,
    0x095B0,
    0x049B0,
    0x0A974,
    0x0A4B0,
    0x0B27A,
    0x06A50,
    0x06D40,
    0x0AF46,
    0x0AB60,
    0x09570,
    0x04AF5,
    0x04970,
    0x064B0,
    0x074A3,
    0x0EA50,
    0x06B58,
    0x055C0,
    0x0AB60,
    0x096D5,
    0x092E0,
    0x0C960,
    0x0D954,
    0x0D4A0,
    0x0DA50,
    0x07552,
    0x056A0,
    0x0ABB7,
    0x025D0,
    0x092D0,
    0x0CAB5,
    0x0A950,
    0x0B4A0,
    0x0BAA4,
    0x0AD50,
    0x055D9,
    0x04BA0,
    0x0A5B0,
    0x15176,
    0x052B0,
    0x0A930,
    0x07954,
    0x06AA0,
    0x0AD50,
    0x05B52,
    0x04B60,
    0x0A6E6,
    0x0A4E0,
    0x0D260,
    0x0EA65,
    0x0D530,
    0x05AA0,
    0x076A3,
    0x096D0,
    0x04BD7,
    0x04AD0,
    0x0A4D0,
    0x1D0B6,
    0x0D250,
    0x0D520,
    0x0DD45,
    0x0B5A0,
    0x056D0,
    0x055B2,
    0x049B0,
    0x0A577,
    0x0A4B0,
    0x0AA50,
    0x1B255,
    0x06D20,
    0x0ADA0,
    0x14B63,
    0x09370,
    0x049F8,
    0x04970,
    0x064B0,
    0x168A6,
    0x0EA50,
    0x06B20,
    0x1A6C4,
    0x0AAE0,
    0x0A2E0,
    0x0D2E3,
    0x0C960,
    0x0D557,
    0x0D4A0,
    0x0DA50,
    0x05D55,
    0x056A0,
    0x0A6D0,
    0x055D4,
    0x052D0,
    0x0A9B8,
    0x0A950,
    0x0B4A0,
    0x0B6A6,
    0x0AD50,
    0x055A0,
    0x0ABA4,
    0x0A5B0,
    0x052B0,
    0x0B273,
    0x06930,
    0x07337,
    0x06AA0,
    0x0AD50,
    0x14B55,
    0x04B60,
    0x0A570,
    0x054E4,
    0x0D160,
    0x0E968,
    0x0D520,
    0x0DAA0,
    0x16AA6,
    0x056D0,
    0x04AE0,
    0x0A9D4,
    0x0A2D0,
    0x0D150,
    0x0F252,
    0x0D520,
]

LUNAR_MONTH_NAMES = ["正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "冬", "腊"]
LUNAR_DAY_NAMES = [
    "初一",
    "初二",
    "初三",
    "初四",
    "初五",
    "初六",
    "初七",
    "初八",
    "初九",
    "初十",
    "十一",
    "十二",
    "十三",
    "十四",
    "十五",
    "十六",
    "十七",
    "十八",
    "十九",
    "二十",
    "廿一",
    "廿二",
    "廿三",
    "廿四",
    "廿五",
    "廿六",
    "廿七",
    "廿八",
    "廿九",
    "三十",
]

BASE_DATE = datetime(1900, 1, 31)

SOLAR_TERM_NAMES = [
    "小寒",
    "大寒",
    "立春",
    "雨水",
    "惊蛰",
    "春分",
    "清明",
    "谷雨",
    "立夏",
    "小满",
    "芒种",
    "夏至",
    "小暑",
    "大暑",
    "立秋",
    "处暑",
    "白露",
    "秋分",
    "寒露",
    "霜降",
    "立冬",
    "小雪",
    "大雪",
    "冬至",
]

# Minutes offset from 1900-01-06 02:05 for each solar term.
SOLAR_TERM_INFO = [
    0,
    21208,
    42467,
    63836,
    85337,
    107014,
    128867,
    150921,
    173149,
    195551,
    218072,
    240693,
    263343,
    285989,
    308563,
    331033,
    353350,
    375494,
    397447,
    419210,
    440795,
    462224,
    483532,
    504758,
]


def _year_data(year: int) -> int:
    return LUNAR_DATA[year - 1900]


def _leap_month(year: int) -> int:
    return _year_data(year) & 0xF


def _leap_days(year: int) -> int:
    leap = _leap_month(year)
    if leap == 0:
        return 0
    return 30 if (_year_data(year) & 0x10000) else 29


def _month_days(year: int, month: int) -> int:
    if month < 1 or month > 12:
        raise ValueError(f"invalid lunar month: {month}")
    return 30 if (_year_data(year) & (0x10000 >> month)) else 29


def _year_days(year: int) -> int:
    days = 348
    bit = 0x8000
    data = _year_data(year)
    for _ in range(12):
        if data & bit:
            days += 1
        bit >>= 1
    return days + _leap_days(year)


def get_lunar_date(date: datetime) -> Optional[str]:
    """Return lunar date text (e.g. '正月初三') or None if out of range."""
    if date.year < 1900 or date.year > 2100:
        return None

    offset = (date.replace(hour=0, minute=0, second=0, microsecond=0) - BASE_DATE).days
    if offset < 0:
        return None

    lunar_year = 1900
    while lunar_year <= 2100:
        year_days = _year_days(lunar_year)
        if offset < year_days:
            break
        offset -= year_days
        lunar_year += 1

    if lunar_year > 2100:
        return None

    leap_month = _leap_month(lunar_year)
    is_leap = False
    lunar_month = 1

    while lunar_month <= 12:
        month_days = _month_days(lunar_year, lunar_month)
        if offset < month_days:
            lunar_day = offset + 1
            month_name = LUNAR_MONTH_NAMES[lunar_month - 1]
            if is_leap:
                month_name = f"闰{month_name}"
            return f"{month_name}月{LUNAR_DAY_NAMES[lunar_day - 1]}"

        offset -= month_days

        if leap_month == lunar_month and not is_leap:
            leap_days = _leap_days(lunar_year)
            if offset < leap_days:
                lunar_day = offset + 1
                month_name = f"闰{LUNAR_MONTH_NAMES[lunar_month - 1]}"
                return f"{month_name}月{LUNAR_DAY_NAMES[lunar_day - 1]}"
            offset -= leap_days

        lunar_month += 1

    return None


def _solar_term_day(year: int, index: int) -> int:
    # Standard approximation formula for 1900-2100.
    minutes = 525948.76 * (year - 1900) + SOLAR_TERM_INFO[index]
    dt = datetime(1900, 1, 6, 2, 5) + timedelta(minutes=minutes)
    return dt.day


def get_solar_term(date: datetime) -> Optional[str]:
    """Return solar term name for the date, otherwise None."""
    if date.year < 1900 or date.year > 2100:
        return None

    for i in (date.month - 1) * 2, (date.month - 1) * 2 + 1:
        if date.day == _solar_term_day(date.year, i):
            return SOLAR_TERM_NAMES[i]
    return None


LUNAR_HOLIDAYS = {
    "正月初一": "春节",
    "正月十五": "元宵节",
    "五月初五": "端午节",
    "七月初七": "七夕",
    "八月十五": "中秋节",
    "九月初九": "重阳节",
    "腊月初八": "腊八节",
}

SOLAR_HOLIDAYS = {
    (1, 1): "元旦",
    (5, 1): "劳动节",
    (10, 1): "国庆节",
    (12, 25): "圣诞节",
}


def get_holiday(date: datetime) -> Optional[str]:
    """Return holiday name or None."""
    lunar = get_lunar_date(date)
    if lunar is not None:
        holiday = LUNAR_HOLIDAYS.get(lunar)
        if holiday is not None:
            return holiday
    return SOLAR_HOLIDAYS.get((date.month, date.day))


def get_special_day(date: datetime) -> Optional[str]:
    """Return holiday first, then solar term, otherwise None."""
    holiday = get_holiday(date)
    if holiday is not None:
        return holiday
    return get_solar_term(date)


def verify_accuracy() -> bool:
    """Run required accuracy checks and print results."""
    cases = [
        {
            "date": datetime(2026, 2, 17),
            "lunar": "正月初一",
            "holiday": "春节",
            "solar_term": None,
            "special": "春节",
        },
        {
            "date": datetime(2026, 2, 18),
            "lunar": "正月初二",
            "holiday": None,
            "solar_term": "雨水",
            "special": "雨水",
        },
        {
            "date": datetime(2026, 2, 13),
            "lunar": "腊月廿六",
            "holiday": None,
            "solar_term": None,
            "special": None,
        },
    ]

    all_passed = True
    print("=" * 48)
    print("verify_accuracy")
    print("=" * 48)

    for case in cases:
        d = case["date"]
        actual_lunar = get_lunar_date(d)
        actual_holiday = get_holiday(d)
        actual_term = get_solar_term(d)
        actual_special = get_special_day(d)

        passed = (
            actual_lunar == case["lunar"]
            and actual_holiday == case["holiday"]
            and actual_term == case["solar_term"]
            and actual_special == case["special"]
        )
        all_passed = all_passed and passed

        status = "PASS" if passed else "FAIL"
        print(
            f"[{status}] {d:%Y-%m-%d} "
            f"lunar={actual_lunar} holiday={actual_holiday} "
            f"solar_term={actual_term} special={actual_special}"
        )

        if not passed:
            print(
                "  expected "
                f"lunar={case['lunar']} holiday={case['holiday']} "
                f"solar_term={case['solar_term']} special={case['special']}"
            )

    print("=" * 48)
    print("RESULT:", "PASS" if all_passed else "FAIL")
    print("=" * 48)
    return all_passed


if __name__ == "__main__":
    verify_accuracy()
