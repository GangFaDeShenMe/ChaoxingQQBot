import requests
from requests.cookies import RequestsCookieJar
import asyncio
import loguru
from xxt_api import xxt_get_cookies_by_phone_password_login
from config import c


async def l():
    global cookie
    try:
        cookie = await xxt_get_cookies_by_phone_password_login("", "")
    except Exception as e:
        print(f"{e}")

    activity_info = requests.get(
        url=f"https://mobilelearn.chaoxing.com/page/sign/signIn?courseId=&classId=6&activeId=&fid=",
        headers=c.xxt_api.request_user_agent_android_app,
        cookies=cookie)
    with open('test.html', 'w', encoding='utf-8') as f:
        f.write(activity_info.text)


asyncio.run(l())
