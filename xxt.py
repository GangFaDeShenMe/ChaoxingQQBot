import os, sys

sys.path.append(os.getcwd())

import creart
from asyncio import AbstractEventLoop
import asyncio
from loguru import logger
from config import c
import db.db, platforms

loop = creart.create(AbstractEventLoop)

bots = []

platform_class_names = {
    'mirai': 'ariadne_bot',
    # 'onebot': 'onebot_bot'
}

for platform, module in platform_class_names.items():
    if getattr(c, platform):
        logger.info(f"检测到 {platform} 配置，将启动 {module} 模式……")
        module = __import__(f'platforms.{module}', fromlist=['start_task'])
        bots.append(loop.create_task(module.start_task()))

loop.run_until_complete(asyncio.gather(*bots))
loop.run_forever()


