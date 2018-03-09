import asyncio, os, inspect, logging, functools

from urllib import parse

from aiohttp import web

import aiomysql, pymysql

help(aiomysql.create_pool())