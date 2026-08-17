"""FurkAI notification service.
Telegram is optional and disabled unless TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID exist.
"""
import json, os, urllib.parse, urllib.request
from dotenv import load_dotenv
load_dotenv()

class NotificationService:
    def __init__(self):
        self.token=os.getenv('TELEGRAM_BOT_TOKEN','').strip()
        self.chat_id=os.getenv('TELEGRAM_CHAT_ID','').strip()

    @property
    def telegram_configured(self):
        return bool(self.token and self.chat_id)

    def telegram(self, message: str, timeout: float=8):
        if not self.telegram_configured:
            return {'ok':False,'configured':False,'error':'TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID ayarlanmamış'}
        url=f'https://api.telegram.org/bot{self.token}/sendMessage'
        data=urllib.parse.urlencode({'chat_id':self.chat_id,'text':message,'disable_web_page_preview':'true'}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url,data=data,method='POST'),timeout=timeout) as r:
                payload=json.loads(r.read().decode('utf-8'))
            return {'ok':bool(payload.get('ok')),'configured':True,'response':payload}
        except Exception as e:
            return {'ok':False,'configured':True,'error':str(e)}

    def signal(self, symbol, decision, score=None, price=None, reason=None):
        bits=[f'FurkAI BIST — {symbol}', f'Karar: {decision}']
        if score is not None: bits.append(f'Skor: {score}')
        if price is not None: bits.append(f'Fiyat: {price}')
        if reason: bits.append(f'Neden: {reason}')
        return self.telegram('\n'.join(bits))

service=NotificationService()
