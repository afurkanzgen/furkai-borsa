"""FurkAI FastAPI/WSGI replacement layer. Existing server.py remains the domain layer during migration."""
import asyncio, os, time
from pathlib import Path
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()
import server
from notification_service import service
from backtest_engine import BacktestEngine

BASE=Path(__file__).resolve().parent
app=FastAPI(title='FurkAI BIST', version=server.APP_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

RATE_LIMIT=int(os.getenv('FURKAI_RATE_LIMIT','120'))
WINDOW=60
_hits={}

def rate_guard(request: Request):
    ip=request.client.host if request.client else 'local'
    now=time.time(); bucket=[t for t in _hits.get(ip,[]) if now-t<WINDOW]
    if len(bucket)>=RATE_LIMIT: raise HTTPException(429,'Rate limit aşıldı; lütfen biraz sonra tekrar deneyin.')
    bucket.append(now); _hits[ip]=bucket

def auth_guard(request: Request):
    user=server.auth_user(request.headers)
    if not user: raise HTTPException(401,'Kimlik doğrulama gerekli')
    request.state.user=user
    return user

def payload(request: Request):
    rate_guard(request)
    if request.url.path.startswith('/api/') and request.url.path != '/api/health': return auth_guard(request)
    return None

@app.get('/')
@app.get('/index.html')
async def index(): return FileResponse(BASE/'index.html',media_type='text/html')

@app.get('/manifest.webmanifest')
async def manifest(): return FileResponse(BASE/'manifest.webmanifest',media_type='application/manifest+json')
@app.get('/sw.js')
async def sw(): return FileResponse(BASE/'sw.js',media_type='application/javascript')
@app.get('/app.js')
async def app_js(): return FileResponse(BASE/'app.js',media_type='text/javascript')
@app.get('/icon-180.png')
@app.get('/icon-512.png')
async def icon(request: Request): return FileResponse(BASE/request.url.path.lstrip('/'))



@app.post('/api/auth/register')
async def auth_register(request: Request):
    rate_guard(request)
    body=await request.json()
    try:
        user=server.create_user(body.get('username',''),body.get('password',''))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    token=server.create_session(user['id'])
    return {'ok':True,'token':token,'user':user}

@app.post('/api/auth/login')
async def auth_login(request: Request):
    rate_guard(request)
    body=await request.json()
    user=server.authenticate_user(body.get('username',''),body.get('password',''))
    if not user: raise HTTPException(401,'Kullanıcı adı veya şifre hatalı')
    return {'ok':True,'token':server.create_session(user['id']),'user':user}

@app.get('/api/auth/me')
async def auth_me(request: Request):
    user=auth_guard(request); return {'ok':True,'user':user}

@app.post('/api/auth/logout')
async def auth_logout(request: Request):
    user=auth_guard(request); raw=str(request.headers.get('Authorization','')); server.revoke_session(raw[7:].strip() if raw.startswith('Bearer ') else ''); return {'ok':True}

@app.get('/api/docs-info')
async def docs_info(): return {'ok':True,'fastapi':True,'websocket':'/ws/signals','rate_limit_per_minute':RATE_LIMIT,'telegram':service.telegram_configured}

@app.get('/api/{path:path}')
async def api_get(path: str, request: Request):
    user=payload(request)
    q=request.query_params
    try:
        if path=='health': return server.public_config() | {'ok':True,'app':'FurkAI BIST'}
        if path=='config': return server.public_config(user)
        if path=='data-status': return server.data_status()
        if path=='market-regime': return server.market_regime()
        if path=='universe': return server.universe()
        if path=='quote': return server.quote(q.get('symbol','THYAO'))
        if path=='quotes': return server.quotes([x.strip() for x in q.get('symbols','THYAO').split(',') if x.strip()])
        if path=='history': return {'ok':True,'data':server.history(q.get('symbol','THYAO'),q.get('range','1y'),q.get('interval','1d'))}
        if path=='analyze': return {'ok':True,'data':server.analyze(q.get('symbol','THYAO'),q.get('range','1y'))}
        if path=='portfolio': return {'ok':True,'portfolio':server.load_portfolio(user['id'])}
        if path=='portfolio/intelligence': return server.portfolio_intelligence(user['id'])
        if path=='backtest': return BacktestEngine(server.backtest).run(q.get('symbol','THYAO'),int(q.get('days','365')),float(q.get('initial','100000')))
        if path=='kap': return server.kap_info(q.get('symbol','THYAO'))
        if path=='dividends-dashboard': return server.dividend_dashboard(user['id'])
        if path=='dividends':
            d=server.yahoo_chart(q.get('symbol','THYAO'),'5y','1d'); div=d.get('events',{}).get('dividends',{}); vals=[]
            for ts,x in div.items(): vals.append({'date':time.strftime('%Y-%m-%d',time.localtime(int(ts))),'amount':x.get('amount'),'symbol':d['symbol']})
            return {'ok':True,'dividends':sorted(vals,key=lambda x:x['date'],reverse=True)}
        if path=='signals': return server.signal_history(int(q.get('limit','200')),q.get('symbol'))
        if path=='scan': return server.scan({'period':q.get('range','1y'),'limit':int(q.get('limit','200')),'minimum_score':int(q.get('min','60')),'models':[x for x in q.get('models','').split('|') if x],'mode':q.get('mode','AND'),'min_models':q.get('min_models') or None}, user['id'])
        if path=='notifications/status': return {'ok':True,'telegram_configured':service.telegram_configured}
        raise HTTPException(404,'Not found')
    except HTTPException: raise
    except Exception as e: return JSONResponse({'ok':False,'error':str(e)},500)

@app.post('/api/{path:path}')
async def api_post(path: str, request: Request):
    user=payload(request); body=await request.json()
    try:
        if path=='config':
            if not user.get('is_admin'): raise HTTPException(403,'Paylaşılan uygulama ayarlarını yalnızca yönetici değiştirebilir')
            return server.save_config(body)
        if path=='portfolio/save': server.save_portfolio(body.get('portfolio',[]), user['id']); return {'ok':True,'portfolio':server.load_portfolio(user['id'])}
        if path=='gemini-test': return server.test_gemini()
        if path=='scan': return server.scan(body, user['id'])
        if path=='ai':
            sym=str(body.get('symbol','THYAO')).upper(); a=server.analyze(sym); return server.gemini(body.get('prompt') or f'BIST {sym} teknik verisini JSON olarak analiz et: {a}')
        if path=='notifications/test': return service.telegram('FurkAI BIST test bildirimi')
        if path=='notifications/signal': return service.signal(body.get('symbol','THYAO'),body.get('decision','TEST'),body.get('score'),body.get('price'),body.get('reason'))
        raise HTTPException(404,'Not found')
    except HTTPException: raise
    except Exception as e: return JSONResponse({'ok':False,'error':str(e)},500)

@app.websocket('/ws/signals')
async def ws_signals(ws: WebSocket):
    user=server.auth_user(ws.headers)
    if not user:
        token=ws.query_params.get('token','')
        user=server.session_user(token) if token else None
    if not user:
        await ws.close(code=4401); return
    await ws.accept()
    try:
        await ws.send_json({'type':'connected','version':server.APP_VERSION,'interval':30})
        while True:
            await asyncio.sleep(30)
            try:
                result=await asyncio.to_thread(server.scan,{'period':'1y','limit':20,'minimum_score':70,'models':[],'mode':'OR','min_models':None}, user['id'])
                await ws.send_json({'type':'scan','data':result})
            except Exception as e:
                await ws.send_json({'type':'error','error':str(e)})
    except WebSocketDisconnect: pass


