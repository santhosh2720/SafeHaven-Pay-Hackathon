import os, uuid
from typing import Any
import httpx

class PayPalAdapter:
    def __init__(self):
        self.client_id = os.getenv('PAYPAL_CLIENT_ID', '')
        self.secret = os.getenv('PAYPAL_SECRET', '')
        self.base = os.getenv('PAYPAL_BASE_URL', 'https://api-m.sandbox.paypal.com')

    @property
    def live(self):
        return bool(self.client_id and self.secret)

    async def token(self):
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(f'{self.base}/v1/oauth2/token', data={'grant_type':'client_credentials'}, auth=(self.client_id, self.secret), headers={'Accept':'application/json'})
            r.raise_for_status()
            return r.json()['access_token']

    async def create_authorization_order(self, amount: float, currency='USD', description='SafeHaven Pay protected order') -> dict[str, Any]:
        if not self.live:
            return {'id': f'DEMO-{uuid.uuid4().hex[:10].upper()}', 'status':'CREATED', 'demo':True, 'links':[]}
        token = await self.token()
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f'{self.base}/v2/checkout/orders', json={'intent':'AUTHORIZE','purchase_units':[{'amount':{'currency_code':currency,'value':f'{amount:.2f}'},'description':description}]}, headers={'Authorization':f'Bearer {token}','Content-Type':'application/json','PayPal-Request-Id':str(uuid.uuid4())})
            r.raise_for_status(); return r.json()

    async def authorize_order(self, order_id: str) -> dict[str, Any]:
        """Authorize an approved PayPal checkout order and return the real authorization."""
        if not self.live:
            return {'id': f'DEMO-AUTH-{uuid.uuid4().hex[:10].upper()}', 'status': 'AUTHORIZED', 'demo': True}
        token = await self.token()
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f'{self.base}/v2/checkout/orders/{order_id}/authorize',
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                    'PayPal-Request-Id': str(uuid.uuid4()),
                },
            )
            r.raise_for_status()
            return r.json()

    async def capture(self, authorization_id: str, amount: float) -> dict[str, Any]:
        if not self.live: return {'id':f'DEMO-CAP-{uuid.uuid4().hex[:10].upper()}','status':'COMPLETED','demo':True}
        token = await self.token()
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f'{self.base}/v2/payments/authorizations/{authorization_id}/capture', json={'amount':{'currency_code':'USD','value':f'{amount:.2f}'},'final_capture':True}, headers={'Authorization':f'Bearer {token}','Content-Type':'application/json','PayPal-Request-Id':str(uuid.uuid4())})
            r.raise_for_status(); return r.json()

    async def void(self, authorization_id: str) -> dict[str, Any]:
        if not self.live: return {'status':'VOIDED','demo':True}
        token = await self.token()
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f'{self.base}/v2/payments/authorizations/{authorization_id}/void', headers={'Authorization':f'Bearer {token}','PayPal-Request-Id':str(uuid.uuid4())})
            r.raise_for_status(); return r.json() if r.content else {'status':'VOIDED'}
