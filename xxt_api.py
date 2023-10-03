from __future__ import annotations

import datetime
import json
import re
import lxml

import requests, base64
from requests import utils
import time
from base64 import b64encode
from Crypto.Cipher import AES, DES
from Crypto.Util.Padding import pad
from requests.cookies import RequestsCookieJar
from bs4 import BeautifulSoup
import asyncio
from loguru import logger as l

import db.crud
from config import c, ConfigError
from db.db_models import User, Course, SignInActivity


class IncorrectPasswordError(Exception):
    """Raised when the provided password is incorrect."""

    def __init__(self, message="Incorrect password provided."):
        self.message = message
        super().__init__(self.message)


class LoginError(Exception):
    """Raised when there's a general login error."""

    def __init__(self, message="Error occurred during login."):
        self.message = message
        super().__init__(self.message)


class GetCoursesError(Exception):
    """Raised when getting courses failed."""

    def __init__(self, message="Error occurred during getting courses."):
        self.message = message
        super().__init__(self.message)


async def xxt_get_courses_raw(cookies: RequestsCookieJar) -> str:
    try:
        await asyncio.sleep(c.system.web_requests_lantency)
        resp = requests.post("https://mooc2-ans.chaoxing.com/mooc2-ans/visit/courselistdata",
                             headers=c.xxt_api.request_user_agent, cookies=cookies, data={
                "courseType": 1,
                "courseFolderId": 0,
                "query": "",
                "superstarClass": 0
            })

        return resp.text
    except Exception as e:
        raise GetCoursesError(f"无法从学习通服务器取得课程列表 {str(e)}")


def xxt_parse_raw_courses_to_courses_list(courses_raw: str) -> list[Course]:
    courses = []

    try:
        soup = BeautifulSoup(courses_raw, 'html.parser')
        courses_raw_list = soup.find_all('li', class_='course')
    except Exception as e:
        raise GetCoursesError(f"无法解析取得的课程网页 {str(e)}")

    try:
        for course in courses_raw_list:
            clazzId = course.find('input', class_='clazzId')['value']
            courseId = course.find('input', class_='courseId')['value']

            # 获取课程的URL链接，然后从该链接中提取cpi参数
            course_url = course.find('a', class_='color1')['href']
            cpi = course_url.split('&cpi=')[1].split('&')[0]

            course_name = course.find('span', class_='course-name').text
            teacher_name = course.find('p', class_='line2 color3').text

            # 将提取的信息实例化为一个 Course 对象，然后添加到列表中
            course_info = Course(
                class_id=clazzId,
                course_id=courseId,
                cpi=cpi,
                name=course_name,
                teacher_name=teacher_name
            )

            courses.append(course_info)
        return courses

    except Exception as e:
        raise GetCoursesError(f"无法格式化已解析的课程网页: {e}")


async def xxt_get_course_activities(course: Course, user: User) -> list[SignInActivity]:
    cookies = await validate_cookies(user.cookies, phone_number=user.phone_number, password=user.password)
    try:
        course_redirect_page = get_course_redirect_page(cookies, course)
        param_dict = get_param_dict_from_course_redirect_page(course_redirect_page)
    except Exception as e:
        raise Exception(f"无法取得获取活动列表的必要的参数: {e}")
    try:
        course_activities_list_raw_json = requests.get(
            url="https://mobilelearn.chaoxing.com/v2/apis/active/student/activelist",
            params={
                "fid": int(param_dict["cfid"]),
                "courseId": int(course.course_id),
                "classId": int(course.class_id),
                "showNotStartedActive": 0,
                "_": str(int(time.time() * 1000))
            },
            cookies=cookies,
            headers=c.xxt_api.request_user_agent
        )
        if not course_activities_list_raw_json.ok:
            raise Exception(f"无法取得活动列表: HTTP 请求失败")
    except Exception as e:
        raise Exception(f"无法取得活动列表: {e}")

    try:
        data = json.loads(course_activities_list_raw_json.text)
        # 提取 activeList
        active_list = data.get('data', {}).get('activeList', [])

        # 提取状态为 1 的活动信息
        course_activities_raw = [activity for activity in active_list if activity.get('status') == 1]

    except Exception as e:
        raise Exception(f"无法格式化取得的活动列表: {e}")
    try:
        course_activities = []

        for activity_dict in course_activities_raw:
            course_activities.append(await package_activity_info(activity_dict, cookies))
    except Exception as e:
        raise Exception(f"无法格式化取得的活动列表: {e}")
    return course_activities


async def get_activity_info(activity: SignInActivity, cookies: RequestsCookieJar):

    return requests.get(
        url="https://mobilelearn.chaoxing.com/v2/apis/active/getPPTActiveInfo",
        params={
            "activeId": activity.active_id
        },
        headers=c.xxt_api.request_user_agent_android_app,
        cookies=cookies
    )


async def package_activity_info(activity_dict: dict, cookies: RequestsCookieJar) -> SignInActivity:
    def get_sign_type(other_id):
        types = {
            '0': '普通签到',
            # 照片签到已被合并到普通签到
            '2': '二维码签到',
            '3': '手势签到',
            '4': '位置签到',
            '5': '签到码签到',
        }
        return types.get(str(other_id), '未知签到类型')
    activity = SignInActivity(
        name=activity_dict["nameOne"],
        type_name=get_sign_type(activity_dict["otherId"]),
        start_time=datetime.datetime.fromtimestamp(activity_dict["startTime"] / 1000.0),
        end_time=datetime.datetime.fromtimestamp(activity_dict["endTime"] / 1000.0) if
        activity_dict["endTime"] else None,
        status=int(activity_dict["status"]),
        user_status=int(activity_dict["userStatus"]),
        other_id=int(activity_dict["otherId"]),
        group_id=int(activity_dict["groupId"]),
        source=int(activity_dict["source"]),
        is_look=int(activity_dict["isLook"]),
        type=int(activity_dict["type"]),
        release_num=int(activity_dict["releaseNum"]),
        attend_num=int(activity_dict["attendNum"]),
        active_type=int(activity_dict["activeType"]),
        active_id=str(activity_dict["id"]),  # activeId
    )
    # Check activity
    info = await get_activity_info(activity, cookies)
    info_dict = json.loads(info.text)["data"]
    activity.location_range = int(info_dict["locationRange"])

    if info_dict["ifphoto"] == 1:
        activity.require_photo = True
        activity.type_name += "[需照片]"
    if info_dict["ifopenAddress"] == 1:
        activity.require_location = True
        activity.type_name += "[需位置]"

    return activity


async def xxt_get_cookies_by_phone_password_login(phone: str, password: str) -> RequestsCookieJar:
    def encrypt_by_aes(message: str, key: str) -> str:
        key_bytes = key.encode('utf-8')[:16]  # Ensure key is 16 bytes long for AES-128
        iv = key_bytes  # Using same key as iv as per your JavaScript function
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
        encrypted_bytes = cipher.encrypt(pad(message.encode('utf-8'), AES.block_size))
        return b64encode(encrypted_bytes).decode('utf-8')

    def encrypt_by_des(message: str, key: str) -> str:
        key_bytes = key.encode('utf-8')[:8]  # DES key should be 8 bytes long
        cipher = DES.new(key_bytes, DES.MODE_ECB)
        encrypted_bytes = cipher.encrypt(pad(message.encode('utf-8'), DES.block_size))
        return encrypted_bytes.hex()

    if c.xxt_api.xxt_login_encrypt_scheme == "aes":
        phone_encrypt = encrypt_by_aes(phone, c.xxt_api.xxt_login_encrypt_key)
        password_encrypt = encrypt_by_aes(password, c.xxt_api.xxt_login_encrypt_key)
    elif c.xxt_api.xxt_login_encrypt_scheme == "des":
        phone_encrypt = encrypt_by_des(phone, c.xxt_api.xxt_login_encrypt_key)
        password_encrypt = encrypt_by_des(password, c.xxt_api.xxt_login_encrypt_key)
    elif c.xxt_api.xxt_login_encrypt_scheme == "base64":
        phone_encrypt = base64.b64encode(phone.encode()).decode('utf-8')
        password_encrypt = base64.b64encode(password.encode()).decode('utf-8')
    # 更多算法...
    else:
        raise ConfigError("学习通登录加密算法填写有误")

    try:
        await asyncio.sleep(c.system.web_requests_lantency)
        login_res = requests.post(url="https://passport2.chaoxing.com/fanyalogin", headers=c.xxt_api.request_user_agent,
                                  data={"fid": -1,
                                        "uname": phone_encrypt,
                                        "password": password_encrypt,
                                        "refer": "https%3A%2F%2Fi.chaoxing.com",
                                        "t": "true",
                                        "forbidotherlogin": 0,
                                        "validate": '',
                                        "doubleFactorLogin": 0,
                                        "independentId": 0
                                        },
                                  )
        resp_data = login_res.json()
    except Exception as e:
        raise e

    if 'status' in resp_data and resp_data['status']:
        try:
            profile = get_profile(cookies=login_res.cookies)
            merged_cookies = login_res.cookies
            merged_cookies.update(profile.cookies)
            mooc_cookies = get_mooc_cookies(merged_cookies, profile.text)
            merged_cookies.update(mooc_cookies)
        except Exception as e:
            raise Exception(f"取得中间 cookies 时失败: {e}")
        return merged_cookies
    elif 'status' in resp_data and 'msg2' in resp_data and not resp_data['status']:
        raise IncorrectPasswordError(f"学习通返回消息：{resp_data['msg2']}")
    else:
        raise LoginError("登录方法有变，需要检查或更新软件")


def get_mooc_cookies(cookies: RequestsCookieJar, profile_text: str) -> RequestsCookieJar:
    mooc = requests.get(url="https://mooc2-ans.chaoxing.com/visit/interaction", cookies=cookies,
                        headers=c.xxt_api.request_user_agent,
                        data={
                            "s": extract_s_param_from_profile_text(profile_text)
                        })
    return mooc.cookies


def extract_s_param_from_profile_text(profile_text: str) -> str:
    # 创建BeautifulSoup对象并指定解析器
    soup = BeautifulSoup(profile_text, 'lxml')

    # 查找包含URL的a标签
    a_tag = soup.find('a', attrs={'dataurl': re.compile(r'http://hunauxs\.portal\.chaoxing\.com/\?s=.*')})

    # 如果找到了a标签，从中提取s参数的值
    if a_tag:
        dataurl = a_tag.get('dataurl')
        match = re.search(r's=([0-9a-f]+)', dataurl)
        if match:
            return match.group(1)
        else:
            raise ValueError("无法从个人主页取得 s 字段")


class GetProfileError(Exception):
    """Raised when error getting profile."""

    def __init__(self, message="Error occurred during getting profile."):
        self.message = message
        super().__init__(self.message)


def get_profile(cookies: RequestsCookieJar) -> requests.Response:
    try:
        profile = requests.get(f"https://i.chaoxing.com/base?t={str(int(time.time() * 1000))}", cookies=cookies,
                               headers=c.xxt_api.request_user_agent)
    except Exception as e:
        raise GetProfileError("取得个人空间失败")
    return profile


def get_profile_cookies(cookies: RequestsCookieJar) -> RequestsCookieJar:
    return get_profile(cookies).cookies


def get_profile_text(cookies: RequestsCookieJar) -> str:
    return get_profile(cookies).text


def get_course_redirect_page(cookies: RequestsCookieJar, course: Course) -> str:
    course_page_res = requests.get(
        f"https://mooc1.chaoxing.com/visit/stucoursemiddle?courseid={course.course_id}&clazzid={course.class_id}&cpi={course.cpi}&ismooc2=1",
        cookies=cookies, headers=c.xxt_api.request_user_agent)
    return course_page_res.text


def get_param_dict_from_course_redirect_page(page: str) -> dict:
    soup = BeautifulSoup(page, 'html.parser')

    # 为了提高效率，我们直接查找具有特定id的input标签
    ids_to_extract = [
        'enc', 'cfid', 'bbsid', 'fid', 'openc', 'oldenc', 'workEnc', 'examEnc'
    ]

    extracted_data = {}
    for id_value in ids_to_extract:
        input_tag = soup.find('input', {'id': id_value})
        if input_tag:
            extracted_data[id_value] = input_tag['value']

    return extracted_data


def get_user_name(profile: str) -> str:
    try:
        soup = BeautifulSoup(profile, 'html.parser')
        user_name_tag = soup.find('p', class_='user-name')
        if user_name_tag:
            return user_name_tag.text
    except Exception as e:
        raise ValueError("无法从个人空间网页取得学生姓名")


def cookie_jar_to_json_str(cookies: RequestsCookieJar) -> str:
    cookie_dict = requests.utils.dict_from_cookiejar(cookies)
    cookie_json = json.dumps(cookie_dict)
    return cookie_json


def json_str_to_cookie_jar(cookie_json: str) -> RequestsCookieJar:
    cookie_dict = json.loads(cookie_json)
    cookie_jar = requests.utils.cookiejar_from_dict(cookie_dict)
    return cookie_jar


async def is_cookies_valid(cookies: RequestsCookieJar) -> bool:
    if cookies is None:
        return False
    try:
        name = get_user_name(get_profile_text(cookies))
        l.debug(f"以本地 cookies 取得用户姓名 {name}")
    except ValueError as ve:
        return False
    return True


async def validate_cookies(cookies_raw: str | RequestsCookieJar | None, phone_number: str,
                           password: str) -> RequestsCookieJar:
    cookies = None

    if isinstance(cookies_raw, RequestsCookieJar):
        cookies = cookies_raw if await is_cookies_valid(cookies_raw) else None
    elif isinstance(cookies_raw, str) and cookies_raw:
        cookies_converted = json_str_to_cookie_jar(cookies_raw)
        cookies = cookies_converted if await is_cookies_valid(cookies_converted) else None
    elif cookies_raw is None:
        # 如果 cookies_raw 为空，尝试根据 phone_number 获取 user，然后获取 user.cookies
        user = db.crud.get_user(phone_number=phone_number)
        if user and user.cookies:
            cookies_converted = json_str_to_cookie_jar(user.cookies)
            cookies = cookies_converted if await is_cookies_valid(cookies_converted) else None

    if cookies is None:
        l.debug("本地没有 cookies 或已失效，重新获取 cookies")
        cookies = await xxt_get_cookies_by_phone_password_login(phone_number, password)
        user = db.crud.get_user(phone_number=phone_number)
        if user:
            try:
                user.cookies = cookie_jar_to_json_str(cookies)
                db.crud.update_user(user)
            except Exception as e:
                l.debug("更新本地已有用户的 cookies 失败")
                raise e
            l.debug("已更新本地已有用户的 cookies")
    else:
        l.debug("本地 cookies 有效，用之")

    return cookies


async def xxt_sign_in(activity: SignInActivity, user: User) -> bool:
    result = requests.get(
        url=f"https://mobilelearn.chaoxing.com/v2/apis/sign/signIn?activeId={activity.active_id}",
        cookies=await validate_cookies(phone_number=user.phone_number, password=user.password, cookies_raw=user.cookies),
        headers=c.xxt_api.request_user_agent_android_app
    )

    if not result.ok:
        raise Exception("网络错误")

    res_dict = json.loads(result.text)
    if res_dict["result"] == 1 and res_dict["msg"] == "success":
        return True
    else:
        return False


async def xxt_get_user_and_courses_info(phone: str, password: str, qq_num: str, is_admin: bool,
                                        cookies_raw: RequestsCookieJar = None) -> dict:
    info = {}
    cookies = await validate_cookies(cookies_raw, phone_number=phone, password=password)
    courses_raw = await xxt_get_courses_raw(cookies)

    info["user"] = User(
        xxt_user_id=str(cookies.get("UID")),
        qq_num=qq_num,
        name=get_user_name(get_profile_text(cookies)),
        cookies=cookie_jar_to_json_str(cookies),
        phone_number=phone,
        password=password,
        is_admin=is_admin
    )

    info["courses"] = xxt_parse_raw_courses_to_courses_list(courses_raw)

    return info
