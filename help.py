import asyncio, os, inspect, logging, functools

from urllib import parse

from aiohttp import web

import pymysql


pymysql.connect(db='base', user='root', passwd='123456', host='localhost', port=3306)