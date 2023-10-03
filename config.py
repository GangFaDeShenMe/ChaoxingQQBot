from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
from charset_normalizer import from_bytes
from loguru import logger
import sys
import toml

'''
class Onebot(BaseModel):
    qq: int
    """Bot 的 QQ 号"""
    manager_qq: int = 0
    """机器人管理员的 QQ 号"""
    reverse_ws_host: str = "0.0.0.0"
    """go-cqhttp 的 反向 ws 主机号"""
    reverse_ws_port: Optional[int] = 8566
    """go-cqhttp 的 反向 ws 端口号，填写后开启 反向 ws 模式"""
'''


class Mirai(BaseModel):
    qq: int
    """Bot 的 QQ 号"""
    manager_qq: int = 0
    """机器人管理员的 QQ 号"""
    api_key: str = "1234567890"
    """mirai-api-http 的 verifyKey"""
    http_url: str = "http://localhost:8080"
    """mirai-api-http 的 http 适配器地址"""
    ws_url: str = "http://localhost:8080"
    """mirai-api-http 的 ws 适配器地址"""
    reverse_ws_host: str = "0.0.0.0"
    """mirai-api-http 的 反向 ws 主机号"""
    reverse_ws_port: Optional[int] = None
    """mirai-api-http 的 反向 ws 端口号，填写后开启 反向 ws 模式"""


class System(BaseModel):
    accept_group_invite: bool = False
    """自动接收邀请入群请求"""

    accept_friend_request: bool = False
    """自动接收好友请求"""

    web_requests_lantency: float = 0.5
    """每个web请求之间的延迟，对所有请求适用，不分用户"""


class Respond(BaseModel):
    new_user_message: str = "欢迎新用户使用。本程序具有这些功能：..."
    """对于数据库内没有QQ号记录的用户首先发送的消息，需要用户主动触发"""

    reply_latency: float = 1
    """每条消息回复之间的延迟，对所有消息适用，不分用户"""


class XxtAPI(BaseModel):
    request_user_agent: dict = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Dnt": "1",
        "Referer": "https://passport2.chaoxing.com/login?fid=&newversion=true&refer=https://i.chaoxing.com",
        "Sec-Ch-Ua": '"Google Chrome";v="117", "Not;A=Brand";v="8", "Chromium";v="117"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": "Windows",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }
    """自定义请求UA"""

    request_user_agent_android_app: dict = {
        "Connection": "keep-alive",
        "sec-ch-ua": '"Android WebView";v="117", "Not;A=Brand";v="8", "Chromium";v="117"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": "Android",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G9980 Build/TP1A.220624.014; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/117.0.0.0 Mobile Safari/537.36(schild:def3706876ea1a13613591dbdd242d6b) (device:SM-G9980) Language/zh_CN com.chaoxing.mobile/ChaoXingStudy_3_6.2.3_android_phone_1000_115 (@Kalimdor)_724fd66a6e2d35dbc1bf74908d149990",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "zh_CN",
        "X-Requested-With": "com.chaoxing.mobile",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Accept-Encoding": "gzip, deflate, br"
    }
    """签到及查询签到活动时使用的UA"""

    xxt_login_encrypt_scheme: str = "aes"  # aes, des, base64
    """登录时，向服务器发送的密码的加密算法"""

    xxt_login_encrypt_key: str = "u2oh6Vu^HWe4_AES"
    """加密密钥，只在对称加密算法(aes, des...)有效"""


class Db(BaseModel):
    sqlalchemy_db_url: str = ''
    '''参考文档：https://www.osgeo.cn/sqlalchemy/core/engines.html#database-urls'''


class Config(BaseModel):
    # === Platform Settings ===
    # onebot: Optional[Onebot] = None
    mirai: Optional[Mirai] = None

    # === General Settings ===
    system: System = System()

    # === Respond Settings ===
    respond: Respond = Respond()

    # === XXT API Settings ===
    xxt_api: XxtAPI = XxtAPI()

    # === Database Settings ===
    db: Db = Db()

    @staticmethod
    def load_config() -> Config:
        try:
            with open("config.cfg", "rb") as f:
                if guessed_str := from_bytes(f.read()).best():
                    return Config.parse_obj(toml.loads(str(guessed_str)))
                else:
                    raise ValueError("无法识别配置文件，请检查是否输入有误！")
        except Exception as e:
            logger.exception(e)
            logger.error("配置文件有误，请重新修改！")
            exit(-1)

    @staticmethod
    def save_config(config: Config):
        try:
            with open("config.cfg", "wb") as f:
                parsed_str = toml.dumps(config.dict()).encode(sys.getdefaultencoding())
                f.write(parsed_str)
        except Exception as e:
            logger.exception(e)
            logger.warning("配置保存失败。")


try:
    logger.info("载入配置文件")
    c = Config.load_config()
except Exception as e:
    logger.error("配置文件有误")
    logger.exception(e)
    exit(1)


class ConfigError(Exception):
    """Raised when there is an error in the configuration file."""
    pass


logger.success("载入配置文件成功")
