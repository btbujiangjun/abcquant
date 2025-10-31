from datetime import datetime, timedelta

def get_format(date_format : str="YYMMDD") -> str:
    date_format = date_format.upper()
    if date_format == "YYMMDD":
        return "%Y-%m-%d"
    elif date_format == "YMD":
        return "%Y%m%d"
    else:
        return "%Y-%m-%d %H:%M:%S"

def _match_format(date_str:str) -> str:
    if len(date_str) == 8:
        return get_format("YMD")
    elif len(date_str) == 10:
        return get_format("YYMMDD")
    else:
        return get_format("YYMMDDHHMMSS")

def today():
    return datetime.today()

def today_str(date_format : str = "YYMMDD") -> str:
    return today().strftime(get_format(date_format))

def is_today(date_str:str) -> bool:
    try:
        return datetime.strptime(date_str, get_format()).date() == datetime.today().date()
    except ValueError:
        return False  # 格式不正确

def is_yesterday(date_str:str) -> bool:
    try:
        date_obj = datetime.strptime(date_str, _match_format(date_str)).date()
    except ValueError:
        return False  # 格式不正确
    yesterday = (today() - timedelta(days=1)).date()
    return date_obj == yesterday

def days_delta(date_str:str, days:int) -> str:
    date_format = _match_format(date_str)
    return (datetime.strptime(date_str, date_format) + timedelta(days=days)).strftime(date_format)


