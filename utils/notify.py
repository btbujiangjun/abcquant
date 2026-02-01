from email.mime.text import MIMEText
from email.header import Header
from trade.config import TradeConfig
from utils.logger import logger

def email_notify(subject, content):
    logger.info(f"Email notify:[{subject}]\n{content}")
    try:
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['Subject'], msg['From'] = Header(subject, 'utf-8'), TradeConfig.MAIL_CONFIG["user"]
        with smtplib.SMTP_SSL(TradeConfig.MAIL_CONFIG["host"], 465) as s:
            s.login(TradeConfig.MAIL_CONFIG["user"], TradeConfig.MAIL_CONFIG["pass"])
            s.sendmail(msg['From'], TradeConfig.MAIL_CONFIG["receivers"], msg.as_string())
    except Exception as e:
        logger.info(f"邮件发送失败: {e}")

def dingtalk_notify(subject, content):
    if not TradeConfig.DINGTALK_WEBHOOK:
        logger.warning("DingTalk webhook is required")
        return

    logger.info(f"DingTalk notify:[{subject}]\n{content}")
    try: 
        requests.post(
            TradeConfig.DINGTALK_WEBHOOK, 
            json={"msgtype": "text", "text": {"content": f"{subject}\n{content}"}}
        )
    except Exception as e:
        logger.info(f"DingTalk发送失败: {e}")
            
