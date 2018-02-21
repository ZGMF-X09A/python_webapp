# 导入库：
import asyncio
from aiohttp import web

import logging
logging.basicConfig(level = logging.INFO)

# 定义handler:
def index(request):
    resp = web.Response(body = b'<h1>Awesome</h1>')
    resp.content_type = 'text/html;charset=utf-8'
    return resp
    
# 通过127.0.0.1:9000访问：
async def init(loop):
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/', index)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1...')
    return srv
    
loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()