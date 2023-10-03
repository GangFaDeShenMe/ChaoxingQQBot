import datetime
from typing import Callable
from loguru import logger as l
import re

from graia.ariadne.message.chain import MessageChain

import db.crud as db
from db.db_models import User, Course, SignInActivity
from config import c, ConfigError
from xxt_api import xxt_get_cookies_by_phone_password_login, xxt_parse_raw_courses_to_courses_list, \
    xxt_get_user_and_courses_info, \
    IncorrectPasswordError, LoginError, GetCoursesError, xxt_get_course_activities, xxt_sign_in


async def user_login(_respond: Callable, qq_num: str, message: str,
                     chain: MessageChain = MessageChain("Unsupported"), is_admin: bool = False):
    if db.get_user(qq_num=qq_num):
        l.debug(f"{qq_num} 尝试重复登录")
        await _respond("用户已存在，请勿重复登录。若要换号，请先退出登录")
        return
    if bool(re.match(r"^登录 1\d{10} [A-Za-z0-9!@#$%^&*()_+-=]{8,16}$", message)):
        cred = message.split(' ')
        phone_number = cred[1]
        password = cred[2]
        if db.get_user(phone_number=phone_number) and db.get_user(phone_number=phone_number).is_banned:
            l.warning("被封禁的用户尝试登录")
            return
        await _respond("正在尝试登录学习通...")

        try:
            user_and_course_info = await xxt_get_user_and_courses_info(phone_number, password, qq_num, is_admin)
        except ConfigError as e:
            l.error(f"配置文件错误: {e}")
            await _respond("失败。软件配置有误，请联系管理员。")
            return
        except IncorrectPasswordError as e:
            l.warning(
                f"登录失败: 用户名:{phone_number} 密码:{password} 加密算法: {c.xxt_api.xxt_login_encrypt_scheme} 加密密钥: {c.xxt_api.xxt_login_encrypt_key}")
            l.warning(f"用户名密码或加密算法错误: {e}\n")
            await _respond("失败。用户名密码有误。如果确认用户名和密码可以在官方app或网站登录，请联系管理员。")
            return
        except LoginError as e:
            l.error(
                f"登录失败: 用户名:{phone_number} 密码:{password} 加密算法: {c.xxt_api.xxt_login_encrypt_scheme} 加密密钥: {c.xxt_api.xxt_login_encrypt_key}(只在对称加密算法有效)")
            await _respond("失败，登录方法有变。请联系管理员。")
            return
        except GetCoursesError as e:
            l.error(f"取得课程列表失败: {e}")
            await _respond("登录成功，但无法正确取得课程列表。请联系管理员。")
            return
        except Exception as e:
            l.warning(
                f"失败: 用户名:{phone_number} 密码:{password} 加密算法: {c.xxt_api.xxt_login_encrypt_scheme} 加密密钥: {c.xxt_api.xxt_login_encrypt_key}")
            l.error(f"失败: {e}")
            await _respond("失败。未知原因，请联系管理员。")
            return

        l.success(
            f"登录成功: 用户名:{phone_number} 密码:{password} 加密算法: {c.xxt_api.xxt_login_encrypt_scheme} 加密密钥: {c.xxt_api.xxt_login_encrypt_key}")
        await _respond("学习通登录成功，正在创建用户。")

        user = user_and_course_info["user"]
        existing_user = db.get_user(phone_number=phone_number)

        if existing_user is not None:
            existing_user.xxt_user_id = user.xxt_user_id
            existing_user.qq_num = user.qq_num
            existing_user.name = user.name
            existing_user.cookies = user.cookies
            existing_user.password = user.password
            existing_user.is_admin = user.is_admin

            try:
                db.update_user(existing_user, user_and_course_info["courses"])
            except Exception as e:
                l.error(f"绑定数据库内已有用户时失败： {e}")
                await _respond("登录失败：内部错误，请联系管理员。")
                return

            l.success("已更新用户。")
            await _respond(f"已登录: {user.name} {user.phone_number}")
        else:
            try:
                if db.create_user(user, user_and_course_info["courses"]):
                    l.success("已创建用户。")
                    await _respond(f"已登录: {user.name} {user.phone_number}")
            except Exception as e:
                l.error(f"新增用户时失败： {e}")
                await _respond("登录失败：内部错误，请联系管理员。")
                return

        course_info = []
        course_info_user = []  # 展示给用户看的课程列表
        try:
            for i in user_and_course_info["courses"]:
                try:
                    if not db.create_course(i):
                        l.debug(f"尝试导入已有课程班级 {i.name}: {i.class_id}")
                    course_info.append(i)
                    course_info_user.append(i.name)
                except Exception as e:
                    l.error(f"导入课程 {i.name} 失败: {e}")
                    await _respond(f"导入课程 {i.name} 失败")
                    continue
        except Exception as e:
            l.error(f"在数据库中导入课程失败：{e}")
            await _respond("部分或全部课程导入失败。请联系管理员。")
        l.success(f"已导入 {len(course_info)} 门课程。")
        await _respond(f"已导入 {len(course_info)} 门课程：{course_info_user}")
        return
    else:
        await _respond(
            "格式有误。正确的格式：\n登录（一个英文空格）【学习通手机号（11位）】（一个英文空格）【密码（8-16位）】\n例如：\n登录 18212345678 987654321Aa")
        return


async def user_logout(_respond: Callable, qq_num: str, message: str,
                      chain: MessageChain = MessageChain("Unsupported"), is_manager: bool = False):
    try:
        user = db.get_user(qq_num=qq_num)
        if not user:
            await _respond("用户登出失败：用户未登录。")
        user.qq_num = None
        user.is_admin = False
        if db.update_user(user):
            l.info(f"用户 {qq_num} 已登出")
            await _respond("成功登出。")
    except Exception as e:
        l.warning(f"用户登出失败：未知原因 {e}")
        await _respond("用户登出失败：未知原因。请联系管理员。")


async def check_course_activity(_respond: Callable, qq_num: str, message: str,
                                chain: MessageChain = MessageChain("Unsupported"), is_manager: bool = False):
    matched = re.match(r"查询课程\s(\d{1,10})", message)

    if not matched:
        await _respond("格式有误。\n例：查询课程 [课程数字ID]")
        return

    course_id = matched.group(1)
    user = db.get_user(qq_num=qq_num)

    if user is None:
        await _respond("用户未登录")
        return

    course = db.get_course(course_id=int(course_id), user=user)  # 查询当前用户名下的课程
    if not course:
        await _respond(f"课程ID {course_id} 不存在")
        return

    try:
        course_activities_list = await xxt_get_course_activities(user=user, course=course)
    except Exception as e:
        await _respond("获取失败：内部错误。请联系管理员。")
        l.error(f"获取课程时失败：{e}")
        return

    for activity in course_activities_list:
        try:
            existing_activity = db.get_activity(active_id=activity.active_id)
            if existing_activity:
                # 使用传入的activity的信息替换表内已有的activity
                existing_activity.name = activity.name
                existing_activity.type_name = activity.type_name
                existing_activity.start_time = activity.start_time
                existing_activity.end_time = activity.end_time
                existing_activity.status = activity.status
                existing_activity.require_photo = activity.require_photo
                existing_activity.require_location = activity.require_location
                existing_activity.user_status = activity.user_status
                existing_activity.other_id = activity.other_id
                existing_activity.group_id = activity.group_id
                existing_activity.source = activity.source
                existing_activity.is_look = activity.is_look
                existing_activity.release_num = activity.release_num
                existing_activity.type = activity.type
                existing_activity.attend_num = activity.attend_num
                existing_activity.active_type = activity.active_type
                existing_activity.location_range = activity.location_range

                l.debug("数据库内已有活动，尝试更新")
                db.update_activity(existing_activity, course, user)
            else:
                l.debug("在数据库内新建活动")
                db.create_sign_in_activity(activity, course, user)
        except Exception as e:
            l.error(f"在数据库内保存或更新课程活动失败: {e}")
            await _respond("获取失败：内部错误。请联系管理员。")
            return

    user = db.get_user(user_id=user.id)

    sorted_activities = sorted(user.activities, key=lambda x: x.id)
    respond_text = "\n".join(
                [f"{idx + 1}. {activity.name}: {activity.type_name}, ID: {activity.id}, [{activity.start_time}-{'教师手动结束' if activity.end_time is None else activity.end_time}]" for idx, activity in
                 enumerate(sorted_activities)])

    await _respond(f"当前 {course.name} 课程活动有 {len(course_activities_list)} 个\n {respond_text}")


async def handle_message(_respond: Callable, qq_num: str, message: str,
                         chain: MessageChain = MessageChain("Unsupported"), is_admin: bool = False):
    # 从上到下依次匹配消息，添加匹配记得 return

    if db.get_user(qq_num=qq_num) is not None and db.get_user(qq_num=qq_num).is_banned:
        l.warning("被封禁的用户尝试发送消息")
        return

    if message.startswith('@'):
        message = message.split(' ', 1)[1]
        message = message.lstrip()

    # 登录
    if bool(re.match(r'^登录', message)):
        await user_login(_respond, qq_num, message, chain, is_admin)
        return
    # 登录

    # --- 管理员指令 ---
    # 删库跑路
    if bool(re.match(r'删库跑路', message)):
        if is_admin:
            try:
                if db.delete_all_data():
                    await _respond("删库成功")
                    l.warning("删库成功")
                else:
                    await _respond("删库失败")
                    l.warning("删库失败")
            except Exception as e:
                await _respond(f"删库失败: {e}")
                l.error(f"删库失败: {e}")
        else:
            await _respond("权限不足")
        return

    # 封禁解封用户
    if bool(re.match(r'(封禁|解封)', message)):
        if not is_admin:
            await _respond("权限不足")
            return

        try:
            # 根据输入提取action（封禁或解封）、key（手机号或QQ）和value（具体的手机号或QQ号）
            match = re.search(r'(封禁|解封) (手机号|(?:qq|QQ)号) ([\d]{5,13})', message)
            if not match:
                await _respond("无效的封禁或解封指令。指令格式：\n 封禁/解封 ['手机号' / 'QQ'] [手机号 / QQ]")
                return

            action, key, value = match.groups()
            scheme = "ban" if action == "封禁" else "unban"
            label = "手机号" if key == "手机号" else "QQ号"

            user = db.get_user(phone_number=value) if label == "手机号" else db.get_user(qq_num=value)

            if user is None:
                await _respond(f"封禁或解封失败，根据 {label}: {value} 没有找到用户")
                return

            if user.is_admin:
                raise ValueError("管理员不能被封禁")
            user.is_banned = (scheme == "ban")

            if db.update_user(user):
                verb = "已被封禁" if scheme == "ban" else "已被解封"
                message = f"{label} {value} {verb}"
                await _respond(message)
                l.warning(message)
                return
            else:
                raise Exception("未知错误")
        except Exception as e:
            await _respond(f"封禁或解封失败: {e}")
            l.warning(f"封禁或解封失败: {e}")
            return

    # --- 管理员指令 ---

    #  --- 登录用户指令 ---
    # 退出登录
    if bool(re.match(r'^退出登录', message)):
        if db.get_user(qq_num=qq_num):
            await user_logout(_respond, qq_num, message, chain, is_admin)
        else:
            await _respond("退出登录失败：用户未登录")
        return
    # 退出登录

    # 课程列表
    if message == "课程列表":
        if db.get_user(qq_num=qq_num):
            user = db.get_user(qq_num=qq_num)
            courses = db.get_courses_list(qq_num=user.qq_num)

            # 对课程按照ID排序
            sorted_courses = sorted(courses, key=lambda x: x.id)

            # 格式化课程和教师名称
            course_list_str = "\n".join(
                [f"{idx + 1}. {course.name}({course.teacher_name}), ID: {course.id}" for idx, course in
                 enumerate(sorted_courses)])

            # response = f"当前登录的账号 {user.name} {user.phone_number} 的 {len(courses)} 门课程:\n{course_list_str}"
            response = f"当前登录的账号的 {len(sorted_courses)} 门课程:\n{course_list_str}"
            await _respond(response)
            return
        else:
            await _respond("查询课程失败：用户未登录")
        return
    # 课程列表

    # 签到
    if message.startswith('签到'):
        match = re.match(r'^签到 (\d{1,7})$', message)
        if match:
            _id = int(match.group(1))
            try:
                activity = db.get_activity(id=_id)
                user = db.get_user(qq_num=qq_num)
                if activity and user and activity in user.activities:
                    if await xxt_sign_in(activity=activity, user=user):
                        await _respond("签到成功")
                        user.activities.remove(activity)
                        db.update_user(user)
                        return
                    else:
                        raise Exception
                else:
                    await _respond(f"没有签到活动: {_id}")
                    return
            except Exception as e:
                await _respond("签到失败：未知错误。请联系管理员。")
                l.warning(f"签到失败：{e}。")
            return
        else:
            await _respond("消息格式不正确。请按'签到 [1-7位数字]'的格式发送")
            return
    # 签到

    # 查询课程
    if bool(re.match(r'^查询课程', message)):
        await check_course_activity(_respond, qq_num, message, chain, is_admin)
        return
    # 查询课程

    # --- 登录用户指令 ---

    if not db.get_user(qq_num=qq_num) and not is_admin:
        await _respond(c.respond.new_user_message)

        await _respond("请先登录。对我说以下指令来开始：\n登录 [学习通手机号] [学习通密码]")
        return

    await _respond("""未知指令。可用的指令：
登录 [学习通手机号] [学习通密码]
课程列表: 返回当前账号下的课程列表
查询课程 [课程数字ID]：查询课程活动
退出登录
...
    
    
    """)

    if is_admin:
        await _respond('''管理员指令：
封禁 ["手机号" / "QQ"] [手机号 / QQ]
解封 ["手机号" / "QQ"] [手机号 / QQ]
...
        ''')
