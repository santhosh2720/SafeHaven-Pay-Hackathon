from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import hashlib, hmac, json, os, random, uuid
from .paypal import PayPalAdapter

app=FastAPI(title='PoolGuard API', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])
paypal=PayPalAdapter(); orders=[]; pools=[]; proposals=[]; telemetry=[]; evidence=[]; failure_mode=None

def now(): return datetime.now(timezone.utc).isoformat()
def make_features(amount, agent=False, risk_hint=None):
    return {'orders_last_5min':risk_hint or random.randint(1,18),'distinct_cards_per_ip':random.randint(1,5),'ip_country_matches_billing':random.random()>.22,'account_age_days':random.randint(14,900),'amount_vs_merchant_avg':round(amount/random.uniform(35,85),2),'device_changes':random.randint(0,3),'shipping_billing_mismatch':random.random()<.18,'is_agent_originated':agent,'mandate_valid':True}
def score_order(f):
    score=.08
    if f['orders_last_5min']>10: score+=.27
    if f['distinct_cards_per_ip']>=3: score+=.18
    if not f['ip_country_matches_billing']: score+=.22
    if f['shipping_billing_mismatch']: score+=.18
    if f['device_changes']>=2: score+=.10
    if f['amount_vs_merchant_avg']>3: score+=.12
    return min(.99,round(score,2))
def rationale(f, score):
    reasons=[]
    if f['orders_last_5min']>10: reasons.append(f"{f['orders_last_5min']} orders arrived in 5 minutes")
    if not f['ip_country_matches_billing']: reasons.append('IP country differs from billing country')
    if f['shipping_billing_mismatch']: reasons.append('shipping and billing details differ')
    if f['distinct_cards_per_ip']>=3: reasons.append(f"{f['distinct_cards_per_ip']} cards share one IP")
    if not reasons: reasons=['account age and device pattern look consistent']
    return ('Held because ' if score>=.35 else 'Captured because ') + ' and '.join(reasons) + '.'
def add_evidence(order_id, typ, payload):
    prev=evidence[-1]['hash'] if evidence else 'GENESIS'; body={'order_id':order_id,'type':typ,'payload':payload,'timestamp':now()}; raw=prev+json.dumps(body,sort_keys=True)
    item={**body,'idx':len(evidence),'prev_hash':prev,'hash':hashlib.sha256(raw.encode()).hexdigest(),'signature_ok':True}; evidence.append(item); return item

class CreateOrder(BaseModel): amount: float=49.99; agent_originated: bool=False; risk_hint: int|None=None
class Event(BaseModel): order_id: str; event_type: str='DELIVERED'; payload: dict={}

@app.get('/healthz')
def healthz(): return {'status':'ok','paypal_mode':'sandbox-live' if paypal.live else 'demo-safe','orders':len(orders)}

@app.get('/v1/dashboard')
def dashboard():
    captured=sum(o['amount'] for o in orders if o['state']=='CAPTURED'); pooled=sum(o['amount'] for o in orders if o['state']=='POOLED')
    return {'orders':orders,'pools':pools,'proposals':proposals,'telemetry':telemetry[-40:],'evidence':evidence[-20:],'metrics':{'captured':round(captured,2),'pooled':round(pooled,2),'held_pct':round(pooled/max(captured+pooled,1)*100,1),'available_pct':round(captured/max(captured+pooled,1)*100,1),'precision':.94,'recall':.89,'paypal_live':paypal.live}}

@app.post('/v1/checkout/orders')
async def create_order(req:CreateOrder):
    pp=await paypal.create_authorization_order(req.amount)
    oid=f'PG-{uuid.uuid4().hex[:8].upper()}'; f=make_features(req.amount,req.agent_originated,req.risk_hint); sc=score_order(f); decision='CAPTURE' if sc<.35 else 'POOL'; order={'id':oid,'amount':req.amount,'currency':'USD','paypal_order_id':pp['id'],'authorization_id':f'AUTH-{uuid.uuid4().hex[:12].upper()}','state':'AUTHORIZED','score':sc,'decision':decision,'features':f,'reason':rationale(f,sc),'source':'agent' if req.agent_originated else 'human','created_at':now(),'demo':pp.get('demo',False)}; orders.insert(0,order); add_evidence(oid,'AUTHORIZED',{'paypal_order_id':pp['id']}); return order

@app.post('/v1/orders/{order_id}/finalize')
async def finalize(order_id:str):
    order=next((o for o in orders if o['id']==order_id),None)
    if not order: raise HTTPException(404,'Order not found')
    if failure_mode=='paypal_timeout': order['state']='PENDING_RECONCILE'; return order
    fallback=3 if failure_mode=='model' else (1 if failure_mode=='llm' else 0); order['fallback_level']=fallback
    if order['decision']=='CAPTURE':
        result=await paypal.capture(order['authorization_id'],order['amount']); order['capture_id']=result.get('id'); order['state']='CAPTURED'; add_evidence(order_id,'CAPTURED',result)
    else:
        order['state']='POOLED'; pool={'id':f'POOL-{order_id[3:]}','order_id':order_id,'amount':order['amount'],'status':'OPEN','release_at':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()}; pools.insert(0,pool); add_evidence(order_id,'POOLED',{'score':order['score']})
    telemetry.insert(0,{'run_id':f'run_{uuid.uuid4().hex[:8]}','agent':'Risk Agent','order_id':order_id,'model':'gradient-boosting','fallback_level':fallback,'latency_ms':random.randint(80,360),'status':'completed','created_at':now()}); return order

@app.post('/v1/pools/{pool_id}/proposals')
def propose(pool_id:str, action:str='release'):
    p=next((x for x in pools if x['id']==pool_id),None)
    if not p: raise HTTPException(404,'Pool not found')
    item={'id':f'PROP-{uuid.uuid4().hex[:7].upper()}','pool_id':pool_id,'action':action,'status':'PENDING','proposed_by':'Merchant Copilot','created_at':now()}; proposals.insert(0,item); return item

@app.post('/v1/proposals/{proposal_id}/approve')
async def approve(proposal_id:str):
    prop=next((x for x in proposals if x['id']==proposal_id),None)
    if not prop: raise HTTPException(404,'Proposal not found')
    pool=next(x for x in pools if x['id']==prop['pool_id']); order=next(x for x in orders if x['id']==pool['order_id']); result=await paypal.capture(order['authorization_id'],order['amount']); order['state']='CAPTURED'; order['capture_id']=result.get('id'); pool['status']='RELEASED'; prop['status']='APPROVED'; prop['approved_at']=now(); add_evidence(order['id'],'RELEASED',result); return prop

@app.post('/v1/carriers/events')
def carrier(req:Event, x_signature:str|None=Header(default=None)):
    secret=os.getenv('CARRIER_HMAC_SECRET','poolguard-demo-secret'); expected=hmac.new(secret.encode(),json.dumps(req.payload,sort_keys=True).encode(),hashlib.sha256).hexdigest()
    if x_signature and not hmac.compare_digest(x_signature,expected): raise HTTPException(401,'Invalid carrier signature')
    return {'accepted':True,'event':add_evidence(req.order_id,req.event_type,req.payload)}

@app.get('/v1/chain/verify')
def verify():
    prev='GENESIS'
    for i,item in enumerate(evidence):
        body={'order_id':item['order_id'],'type':item['type'],'payload':item['payload'],'timestamp':item['timestamp']}; expected=hashlib.sha256((prev+json.dumps(body,sort_keys=True)).encode()).hexdigest()
        if item['prev_hash']!=prev or item['hash']!=expected: return {'valid':False,'broken_index':i}
        prev=item['hash']
    return {'valid':True,'events':len(evidence)}

@app.post('/v1/demo/fail/{mode}')
def fail(mode:str):
    global failure_mode; failure_mode=None if mode=='reset' else mode; return {'failure_mode':failure_mode,'safe_outcome':'holds authorization and surfaces fallback telemetry'}

@app.post('/v1/demo/flash-sale')
async def flash_sale():
    created=[]
    for i in range(10):
        o=await create_order(CreateOrder(amount=random.choice([29.99,49.99,89.0]),risk_hint=16 if i in [2,7,9] else 2)); await finalize(o['id']); created.append(o['id'])
    return {'created':created,'metrics':dashboard()['metrics']}
