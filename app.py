import argparse
import hashlib
import logging
import os
from urllib.parse import unquote_plus

import shutil
import requests
from flask import Flask, request, abort, redirect, send_from_directory, Response, jsonify, render_template_string, \
    make_response
from flask_caching import Cache
from waitress import serve
import concurrent.futures

from mod import api, lrc, tags
from mod.auth import webui, cookie


# 创建一个解析器
parser = argparse.ArgumentParser(description="启动LRCAPI服务器")
# 添加一个 `--port` 参数，默认值28883
parser.add_argument('--port', type=int, default=28883, help='应用的运行端口，默认28883')
parser.add_argument('--auth', type=str, help='用于验证Header.Authentication字段，建议纯ASCII字符')
args, unknown_args = parser.parse_known_args()
# 赋值到token，启动参数优先性最高，其次环境变量，如果都未定义则赋值为false
token = args.auth if args.auth is not None else os.environ.get('API_AUTH', False)

app = Flask(__name__)

# 缓存逻辑
cache_dir = './flask_cache'
try:
    # 尝试删除缓存文件夹
    shutil.rmtree(cache_dir)
except FileNotFoundError:
    pass
cache = Cache(app, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': cache_dir
})


# 鉴权函数，在token存在的情况下，对请求进行鉴权
# permission=0 代表最小权限
def require_auth(permission=0):
    # 如果已经定义了鉴权请求头
    if token is not False:
        user_cookie = request.cookies.get("api_auth_token", "")
        # logger.info(user_cookie)
        auth_header = request.headers.get('Authorization', False) or request.headers.get('Authentication', False)
        if (auth_header and auth_header == token) or cookie.check_cookie(user_cookie):
            return 1
        else:
            return -1
    # 没有定义请求头的情况，判断是不是强制要求鉴权，permission>0就是需要鉴权
    else:
        if permission:
            return -2
        else:
            return 1


# 缓存键，解决缓存未忽略参数的情况
def make_cache_key(*args, **kwargs):
    path = request.path
    args = str(hash(frozenset(request.args.items())))
    return path + args


# hash计算器
def calculate_md5(string):
    # 创建一个 md5 对象
    md5_hash = hashlib.md5()

    # 将字符串转换为字节流并进行 MD5 计算
    md5_hash.update(string.encode('utf-8'))

    # 获取计算结果的十六进制表示，并去掉开头的 "0x"
    md5_hex = md5_hash.hexdigest()
    md5_hex = md5_hex.lstrip("0x")

    return md5_hex


# 跟踪重定向
def follow_redirects(url, max_redirects=10):
    for _ in range(max_redirects):
        response = requests.head(url, allow_redirects=False)
        if response.status_code == 200:
            return url
        elif 300 <= response.status_code < 400:
            url = response.headers['Location']
        else:
            abort(404)  # 或者根据需求选择其他状态码
    abort(404)  # 达到最大重定向次数仍未获得 200 状态码，放弃


def read_file_with_encoding(file_path, encodings):
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return None


@app.route('/lyrics', methods=['GET'])
@cache.cached(timeout=86400, key_prefix=make_cache_key)
def lyrics():
    match require_auth():
        case -1:
            return render_template_string(webui.error()), 403
        case -2:
            return render_template_string(webui.error()), 421
    if not bool(request.args):
        abort(404, "请携带参数访问")
    # 通过request参数获取文件路径
    path = unquote_plus(request.args.get('path', ''))
    # 根据文件路径查找同名的 .lrc 文件
    if path:
        lrc_path = os.path.splitext(path)[0] + '.lrc'
        if os.path.isfile(lrc_path):
            file_content = read_file_with_encoding(lrc_path, ['utf-8', 'gbk'])
            if file_content is not None:
                return lrc.standard(file_content)
    try:
        lrc_in = tags.r_lrc(path)
        return lrc_in
    except:
        pass
    try:
        # 通过request参数获取音乐Tag
        title = unquote_plus(request.args.get('title'))
        artist = unquote_plus(request.args.get('artist', ''))
        album = unquote_plus(request.args.get('album', ''))
        executor = concurrent.futures.ThreadPoolExecutor()
        # 提交任务到线程池，并设置超时时间
        future = executor.submit(api.main, title, artist, album)
        lyrics_text = future.result(timeout=30)
        return lrc.standard(lyrics_text)
    except:
        return "Lyrics not found.", 404


@app.route('/jsonapi', methods=['GET'])
@cache.cached(timeout=86400, key_prefix=make_cache_key)
def lrc_json():
    match require_auth():
        case -1:
            return render_template_string(webui.error()), 403
        case -2:
            return render_template_string(webui.error()), 421
    if not bool(request.args):
        abort(404, "请携带参数访问")
    path = unquote_plus(request.args.get('path'))
    title = unquote_plus(request.args.get('title'))
    artist = unquote_plus(request.args.get('artist', ''))
    album = unquote_plus(request.args.get('album', ''))
    response = []
    if path:
        lrc_path = os.path.splitext(path)[0] + '.lrc'
        if os.path.isfile(lrc_path):
            file_content = read_file_with_encoding(lrc_path, ['utf-8', 'gbk'])
            if file_content is not None:
                file_content = lrc.standard(file_content)
                response.append({
                    "id": calculate_md5(file_content),
                    "title": title,
                    "artist": artist,
                    "lyrics": file_content
                })

    lyrics_list = api.allin(title, artist, album)
    if lyrics_list:
        for i in lyrics_list:
            i = lrc.standard(i)
            response.append({
                "id": calculate_md5(i),
                "title": title,
                "artist": artist,
                "lyrics": i
            })
    return jsonify(response)


@app.route('/cover', methods=['GET'])
@cache.cached(timeout=86400, key_prefix=make_cache_key)
def cover_api():
    req_args = {key: request.args.get(key) for key in request.args}
    # 构建目标URL
    target_url = 'https://lrc.xms.mx/cover?' + '&'.join([f"{key}={req_args[key]}" for key in req_args])
    # 跟踪重定向并获取最终URL
    final_url = follow_redirects(target_url)
    # 获取最终URL的内容或响应
    response = requests.get(final_url)
    if response.status_code == 200:
        content_type = response.headers.get('Content-Type', 'application/octet-stream')
        return Response(response.content, content_type=content_type)
    else:
        abort(404)


def validate_json_structure(data):
    if not isinstance(data, dict):
        return False
    if "path" not in data:
        return False
    return True


@app.route('/tag', methods=['POST'])
def setTag():
    match require_auth():
        case -1:
            return render_template_string(webui.error()), 403
        case -2:
            return render_template_string(webui.error()), 421

    musicData = request.json
    if not validate_json_structure(musicData):
        return "Invalid JSON structure.", 422

    audio_path = musicData.get("path")
    if not audio_path:
        return "Missing 'path' key in JSON.", 422

    if not os.path.exists(audio_path):
        return "File not found.", 404

    supported_tags = {
        "title": "title",
        "artist": "artist",
        "album": "album",
        "lyrics": "lyrics"
    }

    tags_to_set = {supported_tags[key]: value for key, value in musicData.items() if key in supported_tags}
    result = tags.w_file(audio_path, tags_to_set)
    if result == 0:
        return "OK", 200
    elif result == -1:
        return "Failed to write lyrics", 523
    elif result == -2:
        return "Failed to write tags", 524
    else:
        return "Unknown error", 525


@app.route('/')
def redirect_to_welcome():
    return redirect('/src')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory('src', 'img/Logo_Design.svg')


@app.route('/src')
def return_index():
    return send_from_directory('src', 'index.html')


@app.route('/src/<path:filename>')
def serve_file(filename):
    try:
        return send_from_directory('src', filename)
    except FileNotFoundError:
        abort(404)


@app.route('/login')
def login_check():
    if require_auth() < 0 and len(token) > 0:
        return render_template_string(webui.html_login())

    return redirect('/src')


@app.route('/login-api', methods=['POST'])
def login_api():
    data = request.get_json()
    if 'password' in data:
        pwd = data['password']
        if pwd == token:
            response = make_response(jsonify(success=True))
            response.set_cookie('api_auth_token', cookie.set_cookie())
            return response

    return jsonify(success=False)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger('')
    logger.info("正在启动服务器")
    serve(app, host='0.0.0.0', port=args.port, threads=32, channel_timeout=50)
    # app.run(host='0.0.0.0', port=args.port)
