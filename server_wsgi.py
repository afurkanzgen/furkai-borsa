import json, os, urllib.parse, time
from pathlib import Path
import server

BASE=Path(__file__).resolve().parent

def _auth_headers(environ):
    class H:
        def get(self,k,d=''):
            return environ.get('HTTP_AUTHORIZATION', d) if k.lower()=='authorization' else d
    return H()

def _json(start_response, payload, status='200 OK'):
    body=json.dumps(payload, ensure_ascii=False).encode('utf-8')
    start_response(status,[('Content-Type','application/json; charset=utf-8'),('Content-Length',str(len(body)))])
    return [body]

def app(environ, start_response):
    path=environ.get('PATH_INFO','/')
    method=environ.get('REQUEST_METHOD','GET').upper()
    if path in ('/','/index.html') and method in ('GET','HEAD'):
        body=(BASE/'index.html').read_bytes()
        start_response('200 OK',[('Content-Type','text/html; charset=utf-8'),('Content-Length',str(len(body)))])
        return [body] if method=='GET' else [b'']
    static = {
        '/manifest.webmanifest': ('application/manifest+json', BASE/'manifest.webmanifest'),
        '/sw.js': ('application/javascript', BASE/'sw.js'),
        '/icon-180.png': ('image/png', BASE/'icon-180.png'),
        '/icon-512.png': ('image/png', BASE/'icon-512.png'),
    }
    if path in static and static[path][1].exists() and method in ('GET','HEAD'):
        ctype, fp = static[path]
        data=fp.read_bytes()
        start_response('200 OK',[('Content-Type',ctype),('Content-Length',str(len(data)))])
        return [data] if method=='GET' else [b'']
    if path=='/api/health' and method in ('GET','HEAD'):
        payload={'ok':True,'app':'FurkAI BIST','version':server.DEFAULT.get('app_version',server.APP_VERSION),'source':'Yahoo Finance/KAP public data'}
        if method=='HEAD':
            start_response('200 OK',[('Content-Type','application/json; charset=utf-8')])
            return [b'']
        return _json(start_response, payload)
    if path=='/api/config' and method in ('GET','HEAD'):
        user=server.auth_user(_auth_headers(environ))
        if not user: return _json(start_response, {'ok':False,'error':'Kimlik doğrulama gerekli'}, '401 Unauthorized')
        if method=='HEAD':
            start_response('200 OK',[('Content-Type','application/json; charset=utf-8')])
            return [b'']
        return _json(start_response, server.public_config(user))
    if path=='/api/data-status' and method in ('GET','HEAD'):
        user=server.auth_user(_auth_headers(environ))
        if not user: return _json(start_response, {'ok':False,'error':'Kimlik doğrulama gerekli'}, '401 Unauthorized')
        if method=='HEAD':
            start_response('200 OK',[('Content-Type','application/json; charset=utf-8')])
            return [b'']
        return _json(start_response, server.data_status())
    user=server.auth_user(_auth_headers(environ)) if path.startswith('/api/') else None
    if path.startswith('/api/') and not user:
        return _json(start_response, {'ok':False,'error':'Kimlik doğrulama gerekli'}, '401 Unauthorized')
    query=urllib.parse.parse_qs(environ.get('QUERY_STRING',''))
    try:
        if method=='GET':
            if path=='/api/universe': return _json(start_response,server.universe())
            if path=='/api/quote': return _json(start_response,server.quote(query.get('symbol',['THYAO'])[0]))
            if path=='/api/quotes': return _json(start_response,server.quotes(query.get('symbols',['THYAO,ASELS'])[0].split(',')))
            if path=='/api/history': return _json(start_response,{'ok':True,'data':server.history(query.get('symbol',['THYAO'])[0],query.get('range',['1y'])[0],query.get('interval',['1d'])[0])})
            if path=='/api/analyze': return _json(start_response,{'ok':True,'data':server.analyze(query.get('symbol',['THYAO'])[0],query.get('range',['1y'])[0])})
            if path=='/api/portfolio': return _json(start_response,{'ok':True,'portfolio':server.load_portfolio(user['id'])})
            if path=='/api/portfolio/intelligence': return _json(start_response,server.portfolio_intelligence(user['id']))
            if path=='/api/market-regime': return _json(start_response,server.market_regime())
            if path=='/api/backtest': return _json(start_response,server.backtest(query.get('symbol',['THYAO'])[0],int(query.get('days',['365'])[0]),float(query.get('initial',['100000'])[0])))
            if path=='/api/kap': return _json(start_response,server.kap_info(query.get('symbol',['THYAO'])[0]))
            if path=='/api/dividends':
                d=server.yahoo_chart(query.get('symbol',['THYAO'])[0],'5y','1d'); div=d.get('events',{}).get('dividends',{}); vals=[]
                for ts,x in div.items(): vals.append({'date':time.strftime('%Y-%m-%d',time.localtime(int(ts))),'amount':x.get('amount'),'symbol':d['symbol']})
                return _json(start_response,{'ok':True,'dividends':sorted(vals,key=lambda x:x['date'],reverse=True)})
            if path=='/api/scan': return _json(start_response,server.scan({'period':query.get('range',['1y'])[0],'limit':int(query.get('limit',['200'])[0]),'minimum_score':int(query.get('min',['60'])[0]),'models':[x for x in query.get('models',[''])[0].split('|') if x],'mode':query.get('mode',['AND'])[0],'min_models':(query.get('min_models',[None])[0] if query.get('min_models',[None])[0] not in (None,'') else None)},user['id']))
            if path=='/api/signals': return _json(start_response,server.signal_history(int(query.get('limit',['200'])[0]),query.get('symbol',[None])[0]))
        if method=='POST':
            n=int(environ.get('CONTENT_LENGTH','0') or 0); raw=environ['wsgi.input'].read(n) if n else b'{}'; body=json.loads(raw or b'{}')
            if path=='/api/portfolio/save': server.save_portfolio(body.get('portfolio',[])); return _json(start_response,{'ok':True,'portfolio':server.load_portfolio(user['id'])})
            if path=='/api/config':
                if not user.get('is_admin'): return _json(start_response,{'ok':False,'error':'Paylaşılan uygulama ayarlarını yalnızca yönetici değiştirebilir'},'403 Forbidden')
                return _json(start_response,server.save_config(body))
            if path=='/api/gemini-test': return _json(start_response,server.test_gemini())
            if path=='/api/ai':
                sym=str(body.get('symbol','THYAO')).upper(); a=server.analyze(sym); prompt=body.get('prompt') or f'BIST hissesi {sym} için aşağıdaki teknik veriyi yorumla. Veri uydurma. AL/TUT/IZLE/SAT kararı ver, güven 0-100, giriş/stop/hedef ve riskleri belirt. Teknik veri: {json.dumps(a,ensure_ascii=False)}'; return _json(start_response,server.gemini(prompt))
            if path=='/api/scan': return _json(start_response,server.scan(body,user['id']))
        return _json(start_response,{'ok':False,'error':'Not found'},'404 Not Found')
    except Exception as e:
        return _json(start_response,{'ok':False,'error':str(e)},'500 Internal Server Error')

if __name__=='__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=int(os.environ.get('PORT','8799')), threads=8)
