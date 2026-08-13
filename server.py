
import json, math, os, time, hmac, hashlib, base64, urllib.parse, urllib.request, threading, traceback, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

BASE=Path(__file__).resolve().parent
CFG=BASE/"config.json"
LOG=BASE/"furkai.log"
STATE={"running":False,"mode":"paper","last_scan":0,"last_error":None,"signals":{},"prices":{},
       "positions":[],"oi":{},"logs":[],"trade_log":[],"paper_balance":10000.0,
       "scan_thread":None,"scan_interval":30}
QUOTE_CACHE={}
HISTORY_CACHE={}
CACHE_LOCK=threading.RLock()
QUOTE_TTL=15
HISTORY_TTL=300

DEFAULT={
 "mode":"paper","api_key":"","api_secret":"","testnet":True,
 "gemini_key":"","gemini_model":"gemini-3.6-flash",
 "risk_per_trade":0.5,"max_daily_loss":2.0,"max_positions":2,"leverage":2,
 "min_score":5,"min_ai_confidence":70,"cooldown_min":15,
 "auto_execute_testnet":False
}

def load_cfg():
    global CFG
    if CFG.exists():
        try:
            x=json.loads(CFG.read_text(encoding="utf-8")); DEFAULT.update(x)
        except: pass
load_cfg()

def log(msg, kind="INFO"):
    line=time.strftime("%Y-%m-%d %H:%M:%S")+" ["+kind+"] "+msg
    STATE["logs"].insert(0,line); STATE["logs"]=STATE["logs"][:200]
    try: LOG.open("a",encoding="utf-8").write(line+"\n")
    except: pass

def save_cfg():
    CFG.write_text(json.dumps(DEFAULT,ensure_ascii=False,indent=2),encoding="utf-8")

def api_base():
    return "https://testnet.binancefuture.com" if DEFAULT["testnet"] else "https://fapi.binance.com"

def http_json(url, method="GET", data=None, timeout=12, headers=None):
    hdrs={"User-Agent":"Mozilla/5.0 FurkAI/41"}
    if headers: hdrs.update(headers)
    req=urllib.request.Request(url, method=method, headers=hdrs)
    if data is not None:
        req.data=json.dumps(data).encode("utf-8")
        req.add_header("Content-Type","application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8","ignore"))

def yahoo_chart(symbol, period="1y", interval="1d"):
    symbol=str(symbol).strip().upper()
    if symbol.isalpha() and not symbol.endswith(".IS") and symbol not in ("BTCUSDT","ETHUSDT","PAXGUSDT","XAUUSDT"):
        symbol += ".IS"
    key=(symbol,period,interval)
    now=time.time()
    with CACHE_LOCK:
        cached=HISTORY_CACHE.get(key)
        if cached and now-cached["ts"] < HISTORY_TTL:
            return cached["data"]
    last_error=None
    for host in ("query1.finance.yahoo.com","query2.finance.yahoo.com"):
        url=f"https://{host}/v8/finance/chart/{urllib.parse.quote(symbol)}?interval={urllib.parse.quote(interval)}&range={urllib.parse.quote(period)}&events=div%2Csplits"
        try:
            data=http_json(url, timeout=15, headers={"Accept":"application/json"})
            result=(data.get("chart") or {}).get("result") or []
            if not result: raise RuntimeError("Yahoo veri döndürmedi")
            r=result[0]
            out={"symbol":symbol,"meta":r.get("meta") or {},"quote":((r.get("indicators") or {}).get("quote") or [{}])[0],"timestamp":r.get("timestamp") or []}
            with CACHE_LOCK: HISTORY_CACHE[key]={"ts":now,"data":out}
            return out
        except Exception as exc: last_error=exc
    raise RuntimeError(f"Piyasa verisi alınamadı ({symbol}): {last_error}")

def yahoo_quote(symbol):
    clean=str(symbol).strip().upper()
    d=yahoo_chart(clean,"2d","1d"); meta=d["meta"]
    price=meta.get("regularMarketPrice")
    prev=meta.get("previousClose") or meta.get("chartPreviousClose")
    if price is None:
        raise RuntimeError("Güncel fiyat alanı boş; veri yokken 0 gösterilmeyecek")
    price=float(price); prev=float(prev) if prev is not None else None
    change=(price-prev) if prev is not None else None
    pct=(change/prev*100) if prev not in (None,0) and change is not None else None
    market_ts=meta.get("regularMarketTime")
    age=int(time.time()-market_ts) if market_ts else None
    return {"ok":True,"symbol":d["symbol"],"price":price,"previousClose":prev,"dailyChange":change,"dailyChangePct":pct,"timestamp":int(time.time()),"marketTimestamp":market_ts,"ageSeconds":age,"stale":bool(age is not None and age>900),"source":"server:yahoo","warning":"Yahoo gecikmeli olabilir" if age is None or age>120 else ""}

def yahoo_quotes(symbols):
    out={}; errors=[]
    unique=list(dict.fromkeys(str(x).strip().upper() for x in symbols if str(x).strip()))
    with ThreadPoolExecutor(max_workers=min(8,max(1,len(unique)))) as pool:
        fm={pool.submit(yahoo_quote,s):s for s in unique}
        for fut in as_completed(fm):
            sym=fm[fut]
            try: out[sym]=fut.result()
            except Exception as exc: errors.append({"symbol":sym,"error":str(exc)})
    return {"ok":True,"quotes":out,"errors":errors,"timestamp":int(time.time()),"source":"Yahoo server proxy","fresh":sum(1 for v in out.values() if not v.get("stale"))}

def binance_klines(symbol, limit=300, interval="1m"):
    symbol=str(symbol).upper()
    last=None
    urls=[
      f"https://testnet.binancefuture.com/fapi/v1/klines?symbol={urllib.parse.quote(symbol)}&interval={interval}&limit={int(limit)}",
      f"https://fapi.binance.com/fapi/v1/klines?symbol={urllib.parse.quote(symbol)}&interval={interval}&limit={int(limit)}"
    ]
    for u in urls:
        try:
            rows=http_json(u,timeout=12)
            if rows: return {"symbol":symbol,"interval":interval,"rows":rows,"source":"binance-public"}
        except Exception as exc: last=exc
    raise RuntimeError(f"Binance piyasa verisi alınamadı: {last}")

def public(path, params=None):
    q=urllib.parse.urlencode(params or {})
    return http_json(api_base()+path+("?" + q if q else ""))

def signed(method,path,params=None):
    params=dict(params or {})
    params["timestamp"]=int(time.time()*1000)
    params["recvWindow"]=5000
    qs=urllib.parse.urlencode(params)
    sig=hmac.new(DEFAULT["api_secret"].encode(),qs.encode(),hashlib.sha256).hexdigest()
    url=api_base()+path+"?"+qs+"&signature="+sig
    return http_json(url,method=method,headers={"X-MBX-APIKEY":DEFAULT["api_key"]})

def f(x): return float(x)
def ema(vals,n):
    if not vals: return 0
    a=2/(n+1); e=vals[0]
    for x in vals[1:]: e=a*x+(1-a)*e
    return e
def rsi(vals,n=14):
    if len(vals)<n+1:return 50
    gains=[]; losses=[]
    for a,b in zip(vals[-n-1:-1],vals[-n:]):
        d=b-a; gains.append(max(d,0)); losses.append(max(-d,0))
    ag=sum(gains)/n; al=sum(losses)/n
    return 100 if al==0 else 100-(100/(1+ag/al))
def atr(rows,n=14):
    if len(rows)<n+2:return 0
    tr=[]
    for i in range(1,len(rows)):
        hi=f(rows[i][2]); lo=f(rows[i][3]); pc=f(rows[i-1][4])
        tr.append(max(hi-lo,abs(hi-pc),abs(lo-pc)))
    return sum(tr[-n:])/n
def macd(vals):
    m=ema(vals,12)-ema(vals,26); sig=ema([ema(vals[:i+1],12)-ema(vals[:i+1],26) for i in range(26,len(vals))],9) if len(vals)>35 else m
    return m,sig
def boll(vals,n=20,k=2):
    a=vals[-n:]; mid=sum(a)/len(a); sd=(sum((x-mid)**2 for x in a)/len(a))**.5
    return mid,mid+k*sd,mid-k*sd
def supertrend(rows,n=10,mult=3):
    # compact stateful approximation
    if len(rows)<n+2:return "NEUTRAL"
    a=atr(rows,n); c=f(rows[-1][4]); prev=f(rows[-2][4])
    mid=(f(rows[-1][2])+f(rows[-1][3]))/2
    band=mid-mult*a if c>=prev else mid+mult*a
    return "BULL" if c>band else "BEAR"

def klines(symbol, interval="5m", limit=300):
    return public("/fapi/v1/klines",{"symbol":symbol,"interval":interval,"limit":limit})

def funding(symbol):
    try:
        return public("/fapi/v1/premiumIndex",{"symbol":symbol})
    except:return {}
def oi(symbol):
    try:return public("/fapi/v1/openInterest",{"symbol":symbol})
    except:return {}

def analyze(symbol):
    out={}
    rows5=klines(symbol,"5m",250)
    rows15=klines(symbol,"15m",250)
    rows1h=klines(symbol,"1h",250)
    # exclude current incomplete candle
    rows5=rows5[:-1]; rows15=rows15[:-1]; rows1h=rows1h[:-1]
    c=[f(x[4]) for x in rows5]; c15=[f(x[4]) for x in rows15]; c1=[f(x[4]) for x in rows1h]
    vols=[f(x[5]) for x in rows5]; tb=[f(x[9]) for x in rows5]
    price=c[-1]; r=rsi(c); m,ms=macd(c); mid,up,lo=boll(c)
    a=atr(rows5); st=supertrend(rows5,10,3)
    # CVD proxy from kline taker-buy base volume
    cvd=[2*t-v for t,v in zip(tb,vols)]
    cvd_now=sum(cvd[-20:]); cvd_prev=sum(cvd[-40:-20])
    cvd_dir=1 if cvd_now>cvd_prev else -1
    # simple divergence proxy
    pchg=(c[-1]-c[-15])/c[-15]*100
    rchg=r-rsi(c[:-15])
    div= -1 if pchg>0 and rchg<0 else 1 if pchg<0 and rchg>0 else 0
    fr=funding(symbol); funding_rate=f(fr.get("lastFundingRate",0))*100
    oi_data=oi(symbol); oi_now=f(oi_data.get("openInterest",0))
    e20=ema(c,20); e50=ema(c,50); e20_15=ema(c15,20); e50_15=ema(c15,50); e20_1=ema(c1,20); e50_1=ema(c1,50)
    score=0; reasons=[]
    if st=="BULL":score+=1;reasons.append("SuperTrend bullish")
    elif st=="BEAR":score-=1;reasons.append("SuperTrend bearish")
    if r<30:score+=1;reasons.append("RSI oversold")
    elif r>70:score-=1;reasons.append("RSI overbought")
    if div>0:score+=1;reasons.append("RSI bullish divergence")
    elif div<0:score-=1;reasons.append("RSI bearish divergence")
    if cvd_dir>0:score+=1;reasons.append("CVD positive")
    else:score-=1;reasons.append("CVD negative")
    if funding_rate<-0.01:score+=1;reasons.append("Funding long-friendly")
    elif funding_rate>0.03:score-=1;reasons.append("Funding short-friendly")
    if e20>e50:score+=1;reasons.append("5m EMA trend bullish")
    elif e20<e50:score-=1;reasons.append("5m EMA trend bearish")
    if e20_15>e50_15:score+=1;reasons.append("15m trend bullish")
    elif e20_15<e50_15:score-=1;reasons.append("15m trend bearish")
    if price<lo:score+=1;reasons.append("Below Bollinger lower band")
    elif price>up:score-=1;reasons.append("Above Bollinger upper band")
    # higher timeframe regime as separate filter
    regime="BULL" if e20_1>e50_1 else "BEAR"
    raw=score
    net=score*0.5 if regime=="BEAR" and score>0 else score
    signal="STRONG LONG" if net>=7 else "LONG" if net>=5 else "STRONG SHORT" if net<=-7 else "SHORT" if net<=-5 else "WAIT"
    out={"symbol":symbol,"price":price,"score":score,"raw_score":raw,"net_score":net,"signal":signal,
         "regime":regime,"rsi":r,"macd":m,"macd_signal":ms,"atr":a,"ema20":e20,"ema50":e50,
         "ema20_15":e20_15,"ema50_15":e50_15,"ema20_1h":e20_1,"ema50_1h":e50_1,
         "boll_mid":mid,"boll_up":up,"boll_low":lo,"cvd20":cvd_now,"cvd_prev20":cvd_prev,
         "funding":funding_rate,"oi":oi_now,"reasons":reasons,"ts":int(time.time())}
    return out

def scan():
    symbols=["BTCUSDT","XAUUSDT"]
    res={}
    for s in symbols:
        try: res[s]=analyze(s)
        except Exception as e: log(s+" analiz hatası: "+str(e),"ERROR")
    STATE["signals"]=res; STATE["last_scan"]=time.time()
    for s,v in res.items(): log(f"{s}: {v['signal']} score={v['net_score']:.1f} price={v['price']}")
    return res

def account():
    if not DEFAULT["api_key"] or not DEFAULT["api_secret"]: return {}
    return signed("GET","/fapi/v2/account")

def exchange_info():
    return public("/fapi/v1/exchangeInfo")

def symbol_info(symbol):
    try:
        for x in exchange_info()["symbols"]:
            if x["symbol"]==symbol:return x
    except:pass
    return None

def floor_step(x,step):
    if not step:return x
    return float((Decimal(str(x))/Decimal(str(step))).to_integral_value(rounding=ROUND_DOWN)*Decimal(str(step)))

def live_order(symbol,side,qty):
    return signed("POST","/fapi/v1/order",{"symbol":symbol,"side":side,"type":"MARKET","quantity":qty,"newOrderRespType":"RESULT"})

def set_leverage(symbol,lev):
    return signed("POST","/fapi/v1/leverage",{"symbol":symbol,"leverage":int(lev)})

def open_trade(symbol,signal):
    # This build deliberately supports Binance Testnet only.  A locally saved
    # key is still never enough for an automatic or live order.
    if DEFAULT["mode"] != "testnet" or not DEFAULT.get("testnet", True):
        return {"ok":False,"reason":"Testnet modu kapalı. PAPER modunda emir gönderilmez."}
    if not DEFAULT["api_key"] or not DEFAULT["api_secret"]:
        return {"ok":False,"reason":"Binance Testnet API key ve secret gerekli"}
    if signal["net_score"] < DEFAULT["min_score"] and signal["net_score"] > -DEFAULT["min_score"]:
        return {"ok":False,"reason":"Sinyal skoru yetersiz"}
    side="BUY" if signal["net_score"]>0 else "SELL"
    ac=account()
    avail=float(ac.get("availableBalance",0) or 0)
    risk=avail*DEFAULT["risk_per_trade"]/100
    stop_dist=max(signal["atr"]*1.5,signal["price"]*0.002)
    qty=risk/stop_dist
    qty=min(qty,(avail*0.20*DEFAULT["leverage"])/signal["price"])
    info=symbol_info(symbol)
    if not info:return {"ok":False,"reason":"Sembol bilgisi alınamadı"}
    step=0.001
    for f1 in info.get("filters",[]):
        if f1["filterType"]=="LOT_SIZE": step=float(f1["stepSize"])
    qty=floor_step(qty,step)
    if qty<=0:return {"ok":False,"reason":"Pozisyon miktarı minimumun altında"}
    set_leverage(symbol,DEFAULT["leverage"])
    order=live_order(symbol,side,qty)
    log(f"TESTNET {side} {symbol} qty={qty}","TRADE")
    return {"ok":True,"order":order,"mode":"testnet"}

def gemini(prompt):
    key=DEFAULT.get("gemini_key","").strip()
    if not key:return {"ok":False,"error":"Gemini API anahtarı girilmedi"}
    model=DEFAULT.get("gemini_model","gemini-3.6-flash")
    url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={urllib.parse.quote(key)}"
    payload={"contents":[{"parts":[{"text":prompt}]}]}
    try:
        d=http_json(url,"POST",payload)
        text=d["candidates"][0]["content"]["parts"][0]["text"]
        return {"ok":True,"text":text}
    except Exception as e:return {"ok":False,"error":str(e)}

def ai_analysis(symbol):
    if symbol not in STATE["signals"]: scan()
    s=STATE["signals"].get(symbol)
    if not s:return {"ok":False,"error":"Sinyal yok"}
    prompt=("Sen FurkAI'nin kripto ve Binance Futures analiz motorusun. Sadece aşağıdaki canlı veriyi kullan. "
            "Veri uydurma. Türkçe cevap ver. Kararı LONG/SHORT/WAIT olarak ver; güven 0-100; giriş bölgesi, "
            "ATR tabanlı stop, TP1/TP2 ve en önemli 3 gerekçe ver. Bu bir garanti değildir.\nVERİ:\n"+
            json.dumps(s,ensure_ascii=False))
    return gemini(prompt)

def bot_loop():
    while True:
        if STATE["running"]:
            try:
                scan()
                # Scanning never places an order by itself.  Testnet orders are
                # a separate, explicit action so a stale signal cannot trade.
            except Exception as e:
                STATE["last_error"]=str(e); log(str(e),"ERROR")
        time.sleep(STATE["scan_interval"])


# BIST data is analysis-only. Yahoo Finance is a delayed/public source and may
# reject requests; every failed symbol is reported and never turned into a result.
BIST_UNIVERSE = """
THYAO TUPRS ASELS GARAN AKBNK YKBNK ISCTR BIMAS EREGL KCHOL SAHOL SISE TCELL
FROTO TOASO PGSUS TAVHL PETKM HEKTS KOZAL KOZAA ENKAI ARCLK MGROS ULKER SASA
ASTOR OYAKC CCOLA DOAS MIATK GESAN GWIND ODAS ALARK ENJSA KRDMD TTKOM VESTL
LOGO MAVI SOKM AEFES CIMSA KONTR AKSEN TABGD REEDR AGHOL AGESA AKSA AKSUE
ALBRK ALCTL ALGYO ANSGR ASELS ASUZU ATATP ATLAS AVHOL AYDEM BAGFS BAKAB
BANVT BERA BIZIM BOBET BORLS BOSSA BRISA BRKSN BRSAN BRYAT BUCIM CANTE CEMAS
CLEBI CMBTN CRFSA DAGI DARDL DEVA DGATE DMSAS DODUR DOKTA DURDO DYOBY EGEEN
EGPRO EGYO EKGYO EMKEL ENERY EPDK? ERBOS ESCOM EUHOL EUPWR FADE FENER FLAP
FMIZP FORTE GENTS GEREL GLYHO GOZDE GUBRF GYHOL HALKB HATEK HDFGS HEKTS HLGYO
HUBVC ICBCT IHLAS IHYAY INDES INFO ISDMR ISFIN ISGYO ISMEN IZFAS JANTS KARSN
KARTN KATMR KAYSE KCAER KERVT KFEIN KLGYO KLSER KMPUR KOCMT KORDS KOTON KRDM?
KRDMA KRDMB KRVGD KSTUR KTSKR KUYAS LIDER LKMNH MACKO MAGEN MAKIM MARGN MARKA
MEDTR MEGAP MERIT MHRGY MIATK MPARK MRDIY MRGYO NIBAS NTGAZ OBASE OBAMS ODA? 
ORCAY ORGE OSTIM OTKAR OYAKC OZKGY PAGYO PAPIL PARSN PASEU PATEK PCILT PEKGY
PENTA PETUN PKART PNSUT POLHO PRKAB PRKME PSGYO PWT? QUAGR RALYH RAYSG RODRG
RUBNS RUZYE RYGYO SARKY SASA SAYAS SELEC SELGD SKBNK SKYMD SMART SNGYO SNICA
SOKM SRVGY SUMAS SURGY TATEN TATGD TAVHL TBORG TCKRC TDGYO TEHOL TEKTU TERA
TGSAS TKFEN TKNSA TLMAN TMPOL TMSN TMT? TOASO TRCAS TRGYO TSKB TSPOR TTKOM
TTRAK TUKAS TUPRS TURGG ULKER ULUFA UNLU VAKBN VANGD VBTYZ VERUS VESBE VESTL
VKFYO VKING YAPRK YATAS YAYLA YEOTK YGGYO YKBNK YKSLN YUNSA ZEDUR ZOREN
""".split()
BIST_UNIVERSE = [s for s in dict.fromkeys(BIST_UNIVERSE) if s.isalpha() and 3 <= len(s) <= 6]
KAP_MARKETS_URL = "https://www.kap.org.tr/tr/Pazarlar"
_universe_cache = {"symbols": BIST_UNIVERSE, "source": "Yerleşik başlangıç listesi", "updated": 0}

def get_bist_universe():
    """Prefer the current public KAP market table; use the bundled list only
    when the official site cannot be reached.  This avoids claiming the static
    fallback is the entire market."""
    if time.time() - _universe_cache["updated"] < 12 * 3600:
        return _universe_cache["symbols"], _universe_cache["source"]
    try:
        request = urllib.request.Request(KAP_MARKETS_URL, headers={"User-Agent":"Mozilla/5.0 FurkAI/39"})
        with urllib.request.urlopen(request, timeout=15) as response:
            html = response.read().decode("utf-8", "ignore")
        # KAP renders the trade codes as the short text of linked table cells.
        found = re.findall(r">\s*([A-Z0-9]{3,6})\s*</a>", html.upper())
        symbols = [s for s in dict.fromkeys(found) if any(c.isalpha() for c in s)]
        if len(symbols) >= 450:
            _universe_cache.update({"symbols":symbols, "source":"KAP Pazarlar / güncel kamuya açık liste", "updated":time.time()})
            return symbols, _universe_cache["source"]
    except Exception as exc:
        log("KAP evreni alınamadı; yerleşik liste kullanılıyor: " + str(exc), "WARN")
    _universe_cache.update({"symbols":BIST_UNIVERSE, "source":"Yerleşik başlangıç listesi (KAP erişimi yok)", "updated":time.time()})
    return BIST_UNIVERSE, _universe_cache["source"]

def yahoo_history(symbol, period="1y", allowed_symbols=None):
    symbol = symbol.upper().strip().replace(".IS", "")
    if symbol not in (allowed_symbols or BIST_UNIVERSE): raise ValueError("Sembol tarama evreninde değil")
    d=yahoo_chart(symbol+".IS",period,"1d"); q=d.get("quote") or {}
    def finite(name): return [float(x) for x in q.get(name,[]) if isinstance(x,(int,float)) and math.isfinite(x)]
    opens,highs,lows,closes,volumes=map(finite,("open","high","low","close","volume"))
    n=min(map(len,(opens,highs,lows,closes,volumes)))
    if n<60: raise ValueError("Yeterli OHLCV verisi yok")
    return {"open":opens[-n:],"high":highs[-n:],"low":lows[-n:],"close":closes[-n:],"volume":volumes[-n:]}

def _sma(vals,n): return sum(vals[-n:])/n if len(vals)>=n else None
def _ema_last(vals,n): return ema(vals[-min(len(vals),n*4):],n) if len(vals)>=n else None
def _macd_last(vals):
    if len(vals)<35:return 0,0
    line=ema(vals,12)-ema(vals,26); hist=[]
    for i in range(26,len(vals)):
        hist.append(ema(vals[:i+1],12)-ema(vals[:i+1],26))
    sig=ema(hist,9) if hist else line
    return line,sig
def _adx_last(high,low,close,n=14):
    if len(close)<n*2+1:return None
    trs=[]; plus=[]; minus=[]
    for i in range(1,len(close)):
        trs.append(max(high[i]-low[i],abs(high[i]-close[i-1]),abs(low[i]-close[i-1])))
        up=high[i]-high[i-1]; dn=low[i-1]-low[i]
        plus.append(up if up>dn and up>0 else 0); minus.append(dn if dn>up and dn>0 else 0)
    atrv=sum(trs[-n:])/n or 1; p=sum(plus[-n:])/n; m=sum(minus[-n:])/n
    pdi=100*p/atrv; mdi=100*m/atrv; return 100*abs(pdi-mdi)/max(pdi+mdi,1e-9)

def scan_bist_symbol(symbol, period, rsi_max, volume_min, selected, allowed_symbols):
    d=yahoo_history(symbol,period,allowed_symbols); o,h,l,c,v=d["open"],d["high"],d["low"],d["close"],d["volume"]
    last=c[-1]; e20=_ema_last(c,20); e50=_ema_last(c,50); s50=_sma(c,50); s200=_sma(c,200); r=rsi(c,14); vr=v[-1]/max(_sma(v,20) or 1,1)
    mac,ms=_macd_last(c); hi52=max(c[-min(252,len(c)):]); momentum=(last/c[-6]-1)*100 if len(c)>6 else 0; adx=_adx_last(h,l,c)
    body=abs(c[-1]-o[-1]); rng=max(h[-1]-l[-1],1e-9); hammer=(min(o[-1],c[-1])-l[-1]>body*1.5 and (h[-1]-max(o[-1],c[-1]))<body); doji=body/rng<0.12
    checks={
      "golden":bool(s50 and s200 and s50>s200),
      "breakout":last>=hi52*.995,
      "volume":vr>=volume_min and last>e20,
      "rsi":r<=rsi_max,
      "macd":mac>ms,
      "hammer":hammer or doji,
      "adx":bool(adx is not None and adx>=20),
      "momentum":momentum>0,
      "trend":last>e20 and e20>e50
    }
    enabled=[k for k,vv in selected.items() if vv]; passed=[k for k in enabled if checks[k]]
    score=round(100*len(passed)/max(1,len(enabled)))
    return {"symbol":symbol,"price":round(last,4),"rsi":round(r,2),"ema20":round(e20,4),"ema50":round(e50,4),"sma50":round(s50,4) if s50 else None,"sma200":round(s200,4) if s200 else None,"volume_ratio":round(vr,2),"macd":round(mac,4),"macd_signal":round(ms,4),"adx":round(adx,2) if adx is not None else None,"momentum":round(momentum,2),"score":score,"passed":passed,"conditions":checks,"trend":"Yükseliş" if checks["trend"] else "Karışık"}

def scan_bist(body):
    period = str(body.get("period", "1y"))
    if period not in ("6mo", "1y", "2y", "5y"): period = "1y"
    try: rsi_max = min(99, max(1, float(body.get("rsi_max", 70))))
    except: rsi_max = 70
    try: volume_min = min(20, max(.1, float(body.get("volume_min", 1.2))))
    except: volume_min = 1.2
    try: minimum_score = min(100, max(0, int(body.get("minimum_score", 60))))
    except: minimum_score = 60
    universe, universe_source = get_bist_universe()
    requested = body.get("symbols")
    symbols = [str(s).upper().replace(".IS", "") for s in requested] if isinstance(requested, list) else universe
    symbols = [s for s in dict.fromkeys(symbols) if s in universe]
    limit = min(700, max(1, int(body.get("limit", len(symbols)))))
    symbols = symbols[:limit]
    input_conditions = body.get("conditions", {}) if isinstance(body.get("conditions"), dict) else {}
    selected = {key: bool(input_conditions.get(key, True)) for key in ("trend", "golden", "rsi", "volume", "breakout", "momentum", "macd", "hammer", "adx")}
    if not any(selected.values()): raise ValueError("En az bir koşul seçilmeli")
    # Fail once and clearly when the external provider cannot be reached,
    # rather than making the user wait through hundreds of identical failures.
    probe_symbol = "THYAO" if "THYAO" in universe else symbols[0]
    try:
        yahoo_history(probe_symbol, period, universe)
    except Exception as exc:
        return {"ok":True, "source":"Yahoo Finance / gecikmeli veya erişilemeyebilir", "timestamp":int(time.time()),
                "universe_size":len(universe), "universe_source":universe_source, "requested":len(symbols),
                "scanned":0, "errors":[{"symbol":probe_symbol, "error":"Veri sağlayıcısı erişilemez: " + str(exc)[:140]}],
                "results":[], "conditions":selected, "data_available":False}
    rows, errors = [], []
    with ThreadPoolExecutor(max_workers=12) as pool:
        future_map = {pool.submit(scan_bist_symbol, s, period, rsi_max, volume_min, selected, universe): s for s in symbols}
        for future in as_completed(future_map):
            symbol = future_map[future]
            try:
                row = future.result()
                if row["score"] >= minimum_score: rows.append(row)
            except Exception as exc:
                errors.append({"symbol":symbol, "error":str(exc)[:140]})
    rows.sort(key=lambda item: (-item["score"], -item["volume_ratio"], item["symbol"]))
    return {"ok":True, "source":"Yahoo Finance / gecikmeli veya erişilemeyebilir", "timestamp":int(time.time()),
            "universe_size":len(universe), "universe_source":universe_source, "requested":len(symbols), "scanned":len(symbols)-len(errors),
            "errors":errors, "results":rows, "conditions":selected, "data_available":True}


APP_USER=os.environ.get("FURKAI_USER","furkai")
APP_PASSWORD=os.environ.get("FURKAI_PASSWORD","")

def authorized(headers):
    if not APP_PASSWORD:
        return True
    raw=headers.get("Authorization","")
    if not raw.startswith("Basic "):
        return False
    try:
        decoded=base64.b64decode(raw[6:]).decode("utf-8")
        user,password=decoded.split(":",1)
        return hmac.compare_digest(user,APP_USER) and hmac.compare_digest(password,APP_PASSWORD)
    except Exception:
        return False

class Handler(BaseHTTPRequestHandler):
    def sendj(self,obj,status=200):
        b=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(b)));self.send_header("Access-Control-Allow-Origin","*");self.end_headers();self.wfile.write(b)
    def do_GET(self):
        p=urllib.parse.urlparse(self.path)
        if p.path != "/api/health" and not authorized(self.headers):
            self.send_response(401)
            self.send_header("WWW-Authenticate",'Basic realm="FurkAI"')
            self.end_headers()
            return
        if p.path in ("/", "/index.html"):
            data=(BASE/"index.html").read_bytes();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data);return
        if p.path=="/manifest.json":
            data=(BASE/"manifest.json").read_bytes();self.send_response(200);self.send_header("Content-Type","application/manifest+json; charset=utf-8");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data);return
        if p.path=="/service-worker.js":
            data=(BASE/"service-worker.js").read_bytes();self.send_response(200);self.send_header("Content-Type","application/javascript; charset=utf-8");self.send_header("Service-Worker-Allowed","/");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data);return
        try:
            if p.path=="/api/health":return self.sendj({"ok":True,"version":"V42 Unified","mode":DEFAULT["mode"],"testnet":bool(DEFAULT.get("testnet",True)),"running":STATE["running"],"last_error":STATE["last_error"]})
            if p.path=="/api/state":return self.sendj({"ok":True,"config":{k:v for k,v in DEFAULT.items() if k not in ("api_secret","gemini_key")},"signals":STATE["signals"],"last_scan":STATE["last_scan"],"running":STATE["running"],"logs":STATE["logs"][:80]})
            if p.path=="/api/account":return self.sendj(account())
            if p.path=="/api/scan":return self.sendj({"ok":True,"signals":scan()})
            if p.path=="/api/binance/status":
                return self.sendj({"ok":True,"testnet":bool(DEFAULT.get("testnet",True)),"mode":DEFAULT.get("mode"),"configured":bool(DEFAULT.get("api_key") and DEFAULT.get("api_secret")),"auto_execution":False})
            if p.path=="/api/binance/scan":return self.sendj({"ok":True,"signals":scan(),"source":"Binance Futures Testnet market data"})
            if p.path=="/api/bist/universe":
                symbols, source = get_bist_universe()
                return self.sendj({"ok":True,"symbols":symbols,"count":len(symbols),"source":source})
            if p.path=="/api/ai":
                q=urllib.parse.parse_qs(p.query);return self.sendj(ai_analysis(q.get("symbol",["BTCUSDT"])[0]))
            if p.path=="/api/quote":
                q=urllib.parse.parse_qs(p.query); s=q.get("symbol",["THYAO.IS"])[0]
                return self.sendj(yahoo_quote(s))
            if p.path=="/api/quotes":
                q=urllib.parse.parse_qs(p.query); symbols=q.get("symbols",[""])[0].split(",")
                return self.sendj(yahoo_quotes(symbols))
            if p.path=="/api/history":
                q=urllib.parse.parse_qs(p.query); s=q.get("symbol",["THYAO.IS"])[0]
                period=q.get("range",["1y"])[0]; interval=q.get("interval",["1d"])[0]
                return self.sendj({"ok":True,"data":yahoo_chart(s,period,interval)})
            if p.path=="/api/trading/klines":
                q=urllib.parse.parse_qs(p.query); s=q.get("symbol",["BTCUSDT"])[0]
                interval=q.get("interval",["1m"])[0]; limit=int(q.get("limit",["300"])[0])
                return self.sendj({"ok":True,"data":binance_klines(s,limit,interval)})
            if p.path=="/api/market":
                q=urllib.parse.parse_qs(p.query);s=q.get("symbol",["BTCUSDT"])[0]
                return self.sendj({"ok":True,"symbol":s,"signal":analyze(s)})
            self.send_response(404);self.end_headers()
        except Exception as e:
            STATE["last_error"]=str(e);self.sendj({"ok":False,"error":str(e)},500)
    def do_HEAD(self):
        if self.path=="/api/health":
            self.send_response(200); self.send_header("Content-Length","0"); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Length","0"); self.end_headers()

    def do_POST(self):
        if not authorized(self.headers):
            self.send_response(401)
            self.send_header("WWW-Authenticate",'Basic realm="FurkAI"')
            self.end_headers()
            return
        try:
            n=int(self.headers.get("Content-Length",0)); body=json.loads(self.rfile.read(n) or b"{}")
            if self.path=="/api/config":
                for k,v in body.items():
                    if k in DEFAULT: DEFAULT[k]=v
                # This package intentionally never switches to Binance Live.
                DEFAULT["testnet"] = True
                if DEFAULT.get("mode") not in ("paper", "testnet"): DEFAULT["mode"] = "paper"
                save_cfg();return self.sendj({"ok":True})
            if self.path=="/api/bot/start":
                STATE["running"]=True;log("BOT BAŞLATILDI");return self.sendj({"ok":True})
            if self.path=="/api/bot/stop":
                STATE["running"]=False;log("BOT DURDURULDU");return self.sendj({"ok":True})
            if self.path=="/api/order":
                s=body.get("symbol","BTCUSDT");return self.sendj(open_trade(s,STATE["signals"].get(s) or analyze(s)))
            if self.path=="/api/binance/order":
                s=str(body.get("symbol","BTCUSDT")).upper()
                if DEFAULT.get("mode") != "testnet" or not DEFAULT.get("testnet", True):
                    return self.sendj({"ok":False,"reason":"Testnet modu kapalı. PAPER modunda emir gönderilmez."}, 400)
                if not DEFAULT.get("api_key") or not DEFAULT.get("api_secret"):
                    return self.sendj({"ok":False,"reason":"Binance Testnet API key ve secret gerekli"}, 400)
                signal=STATE["signals"].get(s) or analyze(s)
                # A manual testnet button chooses the side explicitly; it does
                # not alter scanner output or enable automatic execution.
                signal=dict(signal)
                signal["net_score"] = 7 if body.get("side") == "long" else -7
                return self.sendj(open_trade(s,signal))
            if self.path=="/api/bist/scan":return self.sendj(scan_bist(body))
            self.send_response(404);self.end_headers()
        except Exception as e:
            STATE["last_error"]=str(e);self.sendj({"ok":False,"error":str(e)},500)

def main():
    threading.Thread(target=bot_loop,daemon=True).start()
    log("FurkAI V12 başladı. Binance: ayrı modül; Midas/BIST ayrı modül.")
    port=int(os.environ.get("PORT","8798"))
    ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()
if __name__=="__main__":main()
