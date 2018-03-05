import asyncio, os, inspect, logging, functools

from urllib import parse

from aiohttp import web

import aiomysql, pymysql

conn = pymysql.connect(db='test', user='root', passwd='123456', host='localhost')