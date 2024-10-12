from . import *

from flask import request

@jel_bp.route('/System/Ping', methods=['GET'])
def ping_server():
    return "Simple Jellyfin Server"

@jel_bp.route('/Users/AuthenticateByName', methods=['POST'])
def authenticate_user():
    username: str = request.json.get('Username')
    password: str = request.json.get('Pw')
    app_string: str = request.headers.get("Authorization")
