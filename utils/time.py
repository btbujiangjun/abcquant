from datetime import datetime, timedelta

def is_yesterday(date_str:str) -> bool:
    """
    判断 date_str 是否为昨天
    :param date_str: 字符串，格式 'yyyy-mm-dd'
    :return: True/False
    """
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return False  # 格式不正确
    yesterday = (datetime.today() - timedelta(days=1)).date()
    return date_obj == yesterday

def days_delta_yyyymmdd(date_str:str, days:int) -> str:
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
