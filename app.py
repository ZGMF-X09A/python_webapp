# 导入库：
import asyncio, os, json, time
from aiohttp import web
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

import orm
from coroweb import add_route, add_static

import logging
logging.basicConfig(level = logging.INFO)

# 初始化jinja2模板：
def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    options = dict(
        autoescape = kw.get('autoescape', True),
        block_start_string = kw.get('block_start_string', '{%'),
        block_end_string = kw.get('block_end_string', '%}'),
        variable_start_string = kw.get('variable_start_string', '{{'),
        variable_end_string = kw.get('variable_end_string', '}}'),
        auto_reload = kw.get('auto_reload', True)
    )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path: %s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f 
    app['__templating__'] = env
    
# 定义handler:
def index(request):
    resp = web.Response(body = b'<h1>Awesome</h1>')
    resp.content_type = 'text/html;charset=utf-8'
    return resp
    
# 通过127.0.0.1:9000访问：
async def init(loop):
    await orm.create_pool(loop=loop, host='127.0.0.1', port=3306, user='www', password='www', db='awesome')
    app = web.Application(loop=loop, middlewares=[
        logger_factory, response_factory
    ])
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, 'handlers')
    add_static(app)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1...')
    return srv
    
loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()