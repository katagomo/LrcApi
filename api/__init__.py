import shutil
import logging
import sys
import os

from flask import Flask, Blueprint, request
from flask_caching import Cache


app = Flask(__name__)
logger = logging.getLogger(__name__)

v1_bp = Blueprint('v1', __name__, url_prefix='/api/v1')
# Blueprint直接复制app配置项
v1_bp.config = app.config.copy()

# 添加Access-Control-Allow-Origin项以让H5客户端可以使用API
@v1_bp.after_request
def add_custom_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

# 缓存逻辑
cache_dir = './flask_cache'
try:
    # 尝试删除缓存文件夹
    shutil.rmtree(cache_dir)
except FileNotFoundError:
    pass
# 定义缓存逻辑为本地文件缓存，目录为cache_dir = './flask_cache'
cache = Cache(app, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': cache_dir
})


# 缓存键，解决缓存未忽略参数的情况
def make_cache_key(*args, **kwargs):
    path = request.path
    args = str(hash(frozenset(request.args.items())))
    return path + args

def get_base_path():
    """
    获取程序运行路径
    如果是打包后的exe文件，则返回打包资源路径
    """
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.getcwd()


src_path = os.path.join(get_base_path(), 'src')     # 静态资源路径

__all__ = ['app', 'v1_bp', 'cache', 'make_cache_key', 'logger', 'src_path']
