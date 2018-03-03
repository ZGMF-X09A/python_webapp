# 导入库：
import asyncio, os, inspect, logging, functools

from urllib import parse

from aiohttp import web

from apis import APIError

# 把一个函数映射为一个URL处理函数：
# 定义@get():
def get(path):
    '''
    Define decorator @get('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator
  
# 定义@post():
def post(path):
    '''
    Define decorator @post('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator
    
# 使用inspect模块，检查视图函数的参数：

# inspect.Parameter.kind 类型：
# POSITIONAL_ONLY          位置参数
# KEYWORD_ONLY             命名关键字参数
# VAR_POSITIONAL           可选参数 *args
# VAR_KEYWORD              关键字参数 **kw
# POSITIONAL_OR_KEYWORD    位置或必选参数

def get_required_kw_args(fn):  # 获取无默认值的命名关键字参数
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        # 如果视图函数存在命名关键字参数，且默认值为空，获取它的key(参数名)
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)
    
def get_named_kw_args(fn):  # 获取命名关键字参数
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)
    
def has_named_kw_args(fn):  # 判断是否有命名关键字参数
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True
            
def has_var_kw_arg(fn):  # 判断是否有关键字参数
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True
            
def has_request_arg(fn):  # 判断是否有叫'request'的参数，且位置在最后
    params = inspect.signature(fn).parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (
            param.kind != inspect.Parameter.VAR_POSITIONAL and
            param.kind != inspect.Parameter.KEYWORD_ONLY and
            param.kind != inspect.Parameter.VAR_KEYWORD):
            # 若判断为True，表明param只能是位置参数。且该参数位于request之后，故不满足条件，报错。
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found
    
# 定义RequestHandler从视图函数中分析其所需要接受的参数，从web.Request中获取必要的参数
# 调用视图函数，然后把结果转换为web.Response对象，符合aiohttp框架要求
class RequestHandler(object):
    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._required_kw_args = get_required_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._has_request_arg = has_request_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        
    # 1.定义kw，用于保存参数
    # 2.判断视图函数是否存在关键字参数，如果存在根据POST或者GET方法将request请求内容保存到kw
    # 3.如果kw为空（说明request无请求内容），则将match_info列表里的资源映射给kw；若不为空，把命名关键字参数内容给kw
    # 4.完善_has_request_arg和_required_kw_args属性
    async def __call__(self, request):
        kw = None # 定义kw，用于保存参数
        if self._has_named_kw_args or self._has_var_kw_arg: #若视图函数有命名关键字或关键字参数
            if request.method == 'POST':
                # 根据request参数中的content_type使用不同解析方法：
                if request.content_type == None: # 如果content_type不存在，返回400错误
                    return web.HTTPBadRequest(text='Missing Content_type.')
                ct = request.content_type.lower() # 小写，便于检查
                if ct.startswith('application/josn'): #json格式数据
                    params = await request.json() #仅解析body字段的json数据
                    if not isinstance(params, dict): # request.json()返回dict对象
                        return web.HTTPBadRequest(text='JSON body must be object.')
                    kw = params
                # form表单请求的编码格式
                elif ct.startswith('applicaton/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post() #返回post的内容中解析后的数据。dict-like对象。
                    kw = dict(**params) # 组成dict，统一kw格式
                else:
                    return web.HTTPBadRequest(text='Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                qs = request.query_string # 返回URL查询语句，?后的键值。string形式。
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items(): # 返回查询变量和值的映射，dict对象。True表示不忽略空格
                        kw[k] = v[0]
        if kw is None: # 若request中无参数
            # request.match_info返回dict对象。可变路由中的可变字段{variable}为参数名，传入request请求的path为值
            # 若存在可变路由：/a/{name}/c,可匹配path为：/a/jack/c的request
            # 则request.match_info返回{name = jack}
            kw = dict(**request.match_info)
        else: # request有canshu
            if self._has_named_kw_args and (not self._has_var_kw_arg): # 若视图函数中只有命名关键字参数，没有关键字参数
                copy = dict()
                # 只保留命名关键字参数
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                    kw = copy # kw中只存在命名关键字参数
                # 将request.match_info中的参数传入kw
                for k, v in request.match_info.items():
                # 检查kw中的参数是否和match_info中的重复
                    if k in kw:
                        logging.warn('Duplicate are name in named arg and kw args: %s' % k)
                    kw[k] = v 
            if self._has_request_arg: # 视图函数存在request参数
                kw['request'] = request
            if self._required_kw_args: # 视图函数存在无默认值的命名关键字参数
                for name in self._required_kw_args:
                    if not name in kw: #若未传入必须参数值，报错
                        return web.HTTPBadRequest('Missing arguement: %s' % name)
            # 至此，kw为视图函数fn真正能调用的参数
            # request请求中的参数，终于传递给了视图函数
            logging.info('call with args: %s' % str(kw))
            # try:
            r = await self._func(**kw)
            return r 
            # except APIError as e:
                # return dict(error=e.error, data=e.data, message=e.message)
    
# 编写add_route函数，用来注册一个URL处理函数：
def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if mothod is None or route is None:
        raise ValueError('@get or @psot not defined in %s.' % fn.__name__)
	# 判断URL处理函数是否是协程或是生成器
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
		# 将fn转变成协程
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    # 在app中注册经RequestHandler类封装的视图函数
    app.router.add_route(method, path, RequestHandler(app, fn))
    
# 自动扫描完成多次add_route()注册的调用:
def add_routes(app, module_name):
    n = module_name.rfind('.')
    if n == (-1):
		# __import__ 作用同import语句，但__import__是一个函数，只接收字符串作为参数
		# __import__('os', globals(), locals(), ['path', 'pip'], 0),等价于from os import path, pip
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod): #dir()迭代出mod模块中所有的类，实例及函数等对象，str形式
        if attr.startswith('_'):
            continue # 忽略'_'开头的对象，直接继续for循环
        fn = getattr(mod, attr)
		# 确保是函数
        if callable(fn):
			# 确保视图函数中存在method和path
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
				# 注册
                add_route(app, fn)
				
# 编写add_static函数用于注册静态文件，只提供文件路径即可进行注册
# 添加静态文件，如image,css,javascript等
def add_static(app):
	# 拼接static文件目录
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
	# path = os.path.join(os.path.abspath('.'), 'static')
	
	app.router.add_static('/static/', path)
	logging.info('add static %s => %s' % ('/static/', path))