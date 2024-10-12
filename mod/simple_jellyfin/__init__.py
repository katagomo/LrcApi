import time
import json
import re

from mod.auth import cookie

def singleton(cls):
    """
    单例模式装饰器
    """
    instances = {}
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return get_instance

@singleton
class SimpleJellyfin:
    # 单用户的简单Jellyfin服务端实现
    def __init__(self, username, password):
        self.username = username
        self.password = password
        if not self.username or not self.password:
            raise ValueError("username and password must be set")

    def auth_generate(self, expire=86400) -> str:
        """
        生成一个Jellyfin的认证Token
        :param expire: 过期时间（秒），默认一天
        :return: 加密后的Token
        """
        now: float = time.time()
        plain_text: str = json.dumps({'username': self.username, 'password': self.password, 'expire': now + expire})
        return cookie.set_cookie(plain_text)

    def auth_check(self, token: str) -> bool:
        """
        检查Token是否有效
        :param token: 加密后的Token
        :return: 是否有效
        """
        return cookie.cookie_key(token) == self.password

    @staticmethod
    def parse_authorize_header(authorize_header:str) -> dict[str, str]:
        pattern = r'\s*([^=]+)\s*=\s*"([^"]*)"'
        matches = re.findall(pattern, authorize_header.replace(',', ''))

        return {key: value for key, value in matches}

