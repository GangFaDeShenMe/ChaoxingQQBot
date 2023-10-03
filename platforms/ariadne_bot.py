import asyncio
import datetime
from typing import Union

from graia.amnesia.builtins.aiohttp import AiohttpServerService
from graia.ariadne.app import Ariadne
from graia.ariadne.connection.config import (
    HttpClientConfig,
    WebsocketClientConfig,
    config as ariadne_config, WebsocketServerConfig,
)
from graia.ariadne.event.lifecycle import AccountLaunch
from graia.ariadne.event.mirai import NewFriendRequestEvent, BotInvitedJoinGroupRequestEvent
from graia.ariadne.message import Source
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.parser.base import MentionMe
from graia.ariadne.model import Friend, Group, Member, AriadneBaseModel
from loguru import logger
from typing_extensions import Annotated

from handle_msg import handle_message
from config import c as config

# Refer to https://graia.readthedocs.io/ariadne/quickstart/
if config.mirai.reverse_ws_port:
    Ariadne.config(default_account=config.mirai.qq)
    app = Ariadne(
        ariadne_config(
            config.mirai.qq,  # 配置详见
            config.mirai.api_key,
            WebsocketServerConfig()
        ),
    )
    app.launch_manager.add_launchable(AiohttpServerService(config.mirai.reverse_ws_host, config.mirai.reverse_ws_port))
else:
    app = Ariadne(
        ariadne_config(
            config.mirai.qq,  # 配置详见
            config.mirai.api_key,
            HttpClientConfig(host=config.mirai.http_url),
            WebsocketClientConfig(host=config.mirai.ws_url),
        ),
    )


def response(target: Union[Friend, Group], source: Source):
    async def respond(msg: AriadneBaseModel, qq_number: str = None):
        await asyncio.sleep(config.respond.reply_latency)
        event = await app.send_message(
            target if qq_number is None else await Ariadne.get_friend(friend_id=int(qq_number)),
            msg
        )
        return event

    return respond


@app.broadcast.receiver("FriendMessage", priority=19)
async def friend_message_listener(target: Friend, source: Source,
                                  chain: MessageChain):
    if target.id == config.mirai.qq:
        return

    await handle_message(
        response(target, source),
        str(target.id),
        chain.display,
        chain,
        is_admin=target.id == config.mirai.manager_qq,
    )


GroupTrigger = Annotated[MessageChain, MentionMe(True)]


@app.broadcast.receiver("GroupMessage", priority=19)
async def group_message_listener(target: Group, source: Source, chain: GroupTrigger, member: Member):
    await handle_message(
        response(target, source),
        str(member.id),
        chain.display,
        chain,
        is_admin=member.id == config.mirai.manager_qq
    )


@app.broadcast.receiver("NewFriendRequestEvent")
async def on_friend_request(event: NewFriendRequestEvent):
    if config.system.accept_friend_request:
        await event.accept()


@app.broadcast.receiver("BotInvitedJoinGroupRequestEvent")
async def on_friend_request(event: BotInvitedJoinGroupRequestEvent):
    if config.system.accept_group_invite:
        await event.accept()


@app.broadcast.receiver(AccountLaunch)
async def start_background():
    logger.info("尝试从 Mirai 服务中读取机器人 QQ 的 session key……")
    if config.mirai.reverse_ws_port:
        logger.info("[提示] 当前为反向 ws 模式，请确保你的 mirai api http 设置了正确的 reverse-ws adapter 配置")
        logger.info("[提示] 配置不正确会导致 Mirai 端出现错误提示。")

    else:
        logger.info("[提示] 当前为正向 ws + http 模式，请确保你的 mirai api http 设置了正确的 ws 和 http 配置")
        logger.info("[提示] 配置不正确或 Mirai 未登录 QQ 都会导致 【Websocket reconnecting...】 提示的出现。")


async def start_task():
    """|coro|
    以异步方式启动
    """
    app._patch_launch_manager()
    await app.launch_manager.launch()
