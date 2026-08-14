import json, math, os, time, urllib.parse, urllib.request, threading, sqlite3, hmac, base64, re, stat
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

BASE=Path(__file__).resolve().parent
CFG=BASE/'config.json'; DB=BASE/'furkai_bist.db'; LOG=BASE/'furkai_bist.log'; SECRET_FILE=BASE/'.furkai_secret'
CACHE={}; CACHE_LOCK=threading.RLock(); TTL=180

def _fernet():
    raw=os.environ.get('FURKAI_SECRET_KEY','').strip()
    if not raw:
        if SECRET_FILE.exists(): raw=SECRET_FILE.read_text(encoding='utf-8').strip()
        else:
            raw=Fernet.generate_key().decode(); SECRET_FILE.write_text(raw,encoding='utf-8'); os.chmod(SECRET_FILE, stat.S_IRUSR|stat.S_IWUSR)
    return Fernet(raw.encode())

def _decrypt_key(value):
    if not value: return ''
    if not str(value).startswith('enc:'): return str(value)  # migration from legacy plaintext
    try: return _fernet().decrypt(str(value)[4:].encode()).decode()
    except (InvalidToken,ValueError): return ''

def _encrypt_key(value):
    return 'enc:'+_fernet().encrypt(str(value).encode()).decode() if value else ''

DEFAULT={'gemini_key':'','gemini_model':'gemini-3.6-flash','scanner_limit':250,'default_period':'1y','default_interval':'1d','refresh_seconds':15,'auto_refresh':True,'theme':'dark','app_version':'15.0'}
if CFG.exists():
    try: DEFAULT.update(json.loads(CFG.read_text(encoding='utf-8')))
    except Exception: pass
DEFAULT['gemini_key']=_decrypt_key(DEFAULT.get('gemini_key','')); DEFAULT['app_version']='15.0'

BIST_UNIVERSE='''THYAO TUPRS ASELS GARAN AKBNK YKBNK ISCTR BIMAS EREGL KCHOL SAHOL SISE TCELL FROTO TOASO PGSUS TAVHL PETKM HEKTS KOZAL KOZAA ENKAI ARCLK MGROS ULKER SASA ASTOR OYAKC CCOLA DOAS MIATK GESAN GWIND ODAS ALARK ENJSA KRDMD TTKOM VESTL LOGO MAVI SOKM AEFES CIMSA KONTR AKSEN TABGD REEDR AGHOL AGESA AKSA ALBRK ANSGR ASUZU ATATP AYDEM BAGFS BANVT BERA BIZIM BOBET BORLS BOSSA BRISA BRSAN BRYAT BUCIM CANTE CEMAS CLEBI CRFSA DAGI DARDL DEVA DGATE DMSAS DODUR DOKTA DURDO DYOBY EGEEN EGPRO EKGYO EMKEL ENERY ERBOS ESCOM EUHOL EUPWR FENER FORTE GENTS GEREL GLYHO GOZDE GUBRF GYHOL HALKB HDFGS HLGYO HUBVC ICBCT IHLAS IHYAY INDES INFO ISDMR ISFIN ISGYO ISMEN JANTS KARSN KATMR KAYSE KCAER KERVT KFEIN KLGYO KLSER KMPUR KOCMT KORDS KOTON KRDM KRDMA KRDMB KRVGD KSTUR KTSKR KUYAS LIDER LKMNH MACKO MAGEN MAKIM MARGN MARKA MEDTR MEGAP MERIT MHRGY MPARK MRDIY MRGYO NIBAS NTGAZ OBASE OBAMS ORCAY ORGE OSTIM OTKAR OYAKC OZKGY PAPIL PARSN PASEU PATEK PCILT PEKGY PENTA PETUN PKART PNSUT POLHO PRKAB PSGYO QUAGR RALYH RAYSG RODRG RUBNS RUZYE RYGYO SARKY SAYAS SELEC SELGD SKBNK SKYMD SMART SNGYO SNICA SOKM SRVGY SUMAS SURGY TATEN TATGD TAVHL TBORG TCKRC TDGYO TEHOL TEKTU TERA TGSAS TKFEN TKNSA TLMAN TMPOL TOASO TRCAS TRGYO TSKB TSPOR TTKOM TTRAK TUKAS TUPRS TURGG ULKER ULUFA UNLU VAKBN VANGD VBTYZ VERUS VESBE VKFYO VKING YAPRK YATAS YAYLA YEOTK YGGYO YKBNK YKSLN YUNSA ZEDUR ZOREN'''.split()
BIST_UNIVERSE=[s for s in dict.fromkeys(BIST_UNIVERSE) if s.isalpha() and 3<=len(s)<=6]
UNIVERSE_CACHE={'symbols':BIST_UNIVERSE,'source':'Yerleşik başlangıç listesi','updated':0}

# Optional user-provided initial portfolio. Loaded only when the local DB is empty.
# Quantities/costs are taken from the user's latest portfolio screenshot.
INITIAL_PORTFOLIO=[
    {'id':1001,'symbol':'SURGY.IS','label':'','qty':1709,'cost':67.29,'note':'Imported from latest portfolio screenshot'},
    {'id':1002,'symbol':'OYAKC.IS','label':'','qty':2100,'cost':21.90,'note':'Imported from latest portfolio screenshot'},
    {'id':1003,'symbol':'MRGYO.IS','label':'','qty':32241.6,'cost':1.77,'note':'Imported from latest portfolio screenshot'},
    {'id':1004,'symbol':'TUPRS.IS','label':'','qty':80,'cost':236.11,'note':'Imported from latest portfolio screenshot'},
    {'id':1005,'symbol':'GARAN.IS','label':'','qty':130,'cost':137.23,'note':'Imported from latest portfolio screenshot'},
    {'id':1006,'symbol':'LOGO.IS','label':'','qty':108,'cost':144.05,'note':'Imported from latest portfolio screenshot'},
    {'id':1007,'symbol':'RUZYE.IS','label':'','qty':1945,'cost':11.12,'note':'Imported from latest portfolio screenshot'},
    {'id':1008,'symbol':'BULGS.IS','label':'','qty':291,'cost':44.70,'note':'Imported from latest portfolio screenshot'},
    {'id':1009,'symbol':'GWIND.IS','label':'','qty':385,'cost':30.85,'note':'Imported from latest portfolio screenshot'},
    {'id':1010,'symbol':'PAPIL.IS','label':'','qty':516,'cost':19.33,'note':'Imported from latest portfolio screenshot'},
    {'id':1011,'symbol':'CLEBI.IS','label':'','qty':4,'cost':1734.46,'note':'Imported from latest portfolio screenshot'},
]

# ---------- persistence ----------
def db():
    c=sqlite3.connect(DB,timeout=10); c.row_factory=sqlite3.Row
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio(id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, label TEXT, qty REAL NOT NULL, cost REAL NOT NULL, note TEXT DEFAULT '')''')
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio_history(ts REAL, value REAL, cost REAL, pnl REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS signal_history(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, symbol TEXT NOT NULL, models TEXT NOT NULL, entry REAL NOT NULL, score REAL NOT NULL)''')
    # Forward-compatible columns for fixed-horizon signal performance.
    cols={r[1] for r in c.execute('PRAGMA table_info(signal_history)')}
    for name in ('ret_1d','ret_5d','ret_20d'):
        if name not in cols: c.execute(f'ALTER TABLE signal_history ADD COLUMN {name} REAL')
    c.commit(); return c

def load_portfolio():
    c=db(); rows=[dict(r) for r in c.execute('SELECT * FROM portfolio ORDER BY id')];
    if not rows and INITIAL_PORTFOLIO:
        normalized=[]
        for p in INITIAL_PORTFOLIO:
            normalized.append((p['id'],p['symbol'],p.get('label',''),float(p['qty']),float(p['cost']),p.get('note','')))
        c.executemany('INSERT INTO portfolio(id,symbol,label,qty,cost,note) VALUES(?,?,?,?,?,?)',normalized)
        c.commit(); rows=[dict(r) for r in c.execute('SELECT * FROM portfolio ORDER BY id')]
    c.close(); return rows

def save_portfolio(rows):
    if not isinstance(rows,list) or len(rows)>200: raise ValueError('Portföy 0-200 pozisyon içermelidir')
    normalized=[]; seen=set()
    for p in rows:
        if not isinstance(p,dict): raise ValueError('Geçersiz portföy kaydı')
        sym=str(p.get('symbol','')).upper().replace('.IS','').strip()
        if not re.fullmatch(r'[A-Z0-9]{3,6}',sym): raise ValueError(f'Geçersiz hisse kodu: {sym}')
        try:
            qty=float(p.get('qty')); cost=float(p.get('cost'))
        except (TypeError,ValueError): raise ValueError('Adet ve maliyet sayısal olmalı')
        if not math.isfinite(qty) or not math.isfinite(cost) or qty<=0 or cost<=0: raise ValueError('Adet ve maliyet pozitif sonlu değerler olmalı')
        pid=int(p.get('id') or int(time.time()*1000))
        if pid in seen: raise ValueError('Portföy kayıt ID değerleri benzersiz olmalı')
        seen.add(pid)
        normalized.append((pid,sym+'.IS',str(p.get('label',''))[:120],qty,cost,str(p.get('note',''))[:500]))
    c=db(); c.execute('DELETE FROM portfolio')
    c.executemany('INSERT INTO portfolio(id,symbol,label,qty,cost,note) VALUES(?,?,?,?,?,?)',normalized)
    c.commit(); c.close()

def public_config():
    key=str(DEFAULT.get('gemini_key','') or '')
    return {
        'ok':True,
        'gemini_configured':bool(key),
        'gemini_key_masked':('••••••••'+key[-4:]) if len(key)>=4 else ('••••' if key else ''),
        'gemini_model':DEFAULT.get('gemini_model','gemini-3.6-flash'),
        'scanner_limit':int(DEFAULT.get('scanner_limit',250)),
        'default_period':DEFAULT.get('default_period','1y'),
        'default_interval':DEFAULT.get('default_interval','1d'),
        'refresh_seconds':max(5,int(DEFAULT.get('refresh_seconds',15))),
        'auto_refresh':bool(DEFAULT.get('auto_refresh',True)),
        'theme':DEFAULT.get('theme','dark'),
        'app_version':DEFAULT.get('app_version','15.0'),
        'config_path':'config.json','key_storage':'encrypted','secret_source':'FURKAI_SECRET_KEY' if os.environ.get('FURKAI_SECRET_KEY') else 'local secret file'
    }

def save_config(updates):
    allowed=('gemini_key','gemini_model','scanner_limit','default_period','default_interval','refresh_seconds','auto_refresh','theme')
    for k in allowed:
        if k not in updates: continue
        v=updates[k]
        if k=='scanner_limit':
            v=max(10,min(700,int(v)))
        elif k=='refresh_seconds':
            v=max(5,min(300,int(v)))
        elif k=='auto_refresh':
            v=bool(v)
        elif k=='gemini_model':
            v=str(v).strip()[:120] or 'gemini-3.6-flash'
        elif k in ('default_period','default_interval'):
            v=str(v).strip()
        elif k=='gemini_key':
            v=str(v).strip()
        elif k=='theme':
            v=str(v).strip().lower()
            if v not in ('dark','light','system'): v='dark'
        DEFAULT[k]=v
    persist=dict(DEFAULT); persist['gemini_key']=_encrypt_key(DEFAULT.get('gemini_key','')); CFG.write_text(json.dumps(persist,ensure_ascii=False,indent=2),encoding='utf-8'); os.chmod(CFG, stat.S_IRUSR|stat.S_IWUSR)
    return public_config()

def data_status():
    status={'ok':True,'yahoo':'UNKNOWN','gemini':'CONFIGURED' if DEFAULT.get('gemini_key') else 'NOT_CONFIGURED','last_cache_items':len(CACHE),'version':DEFAULT.get('app_version','15.0')}
    try:
        d=yahoo_chart('THYAO','5d','1d')
        status['yahoo']='OK' if d.get('timestamp') else 'EMPTY'
        status['sample_symbol']=d.get('symbol')
        status['last_timestamp']=d.get('timestamp',[])[-1] if d.get('timestamp') else None
        status['data_age_seconds']=max(0,int(time.time()-status['last_timestamp'])) if status['last_timestamp'] else None
        status['freshness']='FRESH' if status['data_age_seconds'] is not None and status['data_age_seconds']<300 else 'STALE' if status['data_age_seconds'] is not None else 'UNKNOWN'
    except Exception as e:
        status['yahoo']='ERROR'; status['error']=str(e)
    return status

# ---------- data ----------
def http_json(url,timeout=15):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 FurkAI-BIST/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read().decode('utf-8','ignore'))

def yahoo_chart(symbol,period='1y',interval='1d'):
    s=str(symbol).strip().upper(); s=s if (s.endswith('.IS') or s.startswith('^')) else s+'.IS'
    key=(s,period,interval); now=time.time()
    with CACHE_LOCK:
        x=CACHE.get(key)
        if x and now-x['ts']<TTL: return x['data']
    last=None
    for host in ('query1.finance.yahoo.com','query2.finance.yahoo.com'):
        try:
            u=f'https://{host}/v8/finance/chart/{urllib.parse.quote(s)}?interval={urllib.parse.quote(interval)}&range={urllib.parse.quote(period)}&events=div%2Csplits'
            d=http_json(u); result=(d.get('chart') or {}).get('result') or []
            if not result: raise RuntimeError('Yahoo veri döndürmedi')
            r=result[0]; out={'symbol':s,'meta':r.get('meta') or {},'quote':((r.get('indicators') or {}).get('quote') or [{}])[0],'timestamp':r.get('timestamp') or [],'events':r.get('events') or {}}
            with CACHE_LOCK: CACHE[key]={'ts':now,'data':out}
            return out
        except Exception as e: last=e
    raise RuntimeError(f'Piyasa verisi alınamadı ({s}): {last}')

BIST_TZ=ZoneInfo('Europe/Istanbul')
# Borsa İstanbul Pay Piyasası continuous trading closes at 18:10 on full days.
# On official half-days the session ends at 13:00. These dates are sourced from
# Borsa İstanbul's published official-holiday calendar and are kept explicit so
# a historical backtest does not accidentally treat a half-day as a full day.
BIST_CLOSE_TIME=dt_time(18,10)
BIST_HALF_DAY_CLOSE_TIME=dt_time(13,0)
BIST_HALF_DAYS={
    # 2024-2026 official Borsa İstanbul half-days relevant to the supported history window.
    '2024-04-09','2024-10-28',
    '2025-06-05','2025-10-28',
    '2026-03-19','2026-05-26','2026-10-28',
}

def _bist_session_close(local_date):
    return BIST_HALF_DAY_CLOSE_TIME if local_date.strftime('%Y-%m-%d') in BIST_HALF_DAYS else BIST_CLOSE_TIME

def _daily_bar_complete(ts):
    """Return True only when the Yahoo daily bar belongs to a completed BIST session."""
    local_bar=datetime.fromtimestamp(int(ts), BIST_TZ)
    now=datetime.now(BIST_TZ)
    if local_bar.date()!=now.date(): return True
    return now.time() >= _bist_session_close(local_bar.date())

def history(symbol,period='1y',interval='1d'):
    interval=(interval or '1d').lower()
    supported=('1m','5m','15m','30m','1h','2h','4h','1d','1w','1mo')
    if interval not in supported:
        raise RuntimeError('Desteklenen zaman dilimleri: 1M, 5M, 15M, 30M, 1H, 2H, 4H, 1D, 1W, 1MO')
    fetch_interval='1h' if interval in ('2h','4h') else interval
    fetch_period=period
    if interval=='1m': fetch_period='5d'
    elif interval in ('5m','15m','30m'): fetch_period='60d'
    elif interval in ('1h','2h','4h') and period in ('5y','max'): fetch_period='2y'
    d=yahoo_chart(symbol,fetch_period,fetch_interval); q=d['quote']; ts=d.get('timestamp',[])
    keys=('open','high','low','close','volume'); arrays=[q.get(k,[]) for k in keys]
    n=min([len(ts),*(len(a) for a in arrays)])
    rows=[]
    for i in range(n):
        if not isinstance(ts[i],(int,float)): continue
        if fetch_interval=='1d' and not _daily_bar_complete(ts[i]): continue
        vals=[arrays[j][i] for j in range(len(keys))]
        if all(isinstance(x,(int,float)) and math.isfinite(float(x)) for x in vals):
            rows.append((int(ts[i]),*[float(x) for x in vals]))
    if len(rows)<60: raise RuntimeError('Yeterli tamamlanmış günlük OHLCV verisi yok')

    # Normalize historical stock splits so technical indicators and backtests
    # do not mistake a split price jump for a real market move. Yahoo exposes
    # split events separately from OHLCV; adjust only bars strictly before each
    # split date. Volume is multiplied by the split ratio. Cash dividends are
    # intentionally not folded into price history because they are cash flows,
    # not price splits, and the backtest currently does not model dividends.
    split_events=(d.get('events') or {}).get('splits') or {}
    if split_events:
        normalized=[]
        for row in rows:
            ts,opn,high,low,close,vol=row
            factor=1.0
            for ev_ts,ev in split_events.items():
                try:
                    split_ts=int(ev_ts); num=float(ev.get('numerator',0)); den=float(ev.get('denominator',0))
                    if split_ts>ts and num>0 and den>0:
                        factor*=num/den
                except (TypeError,ValueError):
                    continue
            if factor!=1.0:
                opn/=factor; high/=factor; low/=factor; close/=factor; vol*=factor
            normalized.append((ts,opn,high,low,close,vol))
        rows=normalized
    if interval=='1w':
        grouped=[]; bucket=None; cur=None
        for row in rows:
            ts,opn,high,low,close,vol=row
            dt=datetime.fromtimestamp(ts,BIST_TZ); key=(dt.isocalendar().year,dt.isocalendar().week)
            if bucket!=key:
                if cur: grouped.append(cur)
                bucket=key; cur=[ts,opn,high,low,close,vol]
            else:
                cur[2]=max(cur[2],high); cur[3]=min(cur[3],low); cur[4]=close; cur[5]+=vol
        if cur: grouped.append(cur)
        rows=grouped
    if interval in ('2h','4h'):
        grouped=[]; bucket=None; cur=None; hours=2 if interval=='2h' else 4
        for row in rows:
            ts,opn,high,low,close,vol=row
            dt=datetime.fromtimestamp(ts,BIST_TZ)
            key=(dt.year,dt.month,dt.day,(dt.hour//hours))
            if bucket!=key:
                if cur: grouped.append(cur)
                bucket=key; cur=[ts,opn,high,low,close,vol]
            else:
                cur[2]=max(cur[2],high); cur[3]=min(cur[3],low); cur[4]=close; cur[5]+=vol
        if cur: grouped.append(cur)
        rows=grouped
    return {'symbol':d['symbol'],'timestamp':[r[0] for r in rows],**{k:[r[j+1] for r in rows] for j,k in enumerate(keys)}}

def quote(symbol):
    d=yahoo_chart(symbol,'5d','1d'); m=d['meta']; p=m.get('regularMarketPrice'); prev=m.get('previousClose') or m.get('chartPreviousClose')
    if p is None: raise RuntimeError('Güncel fiyat alanı yok')
    p=float(p); prev=float(prev) if prev is not None else None; ch=p-prev if prev is not None else None
    return {'ok':True,'symbol':d['symbol'],'price':p,'previousClose':prev,'dailyChange':ch,'dailyChangePct':(ch/prev*100 if prev else None),'marketTimestamp':m.get('regularMarketTime'),'source':'Yahoo Finance','warning':'Yahoo gecikmeli olabilir'}

def quotes(symbols):
    out={}; errors=[]
    with ThreadPoolExecutor(max_workers=8) as ex:
        fm={ex.submit(quote,s):s for s in dict.fromkeys(symbols)}
        for f in as_completed(fm):
            s=fm[f]
            try: out[s]=f.result()
            except Exception as e: errors.append({'symbol':s,'error':str(e)})
    return {'ok':True,'quotes':out,'errors':errors}

def universe():
    # Keep a conservative fallback. If KAP page exposes a usable list, refresh it.
    if time.time()-UNIVERSE_CACHE['updated']<43200: return UNIVERSE_CACHE
    try:
        req=urllib.request.Request('https://www.kap.org.tr/tr/Pazarlar',headers={'User-Agent':'Mozilla/5.0 FurkAI-BIST/1.0'})
        with urllib.request.urlopen(req,timeout=12) as r: html=r.read().decode('utf-8','ignore')
        found=re.findall(r'>\s*([A-Z0-9]{3,6})\s*</a>',html.upper()); found=[s for s in dict.fromkeys(found) if any(c.isalpha() for c in s)]
        if len(found)>=450: UNIVERSE_CACHE.update(symbols=found,source='KAP Pazarlar / kamuya açık liste',updated=time.time()); return UNIVERSE_CACHE
    except Exception: pass
    UNIVERSE_CACHE.update(updated=time.time()); return UNIVERSE_CACHE

# ---------- indicators ----------
def sma(a,n): return sum(a[-n:])/n if len(a)>=n else None
def ema(a,n):
    if len(a)<n:return None
    k=2/(n+1); e=sum(a[:n])/n
    for x in a[n:]: e=x*k+e*(1-k)
    return e
def rsi(a,n=14):
    """Wilder RSI using Wilder's recursive average of gains/losses."""
    if len(a)<n+1:return None
    gains=[]; losses=[]
    for i in range(1,len(a)):
        d=a[i]-a[i-1]; gains.append(max(d,0.0)); losses.append(max(-d,0.0))
    ag=sum(gains[:n])/n; al=sum(losses[:n])/n
    for g,l in zip(gains[n:],losses[n:]):
        ag=(ag*(n-1)+g)/n; al=(al*(n-1)+l)/n
    if al==0 and ag==0:return 50.0
    if al==0:return 100.0
    if ag==0:return 0.0
    rs=ag/al
    return 100-100/(1+rs)
def macd(a):
    if len(a)<35:return None,None
    line=ema(a,12)-ema(a,26); vals=[]
    for i in range(26,len(a)): vals.append(ema(a[:i+1],12)-ema(a[:i+1],26))
    return line,ema(vals,9)
def adx(h,l,c,n=14):
    """Wilder ADX: Wilder-smoothed TR/+DM/-DM, then Wilder-smoothed DX."""
    if len(c)<2*n+1:return None
    tr=[]; plus=[]; minus=[]
    for i in range(1,len(c)):
        tr.append(max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])))
        up=h[i]-h[i-1]; dn=l[i-1]-l[i]
        plus.append(up if up>dn and up>0 else 0.0)
        minus.append(dn if dn>up and dn>0 else 0.0)
    atr=sum(tr[:n])/n; ps=sum(plus[:n])/n; ms=sum(minus[:n])/n
    dx=[]
    def dx_value(a,p,m):
        pdi=100*p/max(a,1e-12); mdi=100*m/max(a,1e-12)
        return 100*abs(pdi-mdi)/max(pdi+mdi,1e-12)
    dx.append(dx_value(atr,ps,ms))
    for i in range(n,len(tr)):
        atr=(atr*(n-1)+tr[i])/n; ps=(ps*(n-1)+plus[i])/n; ms=(ms*(n-1)+minus[i])/n
        dx.append(dx_value(atr,ps,ms))
    if len(dx)<n:return None
    adx_val=sum(dx[:n])/n
    for x in dx[n:]: adx_val=(adx_val*(n-1)+x)/n
    return adx_val


def pct_change(a,n=1):
    return ((a[-1]/a[-1-n])-1)*100 if len(a)>n and a[-1-n] else 0

def stoch_rsi(a,n=14):
    if len(a)<n*2+2:return None
    vals=[]
    for i in range(n,len(a)):
        rr=rsi(a[:i+1],n)
        if rr is not None: vals.append(rr)
    if len(vals)<n:return None
    lo=min(vals[-n:]); hi=max(vals[-n:]); return (vals[-1]-lo)/(hi-lo) if hi>lo else 0.5

def bollinger(a,n=20,k=2):
    if len(a)<n:return None,None,None
    m=sma(a,n); sd=(sum((x-m)**2 for x in a[-n:])/n)**0.5
    return m+k*sd,m,m-k*sd

def atr(h,l,c,n=14):
    """Wilder ATR (RMA of true range)."""
    if len(c)<n+1:return None
    tr=[max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])) for i in range(1,len(c))]
    a=sum(tr[:n])/n
    for x in tr[n:]: a=(a*(n-1)+x)/n
    return a

def true_range_ratio(h,l,c,n=14):
    a=atr(h,l,c,n); return a/c[-1]*100 if a and c[-1] else None


def ichimoku(h,l,c):
    """Standard Ichimoku values with the cloud correctly displaced 26 periods."""
    if len(c)<78: return None
    def midpoint(i,n):
        if i+1<n: return None
        hh=max(h[i-n+1:i+1]); ll=min(l[i-n+1:i+1]); return (hh+ll)/2
    i=len(c)-1
    tenkan=midpoint(i,9); kijun=midpoint(i,26)
    # Senkou spans visible at the current candle were calculated 26 candles earlier.
    cloud_i=i-26
    if cloud_i<51: return None
    t26=midpoint(cloud_i,9); k26=midpoint(cloud_i,26); a26=(t26+k26)/2; b26=midpoint(cloud_i,52)
    top=max(a26,b26); bottom=min(a26,b26)
    return {'tenkan':tenkan,'kijun':kijun,'span_a':a26,'span_b':b26,'cloud_top':top,'cloud_bottom':bottom,
            'bullish':c[-1]>top,'above_cloud':c[-1]>top,'below_cloud':c[-1]<bottom,
            'cloud_bullish':a26>b26}

def _rma(values,n):
    if len(values)<n: return None
    x=sum(values[:n])/n
    for v in values[n:]: x=(x*(n-1)+v)/n
    return x

def supertrend(h,l,c,n=10,mult=3.0):
    """Standard ATR-RMA Supertrend with recursive final bands."""
    if len(c)<n+2: return None
    tr=[0.0]
    for i in range(1,len(c)):
        tr.append(max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])))
    atrs=[None]*len(c); atrs[n-1]=_rma(tr[1:n],n-1) if len(tr[1:n])>=n-1 else None
    # Seed using the first n true ranges, then Wilder RMA.
    if len(tr)>=n+1:
        atrs[n]=sum(tr[1:n+1])/n
        for i in range(n+1,len(c)): atrs[i]=(atrs[i-1]*(n-1)+tr[i])/n
    fu=[None]*len(c); fl=[None]*len(c); st=[None]*len(c); direction=[0]*len(c)
    for i in range(n,len(c)):
        mid=(h[i]+l[i])/2; bu=mid+mult*atrs[i]; bl=mid-mult*atrs[i]
        if i==n:
            fu[i]=bu; fl[i]=bl; st[i]=bl if c[i]>=bl else bu
        else:
            fu[i]=bu if bu<fu[i-1] or c[i-1]>fu[i-1] else fu[i-1]
            fl[i]=bl if bl>fl[i-1] or c[i-1]<fl[i-1] else fl[i-1]
            if st[i-1]==fu[i-1]: st[i]=fl[i] if c[i]>fu[i] else fu[i]
            else: st[i]=fu[i] if c[i]<fl[i] else fl[i]
        direction[i]=1 if c[i]>=st[i] else -1
    return {'line':st[-1],'direction':direction[-1],'bullish':direction[-1]>0,'atr':atrs[-1]}

def candle_patterns(o,h,l,c):
    if len(c)<3:return {}
    i=-1; body=abs(c[i]-o[i]); rng=max(h[i]-l[i],1e-9); upper=h[i]-max(o[i],c[i]); lower=min(o[i],c[i])-l[i]
    prev_body=abs(c[-2]-o[-2]);
    doji=body/rng<0.12
    hammer=lower>=body*2 and upper<=max(body, rng*0.15) and c[i]>=o[i]
    bullish_engulf=c[i]>o[i] and c[-2]<o[-2] and c[i]>=o[-2] and o[i]<=c[-2]
    morning=(c[-3]<o[-3] and abs(c[-2]-o[-2])<abs(c[-3]-o[-3])*0.5 and c[-1]>o[-1] and c[-1]>(o[-3]+c[-3])/2)
    return {'doji':doji,'hammer':hammer,'engulfing':bullish_engulf,'morning_star':morning}

def recent_cross(a,b):
    if len(a)<2 or len(b)<2 or a[-2] is None or b[-2] is None:return False
    return a[-2]<=b[-2] and a[-1]>b[-1]

def _prefix_cross(a, n1, n2):
    if len(a)<n2+2:return False
    return ema(a[:-1],n1) is not None and ema(a[:-1],n2) is not None and ema(a[:-1],n1)<=ema(a[:-1],n2) and ema(a,n1)>ema(a,n2)

def _sma_cross(a,n1,n2):
    if len(a)<n2+2:return False
    return sma(a[:-1],n1)<=sma(a[:-1],n2) and sma(a,n1)>sma(a,n2)

def scan_models(d):
    o,h,l,c,v=d['open'],d['high'],d['low'],d['close'],d['volume']; last=c[-1]
    e9,e10,e20,e21,e50,e200=ema(c,9),ema(c,10),ema(c,20),ema(c,21),ema(c,50),ema(c,200)
    s50,s200=sma(c,50),sma(c,200); rr=rsi(c); sr=stoch_rsi(c); ml,ms=macd(c); ax=adx(h,l,c); vr=v[-1]/max(sma(v,20) or 1,1)
    # 52-week reference must exclude the current completed bar to avoid self-inclusion.
    prev52_close=c[-253:-1] if len(c)>=253 else c[:-1]
    prev52_high=h[-253:-1] if len(h)>=253 else h[:-1]
    prev52_low=l[-253:-1] if len(l)>=253 else l[:-1]
    hi52=max(prev52_high) if prev52_high else last; lo52=min(prev52_low) if prev52_low else last; bb_u,bb_m,bb_l=bollinger(c); pat=candle_patterns(o,h,l,c)
    mom=pct_change(c,20); mom5=pct_change(c,5); atrp=true_range_ratio(h,l,c); ichi=ichimoku(h,l,c); st=supertrend(h,l,c)
    models={}
    models['Özel Filtre']=bool(s50 and last>s50 and rr is not None and rr>40 and vr>=1.2)
    models['10/50 Crossover']=_prefix_cross(c,10,50)
    models['Golden Cross']=_sma_cross(c,50,200)
    models['52H Kırılım']=bool(len(c)>=253 and last>hi52 and vr>=1.5)
    models['Akıllı Para Proxy']=bool(vr>=2 and last>(e20 or last) and mom5>=2)
    models['Tavan Tarama']=bool(mom5>=9.5)
    models['Ucuz Kalmış']=bool(rr is not None and rr<35 and last<=(s50 or last)*1.02)
    models['Hacimlenen Dip']=bool(rr is not None and rr<34 and vr>=1.5 and last>lo52*1.02)
    models['Momentum Bombası']=bool(mom5>=3 and vr>=2 and rr is not None and 55<=rr<=75)
    models['Destek Kalkanı']=bool(s200 and last>s200 and rr is not None and rr<40)
    models['Bollinger Sıkışma']=bool(bb_u and bb_l and bb_m and (bb_u-bb_l)/bb_m<0.10 and last>=bb_m)
    models['Stoch RSI']=bool(sr is not None and sr<0.2 and mom5>=0)
    # Real MACD crossover: previous MACD <= previous signal and current MACD > current signal.
    if len(c)>=40:
        pm,ps=macd(c[:-1]); models['MACD Kesişimi']=bool(pm is not None and ps is not None and ml is not None and ms is not None and pm<=ps and ml>ms)
    else: models['MACD Kesişimi']=False
    models['Doji']=bool(pat.get('doji')); models['Hammer']=bool(pat.get('hammer'))
    models['Supertrend']=bool(st and st['bullish'] and mom5>0)
    models['EMA Crossover']=_prefix_cross(c,9,21)
    models['ADX Güçlü Trend']=bool(ax is not None and ax>25 and mom5>0)
    models['Morning Star']=bool(pat.get('morning_star')); models['Engulfing']=bool(pat.get('engulfing'))
    models['Değer + Momentum']=bool(rr is not None and 40<=rr<=60 and mom>0 and last>(e50 or last))
    models['Ichimoku Bulutu']=bool(ichi and ichi['above_cloud'] and ichi['tenkan']>ichi['kijun'])
    models['Qullamaggie']=bool(len(c)>=253 and last>hi52 and mom>0 and vr>=1.2)
    models['Minervini Trend']=bool(s50 and s200 and last>s50>s200 and mom>0 and vr>=1)
    models['Bulkowski Formasyon']=bool(pat.get('hammer') or pat.get('engulfing') or pat.get('morning_star'))
    models['RSI Trend Kırılımı']=bool(rr is not None and 45<rr<65 and mom5>0 and last>(e20 or last))
    prev_rr=rsi(c[:-1]) if len(c)>20 else None
    models['Pozitif Uyuşmazlık']=bool(len(c)>10 and c[-1]<=min(c[-10:]) and rr is not None and prev_rr is not None and rr>prev_rr)
    return models

def signal_score(d):
    """Single source of truth for FurkAI technical strength (0-100, not win probability)."""
    c,h,v=d['close'],d['high'],d['volume']; last=c[-1]
    e20,e50=ema(c,20),ema(c,50); s50,s200=sma(c,50),sma(c,200); rr=rsi(c); ml,ms=macd(c); ax=adx(h,d['low'],c); vr=v[-1]/max(sma(v,20) or 1,1); mom=pct_change(c,20); prev52_high=h[-253:-1] if len(h)>=253 else h[:-1]; hi=max(prev52_high) if prev52_high else last
    checks={
        'trend':bool(e20 and e50 and last>e20>e50),
        'long_term':bool(s50 and s200 and s50>s200),
        'golden':_sma_cross(c,50,200),
        'rsi':bool(rr is not None and rr<=70), 'volume':vr>=1.2,
        'breakout':bool(len(c)>=253 and last>hi), 'momentum':mom>0,
        'macd':bool(ml is not None and ms is not None and ml>ms), 'adx':bool(ax is not None and ax>=20)}
    weights={'trend':15,'long_term':10,'golden':10,'rsi':10,'volume':15,'breakout':10,'momentum':10,'macd':10,'adx':10}
    score=sum(weights[k] for k,x in checks.items() if x)
    breakdown={'Trend':weights['trend'] if checks['trend'] else 0,'Uzun Vade Trend':weights['long_term'] if checks['long_term'] else 0,'Golden Cross':weights['golden'] if checks['golden'] else 0,'RSI':weights['rsi'] if checks['rsi'] else 0,'Hacim/Akış':weights['volume'] if checks['volume'] else 0,'Breakout':weights['breakout'] if checks['breakout'] else 0,'Momentum':weights['momentum'] if checks['momentum'] else 0,'MACD':weights['macd'] if checks['macd'] else 0,'ADX':weights['adx'] if checks['adx'] else 0}
    return score,checks,breakdown

def analyze(symbol,period='1y'):
    d=history(symbol,period); c=d['close']; h=d['high']; l=d['low']; v=d['volume']; last=c[-1]
    score,checks,breakdown=signal_score(d); e20,e50=ema(c,20),ema(c,50); s50,s200=sma(c,50),sma(c,200); rr=rsi(c); ml,ms=macd(c); ax=adx(h,l,c); atrv=atr(h,l,c); vr=v[-1]/max(sma(v,20) or 1,1); mom=pct_change(c,20); ichi=ichimoku(h,l,c); st=supertrend(h,l,c)
    models=scan_models(d); active_models=[k for k,vv in models.items() if vv]
    return {'symbol':d['symbol'],'price':last,'signal_timestamp':d['timestamp'][-1],'score':score,'signal':'AL' if score>=70 else ('IZLE' if score>=50 else 'BEKLE'),'trend':'Yükseliş' if checks['trend'] else 'Karışık','rsi':rr,'ema20':e20,'ema50':e50,'sma50':s50,'sma200':s200,'volume_ratio':vr,'macd':ml,'macd_signal':ms,'adx':ax,'atr':atrv,'momentum':mom,'checks':checks,'models':models,'active_models':active_models,'score_breakdown':breakdown,'ichimoku':ichi,'supertrend':st,'score_note':'Teknik sinyal gücü; kâr olasılığı değildir.'}

def record_signals(rows,models):
    if not rows:return
    c=db()
    for x in rows:
        selected=[m for m in models if x.get('models',{}).get(m)] if models else list(x.get('active_models',[]))
        # A score-only scan is still a meaningful signal and must be persisted.
        # Keep the provenance explicit instead of inventing a technical model.
        if not selected:
            selected=['FurkAI Score']
        # avoid duplicate signal entries for the same symbol/models on the signal day
        selected=sorted(dict.fromkeys(selected), key=str)
        key=','.join(selected)
        signal_ts=int(x.get('signal_timestamp') or 0)
        if not signal_ts: continue
        local_dt=datetime.fromtimestamp(signal_ts,BIST_TZ)
        day_start=local_dt.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
        day_end=day_start+86400
        exists=c.execute('SELECT id FROM signal_history WHERE symbol=? AND models=? AND ts>=? AND ts<? ORDER BY id DESC LIMIT 1',(x['symbol'].replace('.IS',''),key,day_start,day_end)).fetchone()
        if not exists:
            c.execute('INSERT INTO signal_history(ts,symbol,models,entry,score) VALUES(?,?,?,?,?)',(signal_ts,x['symbol'].replace('.IS',''),key,float(x['price']),float(x['score'])))
    c.commit(); c.close()

def _historical_return_at(symbol, signal_ts, days):
    """Return the close exactly N completed trading bars after the signal bar."""
    try:
        d=history(symbol,'5y'); ts=d['timestamp']; closes=d['close']
        if not ts or len(ts)!=len(closes): return None
        # Signals are stamped with the actual completed daily candle timestamp.
        try: idx=ts.index(int(signal_ts))
        except ValueError:
            # Be tolerant of timestamp normalization by selecting the latest bar
            # not later than the stored signal timestamp.
            candidates=[i for i,t in enumerate(ts) if t<=int(signal_ts)]
            if not candidates: return None
            idx=candidates[-1]
        target=idx+int(days)
        return closes[target] if target < len(closes) else None
    except Exception:
        return None

def signal_history(limit=200,symbol=None):
    c=db(); params=[]; sql='SELECT * FROM signal_history'
    if symbol: sql+=' WHERE symbol=?'; params.append(symbol.replace('.IS','').upper())
    sql+=' ORDER BY ts DESC LIMIT ?'; params.append(min(max(int(limit),1),1000)); rows=[dict(r) for r in c.execute(sql,params)]; c.close()
    if not rows:return {'ok':True,'signals':[]}
    syms=list(dict.fromkeys(r['symbol'] for r in rows)); qs=quotes(syms)['quotes']; out=[]; updates=[]
    for r in rows:
        q=qs.get(r['symbol']); current=q['price'] if q else None; r['current']=current; r['return_pct']=((current/r['entry'])-1)*100 if current and r['entry'] else None
        for days,key in ((1,'ret_1d'),(5,'ret_5d'),(20,'ret_20d')):
            if r.get(key) is None:
                future=_historical_return_at(r['symbol'],r['ts'],days)
                if future is not None: r[key]=(future/r['entry']-1)*100; updates.append((r[key],r['id'],key))
        r['horizons']={'1d':r.get('ret_1d'),'5d':r.get('ret_5d'),'20d':r.get('ret_20d')}
        r['horizon_status']={k:('ready' if r.get(k) is not None else 'pending') for k in ('ret_1d','ret_5d','ret_20d')}
        r['date']=datetime.fromtimestamp(r['ts'],BIST_TZ).strftime('%Y-%m-%d %H:%M'); out.append(r)
    if updates:
        c=db()
        for val,rid,key in updates: c.execute(f'UPDATE signal_history SET {key}=? WHERE id=? AND {key} IS NULL',(val,rid))
        c.commit(); c.close()
    return {'ok':True,'signals':out}

def _models_match(model_flags, selected, mode='AND', min_models=None):
    """Evaluate multi-model scanner semantics.

    AND means every selected model must match. OR means at least one selected
    model must match by default. An explicit min_models can tighten OR to a
    requested threshold, but it can never exceed the number of selected models.
    """
    selected=list(selected or [])
    if not selected:
        return True, []
    matched=[m for m in selected if bool(model_flags.get(m))]
    mode=str(mode or 'AND').upper()
    if mode == 'OR':
        threshold=1 if min_models is None else max(1, min(int(min_models), len(selected)))
        return len(matched)>=threshold, matched
    return len(matched)==len(selected), matched

def scan(body):
    u=universe(); symbols=[str(s).upper().replace('.IS','') for s in body.get('symbols',u['symbols']) if str(s).upper().replace('.IS','') in u['symbols']]
    limit=min(700,max(1,int(body.get('limit',DEFAULT['scanner_limit'])))); symbols=list(dict.fromkeys(symbols))[:limit]; minimum=max(0,min(100,int(body.get('minimum_score',60))))
    period=body.get('period','1y') if body.get('period','1y') in ('6mo','1y','2y','5y') else '1y'; rows=[]; errors=[]
    selected=[str(x) for x in body.get('models',[])][:27]; mode=body.get('mode','AND').upper(); explicit_min=body.get('min_models',None); min_models=None if explicit_min in (None,'') else max(1,int(explicit_min))
    try: history('THYAO',period)
    except Exception as e: return {'ok':True,'data_available':False,'error':'Yahoo veri sağlayıcısına erişilemiyor: '+str(e),'results':[],'universe_source':u['source']}
    with ThreadPoolExecutor(max_workers=12) as ex:
        fm={ex.submit(analyze,s,period):s for s in symbols}
        for f in as_completed(fm):
            s=fm[f]
            try:
                x=f.result(); active=x['active_models']; ok,matched=_models_match(x['models'],selected,mode,min_models)
                if ok and x['score']>=minimum:
                    x['selected_models']=matched; rows.append(x)
            except Exception as e: errors.append({'symbol':s,'error':str(e)[:140]})
    rows.sort(key=lambda x:(-x['score'],-(x['volume_ratio'] or 0),x['symbol']))
    record_signals(rows,selected)
    return {'ok':True,'data_available':True,'results':rows,'scanned':len(symbols)-len(errors),'requested':len(symbols),'errors':errors,'universe_source':u['source'],'selected_models':selected,'mode':mode,'min_models':min_models}

def backtest(symbol,days=365,initial=100000):
    """Long-only BIST backtest with explicit, non-look-ahead execution rules.

    Rules:
      * A signal is known only after a completed daily close.
      * A new entry is executed at the following session OPEN.
      * A signal-based exit is also executed at the following session OPEN.
      * Existing positions are checked against that session's HIGH/LOW for the stop.
      * If the session gaps through the stop, execution is at the session OPEN.
      * If both a stop and a signal-exit are pending for the same session, STOP wins.
      * No signal generated from a future candle is used to execute an earlier trade.
      * Exactly ``days`` completed daily decision bars are evaluated; the final
        decision's order is not executed because its next session lies outside the
        requested horizon.
    """
    days=max(30,min(int(days),730))
    initial=float(initial)
    if not math.isfinite(initial) or initial<=0: raise ValueError('Başlangıç sermayesi pozitif olmalı')

    # 5y gives enough room for 200-bar warm-up + the requested horizon + one
    # execution bar, without fragile period thresholds. We still verify the exact
    # number of usable bars below.
    period='5y'; warmup=200; required=warmup+days+1
    raw=history(symbol,period); n=len(raw['close'])
    if n < required:
        raise RuntimeError(f'Backtest için yeterli geçmiş veri yok: {days} simülasyon günü + {warmup} günlük indikatör ısınma verisi + 1 execution günü gerekiyor, sağlayıcı {n} gün verdi')

    # Use the most recent exact window: 200 warm-up bars + N decision bars +
    # one bar reserved for execution of the final in-horizon decision.
    start=n-required
    d={k:(v[start:] if isinstance(v,list) else v) for k,v in raw.items()}
    if len(d['close']) != required: raise RuntimeError('Backtest veri penceresi beklenenden farklı')

    cash=initial; qty=0.0; entry=0.0; stop=0.0; trades=[]; equity=[]
    peak=initial; max_dd=0.0; fee=0.0008
    # Pending orders are created only after a completed decision candle.
    pending_entry=False; pending_exit=False; pending_atr=0.0

    # Decision bars: [warmup, warmup+days-1]. Their next bars are the execution
    # sessions. The final decision has a reserved next bar but no subsequent
    # decision inside the requested horizon.
    for i in range(warmup, warmup+days):
        decision_sub={k:v[:i+1] for k,v in d.items() if isinstance(v,list)}

        # 1) Execute orders generated from the PREVIOUS completed close, at today's
        # open. This is the only place a new entry/close signal is executed.
        exec_i=i
        day_open=d['open'][exec_i]; day_high=d['high'][exec_i]; day_low=d['low'][exec_i]; day_close=d['close'][exec_i]

        if pending_exit and qty:
            # Stop is evaluated on the execution session. A gap below stop is
            # filled at open; otherwise the protective stop level is executable.
            if day_low <= stop:
                exit_price=day_open if day_open < stop else stop
                proceeds=qty*exit_price*(1-fee)
                pnl=proceeds-(qty*entry*(1+fee)); cash+=proceeds
                trades.append({'entry':entry,'exit':exit_price,'pnl':pnl,'reason':'STOP','entry_index':exec_i})
            else:
                exit_price=day_open
                proceeds=qty*exit_price*(1-fee)
                pnl=proceeds-(qty*entry*(1+fee)); cash+=proceeds
                trades.append({'entry':entry,'exit':exit_price,'pnl':pnl,'reason':'SIGNAL_EXIT_OPEN','entry_index':exec_i})
            qty=0.0; entry=0.0; stop=0.0; pending_exit=False

        elif qty:
            # Existing position: protective stop can trigger intraday. No future
            # close is consulted before the stop decision.
            if day_low <= stop:
                exit_price=day_open if day_open < stop else stop
                proceeds=qty*exit_price*(1-fee)
                pnl=proceeds-(qty*entry*(1+fee)); cash+=proceeds
                trades.append({'entry':entry,'exit':exit_price,'pnl':pnl,'reason':'STOP','entry_index':exec_i})
                qty=0.0; entry=0.0; stop=0.0

        if pending_entry and qty==0:
            # Entry is sized from information available at the previous close.
            # pending_entry_price/atr were captured then; no today's high/low/close
            # participates in sizing.
            entry=day_open
            risk_cash=cash*0.01
            risk_per_share=max(2*pending_atr,entry*0.005)
            qty=min(risk_cash/risk_per_share,(cash*0.25)/entry) if entry>0 else 0
            if qty>0:
                stop=entry-2*pending_atr
                cash-=qty*entry*(1+fee)
                # If the entry session itself hits the protective stop, it is a
                # legitimate same-session stop and is handled with only OHLC data.
                if day_low <= stop:
                    exit_price=day_open if day_open < stop else stop
                    proceeds=qty*exit_price*(1-fee)
                    pnl=proceeds-(qty*entry*(1+fee)); cash+=proceeds
                    trades.append({'entry':entry,'exit':exit_price,'pnl':pnl,'reason':'ENTRY_SESSION_STOP','entry_index':exec_i})
                    qty=0.0; entry=0.0; stop=0.0
            pending_entry=False

        # Mark equity only with today's close, after all execution decisions.
        equity_now=cash+(qty*day_close if qty else 0.0)
        equity.append(equity_now); peak=max(peak,equity_now)
        max_dd=max(max_dd,(peak-equity_now)/peak*100 if peak else 0.0)

        # 2) Only AFTER today's candle has completely closed do we generate the
        # order for the next session. The next session is inside the dataset for
        # every decision bar, but the final decision's order is intentionally not
        # executed within the requested N-day horizon.
        score,_,_=signal_score(decision_sub)
        a=atr(decision_sub['high'],decision_sub['low'],decision_sub['close'],14) or day_close*0.03
        if qty:
            if score < 50:
                pending_exit=True
            else:
                pending_exit=False
        elif score >= 70:
            pending_entry=True
            pending_atr=a
        else:
            pending_entry=False

    # Do NOT execute a pending order generated by the final decision bar: its
    # execution belongs to the next session outside the requested horizon.
    # If a position remains open, mark it to the final in-horizon close but do not
    # manufacture an exit trade at that same close.
    final=d['close'][warmup+days-1]
    final_equity=cash+(qty*final if qty else 0.0)
    if equity: equity[-1]=final_equity
    peak=max(peak,final_equity); max_dd=max(max_dd,(peak-final_equity)/peak*100 if peak else 0.0)

    wins=[t['pnl'] for t in trades if t['pnl']>0]; losses=[t['pnl'] for t in trades if t['pnl']<0]
    gross_win=sum(wins); gross_loss=abs(sum(losses))
    pf=(gross_win/gross_loss) if gross_loss else (float('inf') if gross_win else 0)
    expectancy=(sum(t['pnl'] for t in trades)/len(trades)) if trades else 0
    # Benchmark and risk-adjusted metrics. Keep benchmark independent from strategy execution.
    benchmark_return=None; alpha=None; sharpe=None; sortino=None; cagr=None; benchmark_curve=[]; buy_hold_curve=[]
    try:
        bd=history('^XU100','5y'); bcl=bd['close']; bts=bd.get('timestamp',[])
        bstart=max(0,len(bcl)-days-1)
        if bcl and bcl[bstart]>0:
            benchmark_return=(bcl[-1]/bcl[bstart]-1)*100; alpha=(final_equity/initial-1)*100-benchmark_return
            bench_slice=bcl[bstart:bstart+len(equity)]
            if bench_slice:
                b0=bench_slice[0]
                benchmark_curve=[{'ts':int(bts[bstart+i]) if bstart+i<len(bts) else i,'value':float(initial*(v/b0))} for i,v in enumerate(bench_slice)]
        sym_start=warmup
        closes=d['close'][sym_start:sym_start+len(equity)]
        if closes:
            c0=closes[0]
            buy_hold_curve=[{'ts':int(d.get('timestamp',[i for i in range(len(d['close']))])[sym_start+i]),'value':float(initial*(v/c0))} for i,v in enumerate(closes)]
    except Exception: pass
    if len(equity)>2:
        rets=[equity[i]/equity[i-1]-1 for i in range(1,len(equity)) if equity[i-1]]
        if rets:
            mean=sum(rets)/len(rets); var=sum((r-mean)**2 for r in rets)/max(1,len(rets)-1); sd=math.sqrt(var)
            sharpe=(mean/sd)*math.sqrt(252) if sd else None
            neg=[r for r in rets if r<0]; dsd=math.sqrt(sum(r*r for r in neg)/max(1,len(neg))) if neg else 0
            sortino=(mean/dsd)*math.sqrt(252) if dsd else None
    if days>0: cagr=((final_equity/initial)**(252/max(days,1))-1)*100 if final_equity>0 and initial>0 else None
    return {
        'ok':True,'symbol':symbol.upper(),'initial':initial,'final':final_equity,'return_pct':(final_equity/initial-1)*100,'benchmark_return_pct':benchmark_return,'alpha_pct':alpha,'sharpe':sharpe,'sortino':sortino,'cagr_pct':cagr,
        'trades':len(trades),'win_rate':len(wins)/max(1,len(trades))*100,
        'profit_factor':pf,'expectancy':expectancy,'max_drawdown_pct':max_dd,
        'equity_curve':[{'ts':int(d.get('timestamp',[i for i in range(len(d['close']))])[warmup+i]),'value':float(v)} for i,v in enumerate(equity)],'benchmark_curve':benchmark_curve,'buy_hold_curve':buy_hold_curve,
        'period_days':days,'requested_days':days,'period_source':period,'side':'LONG_ONLY',
        'note':'Long-only backtest. Sinyal yalnızca tamamlanmış günlük kapanıştan sonra hesaplanır; giriş ve sinyal bazlı çıkış bir sonraki seans açılışında gerçekleşir. Koruyucu stop execution seansının LOW değerinde kontrol edilir; gap-through-stop açılıştan gerçekleşir. Son kararın emri test penceresi dışındaki güne taşmaz. Son açık pozisyon yalnızca son gün kapanışında mark-to-market edilir; aynı kapanıştan yapay çıkış yazılmaz. Komisyon ve risk bazlı pozisyon boyutlandırma dahildir. Günlük OHLC verisinde aynı candle içindeki SL/TP sırası kesin bilinmediğinden yalnızca koruyucu stop modellenir.'
    }

# ---------- Portfolio Intelligence ----------
def portfolio_intelligence():
    rows=load_portfolio(); out=[]
    for p in rows:
        sym=p['symbol']
        try:
            a=analyze(sym,'1y')
            score=float(a.get('score') or 0)
            if score>=75: action='TUT / GÜÇLÜ'
            elif score>=60: action='İZLE'
            elif score>=45: action='DİKKAT'
            else: action='RİSK / AZALT'
            atr_pct=((a.get('atr') or 0)/max(a.get('price') or 1,1))*100 if a.get('atr') is not None else None
            vol_risk='YÜKSEK' if atr_pct is not None and atr_pct>=5 else ('ORTA' if atr_pct is not None and atr_pct>=2.5 else 'DÜŞÜK')
            score_risk='DÜŞÜK' if score>=75 else ('ORTA' if score>=55 else 'YÜKSEK')
            risk='YÜKSEK' if 'YÜKSEK' in (vol_risk,score_risk) else ('ORTA' if 'ORTA' in (vol_risk,score_risk) else 'DÜŞÜK')
            q=quote(sym)
            price=q.get('price') if isinstance(q,dict) else None
            pnl=((price-p['cost'])*p['qty']) if price is not None else None
            weight=None
            out.append({'id':p['id'],'symbol':sym,'qty':p['qty'],'cost':p['cost'],'price':price,'pnl':pnl,'score':score,'signal':a.get('signal'),'trend':a.get('trend'),'risk':risk,'action':action,'rsi':a.get('rsi'),'momentum':a.get('momentum'),'volume_ratio':a.get('volume_ratio'),'atr_pct':atr_pct,'active_models':a.get('active_models',[])})
        except Exception as e:
            out.append({'id':p['id'],'symbol':sym,'qty':p['qty'],'cost':p['cost'],'price':None,'pnl':None,'score':None,'signal':'VERİ YOK','trend':'—','risk':'BİLİNMİYOR','action':'VERİ YOK','error':str(e)})
    total_value=sum((x.get('qty',0)*(x.get('price') or 0)) for x in out)
    for x in out: x['weight']=(x['qty']*(x['price'] or 0)/total_value*100) if total_value else None
    for x in out:
        w=x.get('weight') or 0
        atrp=x.get('atr_pct')
        factors=[]
        if x.get('score') is not None and x['score']<55: factors.append('DÜŞÜK_SKOR')
        if atrp is not None and atrp>=5: factors.append('YÜKSEK_VOLATİLİTE')
        if w>=20: factors.append('YÜKSEK_POZİSYON_AĞIRLIĞI')
        if x.get('rsi') is not None and x['rsi']>=75: factors.append('AŞIRI_ALIM')
        x['risk_factors']=factors
        if 'YÜKSEK_VOLATİLİTE' in factors or 'YÜKSEK_POZİSYON_AĞIRLIĞI' in factors or 'DÜŞÜK_SKOR' in factors: x['risk']='YÜKSEK'
        elif atrp is not None and atrp>=2.5: x['risk']='ORTA'
        else: x['risk']='DÜŞÜK'
    out.sort(key=lambda x:(x.get('score') is None, -(x.get('score') or 0)))
    alerts=[x for x in out if x.get('risk')=='YÜKSEK']
    # Diversification is based on recent daily-return correlation of the current holdings.
    corr_pairs=[]; corr_vals=[]
    try:
        series={}
        for x in out:
            try:
                hd=history(x['symbol'],'6mo','1d'); closes=hd['close']; rets=[closes[i]/closes[i-1]-1 for i in range(1,len(closes)) if closes[i-1]]
                if len(rets)>=30: series[x['symbol']]=rets[-60:]
            except Exception: pass
        syms=list(series)
        for i in range(len(syms)):
            for j in range(i+1,len(syms)):
                a,b=series[syms[i]],series[syms[j]]; n=min(len(a),len(b)); a=a[-n:]; b=b[-n:]
                ma=sum(a)/n; mb=sum(b)/n; va=sum((z-ma)**2 for z in a); vb=sum((z-mb)**2 for z in b)
                if va and vb:
                    corr=sum((a[k]-ma)*(b[k]-mb) for k in range(n))/math.sqrt(va*vb); corr_vals.append(corr); corr_pairs.append({'a':syms[i],'b':syms[j],'corr':corr})
        avg_abs=(sum(abs(z) for z in corr_vals)/len(corr_vals)) if corr_vals else None
        diversification_score=(100*(1-avg_abs)) if avg_abs is not None else None
        diversification_label='YÜKSEK' if diversification_score is not None and diversification_score>=70 else ('ORTA' if diversification_score is not None and diversification_score>=45 else ('DÜŞÜK' if diversification_score is not None else 'BİLİNMİYOR'))
    except Exception:
        diversification_score=None; diversification_label='BİLİNMİYOR'; corr_pairs=[]
    return {'ok':True,'positions':out,'alerts':alerts,'total_value':total_value,'alert_count':len(alerts),'diversification_score':diversification_score,'diversification_label':diversification_label,'correlations':sorted(corr_pairs,key=lambda z:-abs(z['corr']))[:10]}

def market_regime():
    try:
        d=history('^XU100','1y','1d'); c=d['close']; h=d['high']; l=d['low'];
        e20=ema(c,20); e50=ema(c,50); rr=rsi(c); ax=adx(h,l,c); mom=pct_change(c,20); vol=true_range_ratio(h,l,c)
        points=0; reasons=[]
        if c[-1]>e20[-1]: points+=1; reasons.append('Fiyat EMA20 üzerinde')
        if e20[-1]>e50[-1]: points+=1; reasons.append('EMA20 > EMA50')
        if rr is not None and rr>=50: points+=1; reasons.append('RSI pozitif bölgede')
        if ax is not None and ax>=20: points+=1; reasons.append('ADX trendi destekliyor')
        if mom is not None and mom>0: points+=1; reasons.append('20G momentum pozitif')
        regime='POZİTİF' if points>=4 else ('NÖTR' if points>=2 else 'RİSKLİ')
        confidence=points/5*100
        return {'ok':True,'symbol':'^XU100','regime':regime,'confidence':confidence,'price':c[-1],'rsi':rr,'adx':ax,'momentum':mom,'volatility_pct':vol*100 if vol is not None else None,'reasons':reasons}
    except Exception as e:
        return {'ok':False,'regime':'VERİ YOK','confidence':None,'error':str(e)}

# ---------- KAP / company context ----------
KAP_HOME='https://www.kap.org.tr/tr'
KAP_SEARCH='https://www.kap.org.tr/tr/bildirim-sorgu'

def kap_info(symbol):
    sym=str(symbol).upper().replace('.IS','').strip()
    # KAP's licensed REST feed requires an authorized subscription/API key; do not scrape or invent disclosure data.
    # We expose the official public KAP search route and a safe company-context card instead.
    return {
        'ok':True, 'symbol':sym, 'source':'KAP resmi kamuya açık web arayüzü',
        'official_url':KAP_HOME, 'search_url':KAP_SEARCH,
        'message':"KAP bildirimlerinin resmi kaynağı KAP'tır. Otomatik bildirim akışı için yetkili KAP Veri Yayın Servisi entegrasyonu gerekir.",
        'categories':['Özel Durum Açıklaması','Finansal Rapor','Temettü / Hak Kullanımı','Sermaye İşlemleri','Genel Kurul','Geri Alım','BISTECH Devre Kesici'],
        'disclaimer':'KAP verisi için yetkili API yoksa uygulama bildirim uydurmaz.'
    }

# ---------- AI ----------
def gemini(prompt):
    key=DEFAULT.get('gemini_key','')
    if not key:return {'ok':False,'error':'Gemini API anahtarı yapılandırılmamış'}
    url=f'https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(DEFAULT.get("gemini_model","gemini-3.6-flash"))}:generateContent?key={urllib.parse.quote(key)}'
    payload={'contents':[{'parts':[{'text':prompt}]}]}
    try:
        d=http_json_post(url,payload); text=''.join(p.get('text','') for p in d.get('candidates',[{}])[0].get('content',{}).get('parts',[])); return {'ok':True,'text':text}
    except Exception as e:return {'ok':False,'error':str(e)}
def test_gemini():
    if not DEFAULT.get('gemini_key'): return {'ok':False,'configured':False,'error':'Gemini API anahtarı yapılandırılmamış'}
    r=gemini('Yalnızca OK yaz.')
    return {'ok':bool(r.get('ok')),'configured':True,'error':r.get('error')}

def http_json_post(url,payload):
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','User-Agent':'FurkAI-BIST/1.0'},method='POST')
    with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode())

# ---------- HTTP ----------
USER=os.environ.get('FURKAI_USER','furkai'); PASSWORD=os.environ.get('FURKAI_PASSWORD',''); REQUIRE_AUTH=os.environ.get('FURKAI_REQUIRE_AUTH','0')=='1'
def auth(h):
    if not REQUIRE_AUTH and not PASSWORD:return True
    if not PASSWORD:return False
    raw=h.get('Authorization','')
    try:
        u,p=base64.b64decode(raw[6:]).decode().split(':',1); return hmac.compare_digest(u,USER) and hmac.compare_digest(p,PASSWORD)
    except:return False
class Handler(BaseHTTPRequestHandler):
    def sendj(self,o,status=200):
        b=json.dumps(o,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p=urllib.parse.urlparse(self.path)
        if p.path in ('/','/index.html'):
            b=(BASE/'index.html').read_bytes(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b); return
        try:
            q=urllib.parse.parse_qs(p.query)
            if p.path=='/api/market-regime': return self.sendj(market_regime())
            if p.path=='/api/config': return self.sendj(public_config())
            if p.path=='/api/data-status': return self.sendj(data_status())
            if p.path=='/api/health': return self.sendj({'ok':True,'app':'FurkAI BIST','version':DEFAULT.get('app_version','15.0'),'source':'Yahoo Finance/KAP public data'})
            if p.path.startswith('/api/') and not auth(self.headers):
                self.send_response(401); self.send_header('WWW-Authenticate','Basic realm=\"FurkAI BIST\"'); self.end_headers(); return
            if p.path=='/api/universe': return self.sendj(universe())
            if p.path=='/api/quote': return self.sendj(quote(q.get('symbol',['THYAO'])[0]))
            if p.path=='/api/quotes': return self.sendj(quotes(q.get('symbols',['THYAO,ASELS,THYAO'])[0].split(',')))
            if p.path=='/api/history': return self.sendj({'ok':True,'data':history(q.get('symbol',['THYAO'])[0],q.get('range',['1y'])[0],q.get('interval',['1d'])[0])})
            if p.path=='/api/analyze': return self.sendj({'ok':True,'data':analyze(q.get('symbol',['THYAO'])[0],q.get('range',['1y'])[0])})
            if p.path=='/api/portfolio': return self.sendj({'ok':True,'portfolio':load_portfolio()})
            if p.path=='/api/portfolio/intelligence': return self.sendj(portfolio_intelligence())
            if p.path=='/api/backtest': return self.sendj(backtest(q.get('symbol',['THYAO'])[0],int(q.get('days',['365'])[0]),float(q.get('initial',['100000'])[0])))
            if p.path=='/api/kap': return self.sendj(kap_info(q.get('symbol',['THYAO'])[0]))
            if p.path=='/api/dividends':
                d=yahoo_chart(q.get('symbol',['THYAO'])[0],'5y','1d'); div=d.get('events',{}).get('dividends',{}); vals=[]
                for ts,x in div.items(): vals.append({'date':time.strftime('%Y-%m-%d',time.localtime(int(ts))),'amount':x.get('amount'),'symbol':d['symbol']})
                return self.sendj({'ok':True,'dividends':sorted(vals,key=lambda x:x['date'],reverse=True)})
            if p.path=='/api/scan': return self.sendj(scan({'period':q.get('range',['1y'])[0],'limit':int(q.get('limit',['200'])[0]),'minimum_score':int(q.get('min',['60'])[0]),'models':[x for x in q.get('models',[''])[0].split('|') if x],'mode':q.get('mode',['AND'])[0],'min_models':(q.get('min_models',[None])[0] if q.get('min_models',[None])[0] not in (None,'') else None)}))
            if p.path=='/api/signals': return self.sendj(signal_history(int(q.get('limit',['200'])[0]), q.get('symbol',[None])[0]))
            self.sendj({'ok':False,'error':'Not found'},404)
        except Exception as e:self.sendj({'ok':False,'error':str(e)},500)
    def do_POST(self):
        if not auth(self.headers): self.send_response(401); self.send_header('WWW-Authenticate','Basic realm="FurkAI BIST"'); self.end_headers(); return
        try:
            n=int(self.headers.get('Content-Length','0')); body=json.loads(self.rfile.read(n) or b'{}')
            if self.path=='/api/portfolio/save': save_portfolio(body.get('portfolio',[])); return self.sendj({'ok':True,'portfolio':load_portfolio()})
            if self.path=='/api/config':
                return self.sendj(save_config(body))
            if self.path=='/api/gemini-test': return self.sendj(test_gemini())
            if self.path=='/api/ai':
                sym=str(body.get('symbol','THYAO')).upper(); a=analyze(sym); prompt=body.get('prompt') or f'''BIST hissesi {sym} için yalnızca verilen teknik veriyi kullan. Veri uydurma. Cevabı SADECE geçerli JSON olarak üret: {{"decision":"GÜÇLÜ_ADAY|İZLE|NÖTR|RİSKLİ","confidence":0,"reasons":[],"risks":[],"suggested_entry":null,"stop":null,"target":null,"invalidate_reason":""}}. Sayısal seviyeler veriden güvenilir biçimde çıkarılamıyorsa null bırak. Teknik veri: {json.dumps(a,ensure_ascii=False)}'''; return self.sendj(gemini(prompt))
            if self.path=='/api/scan': return self.sendj(scan(body))
            self.sendj({'ok':False,'error':'Not found'},404)
        except Exception as e:self.sendj({'ok':False,'error':str(e)},500)

def main():
    db(); port=int(os.environ.get('PORT','8799')); print(f'FurkAI BIST running on :{port}'); ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
if __name__=='__main__':main()
