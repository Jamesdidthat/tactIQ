"""Capture the local rendered product for manual visual review via Edge CDP."""
import base64
import json
import time
import urllib.request
from pathlib import Path
import websocket

out = Path('artifacts/ui_review/revised')
out.mkdir(parents=True, exist_ok=True)
tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9223/json/list'))
ws = websocket.create_connection(tabs[0]['webSocketDebuggerUrl'], origin='http://localhost:9223', timeout=45)
serial = 0

def call(method, params=None):
    global serial
    serial += 1
    ws.send(json.dumps({'id': serial, 'method': method, 'params': params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get('id') == serial:
            if 'error' in msg:
                raise RuntimeError(msg['error'])
            return msg.get('result', {})

def js(expression):
    return call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})['result'].get('value')

def wait_for(expression, seconds=360):
    until = time.time() + seconds
    while time.time() < until:
        if js(expression):
            return
        time.sleep(1)
    raise RuntimeError('Timed out: ' + str(js('document.body.innerText')))

def capture(name):
    data = call('Page.captureScreenshot', {'captureBeyondViewport': False, 'fromSurface': True})['data']
    (out / name).write_bytes(base64.b64decode(data))

call('Emulation.setDeviceMetricsOverride', {'width': 1600, 'height': 1200, 'deviceScaleFactor': 1, 'mobile': False})
call('Page.navigate', {'url': 'http://127.0.0.1:5173'})
wait_for("document.querySelectorAll('.finding-row').length > 0")
titles = js("Array.from(document.querySelectorAll('.finding-row strong')).map(x=>x.innerText)")
print(json.dumps(titles), flush=True)
capture('overview.png')
reviews = []
for i, title in enumerate(titles):
    js(f"document.querySelectorAll('.finding-row')[{i}].click()")
    wait_for("document.querySelectorAll('.moments button').length > 0", 30)
    text = js("document.querySelector('.detail').innerText")
    js("document.querySelector('.moments button').click()")
    time.sleep(2)
    js("document.querySelector('.moments').scrollIntoView({block:'start'})")
    capture(f'finding_{i+1}.png')
    reviews.append({'title': title, 'detail': text, 'page': js('document.body.innerText')})
(out / 'rendered_findings.json').write_text(json.dumps(reviews, indent=2), encoding='utf-8')
print('Captured all finding views', flush=True)
ws.close()
