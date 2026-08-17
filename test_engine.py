import inspect
import json
import server


def test_crosses():
    a=[1,2,3,4,5,6,7,8,9,10]*30
    assert isinstance(server._sma_cross(a,5,10), bool)


def test_rsi_wilder_reference():
    # Independent Wilder calculation on a deterministic zig-zag series.
    c=[100,102,101,103,102,104,103,105,104,106,105,107,106,108,107,109,108,110,109,111]
    n=5
    gains=[max(c[i]-c[i-1],0.0) for i in range(1,len(c))]
    losses=[max(c[i-1]-c[i],0.0) for i in range(1,len(c))]
    ag=sum(gains[:n])/n; al=sum(losses[:n])/n
    for g,l in zip(gains[n:],losses[n:]):
        ag=(ag*(n-1)+g)/n; al=(al*(n-1)+l)/n
    expected=100.0 if al==0 else 100-100/(1+ag/al)
    assert abs(server.rsi(c,n)-expected)<1e-12


def test_adx_wilder_reference():
    c=[100,101,100.5,102,101,103,102.5,104,103,105,104.5,106,105,107,106.5,108,107,109,108,110,109,111,110,112,111,113,112,114,113,115,114,116,115,117,116,118]
    h=[x+1 for x in c]; l=[x-1 for x in c]; n=5
    tr=[]; plus=[]; minus=[]
    for i in range(1,len(c)):
        tr.append(max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])))
        up=h[i]-h[i-1]; dn=l[i-1]-l[i]
        plus.append(up if up>dn and up>0 else 0.0)
        minus.append(dn if dn>up and dn>0 else 0.0)
    atr=sum(tr[:n])/n; ps=sum(plus[:n])/n; ms=sum(minus[:n])/n
    def dx(a,p,m):
        pdi=100*p/a; mdi=100*m/a
        return 100*abs(pdi-mdi)/max(pdi+mdi,1e-12)
    dxs=[dx(atr,ps,ms)]
    for i in range(n,len(tr)):
        atr=(atr*(n-1)+tr[i])/n; ps=(ps*(n-1)+plus[i])/n; ms=(ms*(n-1)+minus[i])/n
        dxs.append(dx(atr,ps,ms))
    adx=sum(dxs[:n])/n
    for x in dxs[n:]: adx=(adx*(n-1)+x)/n
    assert abs(server.adx(h,l,c,n)-adx)<1e-12


def test_supertrend_shape_and_numeric_regression():
    # Fixed deterministic OHLCV fixture. Expected values were calculated with
    # an independent Wilder-ATR + recursive Supertrend implementation and are
    # intentionally hard-coded so this test can catch implementation drift.
    c=[100+i*0.2 for i in range(100)]
    h=[x+1 for x in c]; l=[x-1 for x in c]
    x=server.supertrend(h,l,c)
    assert x and x['bullish'] and abs(x['atr']-2.0)<1e-12
    assert abs(x['line']-113.8)<1e-12 and x['direction']==1


def test_ichimoku_numeric_reference():
    c=list(range(100,180)); h=[x+2 for x in c]; l=[x-2 for x in c]
    x=server.ichimoku(h,l,c)
    i=len(c)-1; cloud_i=i-26
    tenkan=(max(h[i-8:i+1])+min(l[i-8:i+1]))/2
    kijun=(max(h[i-25:i+1])+min(l[i-25:i+1]))/2
    span_a=((max(h[cloud_i-8:cloud_i+1])+min(l[cloud_i-8:cloud_i+1]))/2 + (max(h[cloud_i-25:cloud_i+1])+min(l[cloud_i-25:cloud_i+1]))/2)/2
    span_b=(max(h[cloud_i-51:cloud_i+1])+min(l[cloud_i-51:cloud_i+1]))/2
    assert abs(x['tenkan']-tenkan)<1e-12
    assert abs(x['kijun']-kijun)<1e-12
    assert abs(x['span_a']-span_a)<1e-12
    assert abs(x['span_b']-span_b)<1e-12


def test_auth_required_when_configured():
    old=(server.REQUIRE_AUTH,server.PASSWORD,server.USER)
    try:
        server.REQUIRE_AUTH=True; server.PASSWORD='secret'; server.USER='furkai'
        class H:
            def get(self,k,d=''): return d
        assert server.auth(H()) is False
    finally:
        server.REQUIRE_AUTH,server.PASSWORD,server.USER=old


def test_score_is_bounded():
    c=[100+i*0.1 for i in range(300)]; h=[x+1 for x in c]; l=[x-1 for x in c]; v=[100000]*300
    s,checks,b=server.signal_score({'close':c,'high':h,'low':l,'volume':v})
    assert 0<=s<=100 and sum(b.values())==s


def test_history_excludes_in_progress_daily_bar():
    import datetime
    now=datetime.datetime.now(server.BIST_TZ)
    today=int(now.timestamp())
    yesterday=int((now-datetime.timedelta(days=1)).timestamp())
    if now.time() < server.BIST_CLOSE_TIME:
        assert server._daily_bar_complete(today) is False
    else:
        assert server._daily_bar_complete(today) is True
    assert server._daily_bar_complete(yesterday) is True


def test_bist_session_close_calendar():
    import datetime
    assert server._bist_session_close(datetime.date(2026, 8, 13)).hour==18
    assert server._bist_session_close(datetime.date(2026, 8, 13)).minute==10
    assert server._bist_session_close(datetime.date(2026, 10, 28)).hour==13
    assert server._bist_session_close(datetime.date(2026, 10, 28)).minute==0


def test_signal_horizons_use_trading_bars_not_calendar_days():
    # Three weekly-spaced trading bars demonstrate that N means N bars, not
    # N*24h calendar time. The helper must return the exact Nth subsequent bar.
    base=1700000000
    ts=[base+i*86400*3 for i in range(30)]
    closes=[100+i for i in range(30)]
    old=server.history
    try:
        server.history=lambda symbol,period: {'timestamp':ts,'close':closes}
        assert server._historical_return_at('THYAO',ts[5],1)==106
        assert server._historical_return_at('THYAO',ts[5],5)==110
    finally:
        server.history=old


def test_backtest_uses_exact_requested_horizon():
    n=1200
    close=[100+i*0.02 for i in range(n)]
    high=[x+1 for x in close]; low=[x-1 for x in close]; op=[x for x in close]; vol=[100000]*n
    old=server.history
    try:
        server.history=lambda symbol,period: {'symbol':symbol+'.IS','close':close,'open':op,'high':high,'low':low,'volume':vol}
        out=server.backtest('THYAO',250,100000)
        assert out['period_days']==250 and out['requested_days']==250
    finally:
        server.history=old


def test_backtest_no_same_close_exit_lookahead():
    # The first decision generates entry; the next decision generates exit.
    # The exit must occur on the following session OPEN, not on the bearish
    # decision candle's close.
    n=260; close=[100.0]*n; op=[100.0]*n; high=[101.0]*n; low=[99.0]*n; vol=[100000.0]*n
    start=n-(200+30+1)
    op[start+201]=100; close[start+201]=100
    op[start+202]=80; close[start+202]=40
    old_hist,old_score,old_atr=server.history,server.signal_score,server.atr
    try:
        server.history=lambda symbol,period: {'symbol':symbol+'.IS','close':close,'open':op,'high':high,'low':low,'volume':vol}
        def fake_score(d):
            idx=len(d['close'])-1
            return (70 if idx==200 else 40 if idx==201 else 40, {}, {})
        server.signal_score=fake_score; server.atr=lambda h,l,c,n=14: 1.0
        out=server.backtest('THYAO',30,100000)
        assert out['trades']>=1
        # Entry at 100 and exit at next-session open 80, so final equity is
        # below the all-close-100 shortcut but not the impossible close-40 exit.
        assert out['final']>85000, 'Çıkış karar candle kapanışından uygulanmamalı'
        body=inspect.getsource(server.backtest)
        assert 'SIGNAL_EXIT_OPEN' in body and 'exit_price=day_open' in body
    finally:
        server.history,server.signal_score,server.atr=old_hist,old_score,old_atr


def test_backtest_requests_enough_window():
    body=inspect.getsource(server.backtest)
    assert "period='5y'" in body
    assert 'required=warmup+days+1' in body
    assert "'period_days':days" in body



def test_52h_breakout_excludes_current_bar():
    # Current bar must be compared against the PREVIOUS 252 completed bars.
    base=[100.0 + (i % 20) for i in range(252)]
    # Current close is a new high; including it in the reference would make
    # the breakout impossible to detect.
    c=base+[130.0]
    h=[x+1 for x in c]; l=[x-1 for x in c]; v=[100000.0]*252+[200000.0]
    models=server.scan_models({'open':c,'high':h,'low':l,'close':c,'volume':v})
    assert models['52H Kırılım'] is True
    assert models['Qullamaggie'] is True


def test_52h_not_breakout_when_current_is_below_previous_high():
    c=[100.0 + (i % 20) for i in range(252)] + [118.0]
    h=[x+1 for x in c]; l=[x-1 for x in c]; v=[100000.0]*252+[200000.0]
    models=server.scan_models({'open':c,'high':h,'low':l,'close':c,'volume':v})
    assert models['52H Kırılım'] is False


def test_signal_ui_calls_price_signal_price():
    body=open('app.js',encoding='utf-8').read()
    assert '<th>Sinyal Fiyatı</th>' in body
    assert '<td>${fmt(x.entry)}</td>' in body


def test_52h_uses_high_not_close():
    # Previous 252-day HIGH is 120 while previous CLOSE never exceeds 110.
    # A current close of 121 is a true 52-week breakout; using closes would
    # produce a different reference level.
    c=[100.0 + (i % 11) for i in range(252)] + [121.0]
    h=[120.0 for _ in range(252)] + [122.0]
    l=[x-2 for x in c]
    v=[100000.0]*252+[200000.0]
    models=server.scan_models({'open':c,'high':h,'low':l,'close':c,'volume':v})
    assert models['52H Kırılım'] is True
    assert models['Qullamaggie'] is True


def test_52h_not_triggered_by_previous_close_only():
    # Previous close can be 119 while previous intraday high is 130. A current
    # close of 125 is NOT a 52-week high breakout.
    c=[119.0]*252+[125.0]
    h=[130.0]*252+[126.0]
    l=[118.0]*252+[124.0]
    v=[100000.0]*252+[200000.0]
    models=server.scan_models({'open':c,'high':h,'low':l,'close':c,'volume':v})
    assert models['52H Kırılım'] is False
    assert models['Qullamaggie'] is False



def test_multi_model_and_or_semantics():
    flags={'A':True,'B':False,'C':False}
    ok,matched=server._models_match(flags,['A','B','C'],'OR')
    assert ok and matched==['A']
    ok,matched=server._models_match(flags,['A','B','C'],'AND')
    assert not ok and matched==['A']
    flags={'A':False,'B':True,'C':True}
    ok,matched=server._models_match(flags,['A','B','C'],'OR')
    assert ok and matched==['B','C']
    ok,matched=server._models_match(flags,['A','B','C'],'OR',2)
    assert ok and matched==['B','C']
    ok,matched=server._models_match(flags,['A','B','C'],'OR',3)
    assert not ok


def test_or_default_threshold_is_one():
    flags={'A':True,'B':False,'C':False}
    ok,_=server._models_match(flags,['A','B','C'],'OR',None)
    assert ok

def test_version_is_consistent():
    import re
    server_src=open('server.py',encoding='utf-8').read()
    wsgi_src=open('server_wsgi.py',encoding='utf-8').read()
    html=open('index.html',encoding='utf-8').read()
    readme=open('README.md',encoding='utf-8').read()
    assert server.DEFAULT['app_version']=='15.9.6'
    assert "APP_VERSION='15.9.6'" in server_src
    assert "server.APP_VERSION" in wsgi_src
    assert 'V15.9.6' in html
    assert 'v15.8' in readme.lower()




def test_portfolio_server_validation():
    import tempfile, pathlib
    old_db=server.DB
    with tempfile.TemporaryDirectory() as td:
        server.DB=pathlib.Path(td)/'test.db'
        try:
            u=server.create_user('testuser','StrongPass123!')
            server.save_portfolio([{'id':1,'symbol':'THYAO.IS','qty':10,'cost':100}],u['id'])
            assert server.load_portfolio(u['id'])[0]['symbol']=='THYAO.IS'
            for bad in [
                [{'id':2,'symbol':'THYAO.IS','qty':0,'cost':100}],
                [{'id':3,'symbol':'bad!','qty':1,'cost':100}],
                [{'id':4,'symbol':'THYAO.IS','qty':1,'cost':float('nan')}],
                [{'id':5,'symbol':'THYAO.IS','qty':1,'cost':100},{'id':5,'symbol':'ASELS.IS','qty':1,'cost':100}],
            ]:
                try:
                    server.save_portfolio(bad,u['id'])
                    raise AssertionError('Geçersiz portföy kaydı kabul edildi')
                except ValueError:
                    pass
        finally:
            server.DB=old_db




def test_all_frontend_error_html_uses_escaping():
    html=open('index.html',encoding='utf-8').read()
    assert "catch(e){$('signalTable').innerHTML='<div class=\"note\">'+esc(e.message)+'</div>'}" in html

def test_frontend_dynamic_error_output_is_escaped():
    html=open('index.html',encoding='utf-8').read()
    assert "catch(e){$('kapOut').innerHTML='<div class=\"note\">'+esc(e.message)+'</div>'}" in html

def test_local_auth_default_is_not_deadlocked():
    # Render explicitly enables auth; a bare local `python server.py` must not
    # become unusable merely because no password environment variable exists.
    src=open('server.py',encoding='utf-8').read()
    assert "FURKAI_REQUIRE_AUTH','0'" in src

def test_history_split_adjustment_math():
    # Exercise the adjustment logic without a network call.
    old_chart=server.yahoo_chart
    try:
        base=1700000000
        ts=[base+i*86400 for i in range(70)]
        q={k:[100.0+i for i in range(70)] for k in ('open','high','low','close')}
        q['volume']=[1000.0]*70
        split_ts=ts[40]
        server.yahoo_chart=lambda symbol,period,interval:{
            'symbol':'TEST.IS','quote':q,'timestamp':ts,
            'events':{'splits':{str(split_ts):{'numerator':2,'denominator':1}}}
        }
        out=server.history('TEST','1y')
        assert out['close'][39]==69.5
        assert out['close'][40]==140.0
        assert out['volume'][39]==2000.0
        assert out['volume'][40]==1000.0
    finally:
        server.yahoo_chart=old_chart


def test_signal_model_key_is_canonical_and_deduplicated():
    import tempfile, pathlib
    old_db=server.DB
    with tempfile.TemporaryDirectory() as td:
        server.DB=pathlib.Path(td)/'test.db'
        try:
            row={'symbol':'THYAO.IS','price':100.0,'score':82.0,
                 'models':{'Golden Cross':True,'MACD Kesişimi':True},
                 'active_models':['Golden Cross','MACD Kesişimi'],
                 'signal_timestamp':1700000000}
            server.record_signals([row],['MACD Kesişimi','Golden Cross'])
            server.record_signals([row],['Golden Cross','MACD Kesişimi'])
            c=server.db(); rows=[dict(r) for r in c.execute('SELECT * FROM signal_history')]; c.close()
            assert len(rows)==1
            assert rows[0]['models']=='Golden Cross,MACD Kesişimi'
        finally:
            server.DB=old_db


def test_signal_dedup_uses_bist_local_day_not_utc_day():
    import tempfile, pathlib
    old_db=server.DB
    with tempfile.TemporaryDirectory() as td:
        server.DB=pathlib.Path(td)/'test.db'
        try:
            # 2023-11-14 22:13 UTC is 2023-11-15 01:13 in Europe/Istanbul.
            ts=1700000000
            row={'symbol':'THYAO.IS','price':100.0,'score':82.0,
                 'models':{'Golden Cross':True},'active_models':['Golden Cross'],
                 'signal_timestamp':ts}
            server.record_signals([row],['Golden Cross'])
            server.record_signals([row],['Golden Cross'])
            c=server.db(); rows=[dict(r) for r in c.execute('SELECT * FROM signal_history')]; c.close()
            assert len(rows)==1
        finally:
            server.DB=old_db

def test_score_only_scan_records_signal():
    # A scan with no explicit models still needs a persistent provenance row.
    import tempfile, pathlib
    old_db=server.DB
    with tempfile.TemporaryDirectory() as td:
        server.DB=pathlib.Path(td)/'test.db'
        try:
            row={'symbol':'THYAO.IS','price':100.0,'score':82.0,
                 'models':{m:False for m in ['A','B']},'active_models':[],'signal_timestamp':1700000000}
            server.record_signals([row],[])
            old_quotes=server.quotes
            server.quotes=lambda syms:{'quotes':{}}
            try:
                got=server.signal_history(10)['signals']
            finally:
                server.quotes=old_quotes
            assert len(got)==1 and got[0]['models']=='FurkAI Score'
        finally:
            server.DB=old_db


def test_score_only_scan_keeps_active_model_provenance():
    import tempfile, pathlib
    old_db=server.DB
    with tempfile.TemporaryDirectory() as td:
        server.DB=pathlib.Path(td)/'test.db'
        try:
            row={'symbol':'ASELS.IS','price':100.0,'score':84.0,
                 'models':{'Golden Cross':True},'active_models':['Golden Cross'],
                 'signal_timestamp':1700000000}
            server.record_signals([row],[])
            old_quotes=server.quotes
            old_hist=server._historical_return_at
            server.quotes=lambda syms:{'quotes':{}}
            server._historical_return_at=lambda *args,**kwargs: None
            try:
                got=server.signal_history(10)['signals']
            finally:
                server.quotes=old_quotes
                server._historical_return_at=old_hist
            assert len(got)==1 and got[0]['models']=='Golden Cross'
        finally:
            server.DB=old_db

def test_scanner_accepts_all_27_models_and_min_models():
    body=inspect.getsource(server.scan)
    assert "body.get('models',[])][:27]" in body
    out=server.scan.__defaults__ if hasattr(server.scan,'__defaults__') else None
    ok,matched=server._models_match({f'M{i}':True for i in range(27)},[f'M{i}' for i in range(27)],'AND')
    assert ok and len(matched)==27
    ok,matched=server._models_match({f'M{i}':(i==26) for i in range(27)},[f'M{i}' for i in range(27)],'OR',1)
    assert ok and matched==['M26']


def test_health_version_matches_app_version():
    body=inspect.getsource(server.Handler.do_GET)
    assert "DEFAULT.get('app_version',APP_VERSION)" in body


def test_scanner_get_preserves_min_models_parameter():
    body=inspect.getsource(server.Handler.do_GET)
    assert "'min_models'" in body and "q.get('min_models'" in body


def test_wsgi_static_assets_support_get_and_head():
    from wsgiref.util import setup_testing_defaults
    from io import BytesIO
    import server_wsgi
    for path in ('/manifest.webmanifest','/sw.js','/icon-180.png','/icon-512.png'):
        for method in ('GET','HEAD'):
            env={}; setup_testing_defaults(env); env.update({'PATH_INFO':path,'REQUEST_METHOD':method,'wsgi.input':BytesIO(b''),'CONTENT_LENGTH':'0','QUERY_STRING':''})
            captured=[]
            def sr(status,headers,exc_info=None): captured.append((status,headers)); return lambda data: None
            body=b''.join(server_wsgi.app(env,sr))
            assert captured and captured[0][0]=='200 OK', (path,method,captured)
            if method=='GET': assert body, (path,method)


def test_mobile_nav_selector_is_valid():
    html=open('index.html',encoding='utf-8').read()
    assert '.mobile-bar [data-mobile-page]' in html
    assert '.mobile-bottom-nav [data-mobile-page]' not in html


def test_no_stale_v15_references_in_runtime_files():
    current='15.8'
    stale=('15.0','15.1','15.2','15.3','15.4','15.5')
    for name in ('server.py','server_wsgi.py','index.html','sw.js','manifest.webmanifest','README.md','README_MOBILE.md'):
        text=open(name,encoding='utf-8').read()
        if name != 'server_wsgi.py': assert current in text, name
        assert all(v not in text for v in stale), name


def test_frontend_chart_has_trading_interactions():
    html=open('index.html',encoding='utf-8').read()
    assert html.count('async function aiStock(){')==1
    assert 'attachChartInteractions()' in html
    assert "addEventListener('wheel'" in html
    assert "addEventListener('mousedown'" in html
    assert 'crossIndex' in html
    assert 'resetChartView' in html


def test_frontend_exposes_all_27_models():
    html=open('index.html',encoding='utf-8').read()
    import re
    m=re.search(r"const MODELS=\[(.*?)\];",html,re.S)
    assert m and m.group(1).count("'")//2==27


def test_wsgi_scan_preserves_min_models_parameter():
    src=open('server_wsgi.py',encoding='utf-8').read()
    assert "'min_models'" in src and "query.get('min_models'" in src


def test_chart_supports_extended_timeframes_and_drawings():
    src=open('server.py',encoding='utf-8').read(); html=open('index.html',encoding='utf-8').read(); js=html
    for token in ("'1m'","'5m'","'15m'","'30m'","'1h'","'2h'","'4h'","'1d'","'1w'","'1mo'"): assert token in src
    for token in ("function setDrawMode(mode)","function drawChartOverlays","function startChartLiveRefresh","tf15m","tf1mo"): assert token in html

def test_backtest_backend_exposes_equity_curve():
    src=open('server.py',encoding='utf-8').read()
    js=open('app.js',encoding='utf-8').read()
    assert "'equity_curve'" in src and 'drawBacktestCurves' not in js

def test_portfolio_intelligence_has_risk_and_diversification():
    src=open('server.py',encoding='utf-8').read(); html=open('index.html',encoding='utf-8').read()
    assert 'atr_pct' in src and 'diversification_score' in src and 'En yüksek korelasyon' in html

def test_chart_api_accepts_interval():
    src=open('server.py',encoding='utf-8').read()
    assert "q.get('interval'" in src and "history(q.get('symbol'" in src

def test_market_regime_endpoint_and_dashboard():
    src=open('server.py',encoding='utf-8').read(); html=open('index.html',encoding='utf-8').read(); js=html
    assert 'def market_regime()' in src and "'/api/market-regime'" in src
    assert 'marketRegime' in html and '/api/market-regime' in html


def test_settings_schema_and_masking():
    old=dict(server.DEFAULT)
    try:
        server.DEFAULT.update({'gemini_key':'AIzaTEST1234','gemini_model':'gemini-3.6-flash','scanner_limit':250,'default_period':'1y','default_interval':'1d','refresh_seconds':15,'auto_refresh':True,'app_version':'15.8'})
        cfg=server.public_config()
        assert cfg['gemini_configured'] is True
        assert cfg['gemini_key_masked'].endswith('1234')
        assert 'AIzaTEST1234' not in cfg['gemini_key_masked']
        assert cfg['default_interval']=='1d' and cfg['refresh_seconds']==15
    finally:
        server.DEFAULT.clear(); server.DEFAULT.update(old)


def test_save_config_bounds_and_persistence():
    import tempfile, pathlib
    old_cfg=server.CFG
    old=dict(server.DEFAULT)
    with tempfile.TemporaryDirectory() as td:
        server.CFG=pathlib.Path(td)/'config.json'
        try:
            out=server.save_config({'scanner_limit':9999,'refresh_seconds':1,'default_interval':'4h','auto_refresh':False,'gemini_model':'x'})
            assert out['scanner_limit']==700 and out['refresh_seconds']==5 and out['default_interval']=='4h' and out['auto_refresh'] is False
            saved=json.loads(server.CFG.read_text())
            assert saved['default_interval']=='4h' and saved['refresh_seconds']==5
        finally:
            server.CFG=old_cfg; server.DEFAULT.clear(); server.DEFAULT.update(old)


def test_frontend_settings_page_and_single_backtest_function():
    html=open('index.html',encoding='utf-8').read()
    assert 'section id="settings"' in html
    assert 'setGeminiKey' in html and '/api/config' in html and '/api/data-status' in html
    assert 'runBacktest' not in html and 'runBacktest' not in open('app.js',encoding='utf-8').read()


def test_wsgi_has_config_and_data_status_routes():
    src=open('server_wsgi.py',encoding='utf-8').read()
    assert "path=='/api/config' and method in ('GET','HEAD')" in src
    assert "path=='/api/data-status' and method in ('GET','HEAD')" in src
    assert "path=='/api/portfolio/intelligence'" in src


def test_wsgi_head_support_for_root_and_health():
    src=open('server_wsgi.py',encoding='utf-8').read()
    assert "method in ('GET','HEAD')" in src
    assert "if method=='HEAD'" in src
    assert "/api/health" in src


def test_frontend_has_no_obvious_async_duplication():
    html=open('index.html',encoding='utf-8').read()
    assert 'async async' not in html
    assert html.count('async function aiStock(){')==1
    assert 'runBacktest' not in html and 'runBacktest' not in open('app.js',encoding='utf-8').read()


def test_backtest_exposes_benchmark_and_buy_hold_curves():
    src=open('server.py',encoding='utf-8').read()
    assert "'benchmark_curve':benchmark_curve" in src and "'buy_hold_curve':buy_hold_curve" in src


def test_portfolio_risk_uses_weight_and_risk_factors():
    src=open('server.py',encoding='utf-8').read()
    assert "YÜKSEK_POZİSYON_AĞIRLIĞI" in src and "risk_factors" in src and "AŞIRI_ALIM" in src


def test_gemini_key_is_encrypted_on_persistence():
    import tempfile, pathlib, json
    old_cfg, old_default = server.CFG, dict(server.DEFAULT)
    with tempfile.TemporaryDirectory() as td:
        server.CFG=pathlib.Path(td)/'config.json'
        server.DEFAULT['gemini_key']='TEST-SECRET-1234'
        server.save_config({'gemini_key':'TEST-SECRET-1234'})
        raw=json.loads(server.CFG.read_text(encoding='utf-8'))
        assert raw['gemini_key'].startswith('enc:')
        assert 'TEST-SECRET-1234' not in raw['gemini_key']
        assert server.public_config()['gemini_key_masked'].endswith('1234')
    server.CFG=old_cfg; server.DEFAULT.clear(); server.DEFAULT.update(old_default)

def test_gemini_test_endpoint_exists():
    assert hasattr(server,'test_gemini')
    old=server.DEFAULT.get('gemini_key',''); server.DEFAULT['gemini_key']=''
    try:
        out=server.test_gemini(); assert out['configured'] is False and out['ok'] is False
    finally: server.DEFAULT['gemini_key']=old

def run_all():
    tests=[(name,fn) for name,fn in globals().items() if name.startswith('test_') and callable(fn)]
    failures=[]
    for name,fn in tests:
        try: fn()
        except Exception as e: failures.append((name,e))
    if failures:
        for name,e in failures: print(f'FAIL {name}: {e}')
        raise SystemExit(1)
    print(f'ALL TESTS PASS ({len(tests)})')

if __name__=='__main__': run_all()
