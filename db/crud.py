from __future__ import annotations

from typing import List

from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import func, exc

from db.db_models import *
from db.db import db_session as s, engine


def delete_all_data() -> bool:
    """
    删库跑路
    删除所有表及其结构，再根据结构重建所有表
    失败引发异常

    :return:  True 如果成功。
    """
    try:
        s.commit()

        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    except Exception as e:
        s.rollback()
        raise e
    return True


def update_user(user: User, courses: List[Course] = None) -> bool:
    """
    更新用户信息和关联课程。

    :param user: 用户对象。
    :param courses: 要关联的课程对象列表。
    """
    try:
        # 如果传入了课程列表，则更新用户关联的课程
        if courses:
            updated_courses = []
            for course in courses:
                existing_course = s.query(Course).filter_by(class_id=course.class_id).first()
                if existing_course:
                    # 更新现有课程的信息
                    existing_course.name = course.name
                    existing_course.course_id = course.course_id
                    existing_course.cpi = course.cpi
                    existing_course.teacher_name = course.teacher_name
                    updated_courses.append(existing_course)
                else:
                    # 如果课程不存在，将其添加到会话
                    s.add(course)
                    updated_courses.append(course)
            # 更新用户关联的课程
            user.courses = updated_courses
        # 提交更改到数据库
        s.commit()
        return True

    except Exception as e:
        s.rollback()  # 如果出现异常，回滚事务
        raise e


def create_user(user: User, courses: List[Course]) -> bool:
    """
    创建新用户并保存到数据库。

    :param courses: 课程类的列表。
    :param user: 用户类。
    :return: 创建成功情况。
    """
    # 如果该用户已经存在，直接返回False
    if get_user(qq_num=user.qq_num):
        return False

    # 否则，尝试创建新的用户
    try:
        s.commit()
        # 对于每个课程，检查是否已经存在，如果存在则更新本地课程信息，否则创建新的
        for i, course in enumerate(courses):
            existing_course = s.query(Course).filter_by(class_id=course.class_id).first()
            if existing_course:
                # 更新现有课程的信息
                existing_course.name = course.name
                existing_course.course_id = course.course_id
                existing_course.cpi = course.cpi
                existing_course.teacher_name = course.teacher_name
                courses[i] = existing_course
            else:
                # 如果课程不存在，将其添加到会话
                s.add(course)

        # 添加用户和关联的课程到会话
        user.courses.extend(courses)
        s.add(user)
        s.commit()
        return True
    except Exception as e:  # 如果出现其他任何异常
        s.rollback()  # 回滚事务
        raise e


def create_course(course: Course) -> bool:
    """
    创建新课程并保存到数据库。

    :param course: 课程类。
    :return: 创建成功情况。
    """
    # 首先，检查是否已经存在具有给定class_id的课程
    existing_course = s.query(Course).filter_by(class_id=course.class_id).first()

    # 如果该课程已经存在，直接返回False
    if existing_course:
        return False

    # 否则，尝试创建新的课程
    try:
        s.commit()

        s.add(course)
        s.commit()
        return True
    except Exception as e:  # 如果出现其他任何异常
        s.rollback()  # 同样回滚事务
        raise e  # 再次抛出该异常，这样你可以在上级函数中捕获它并处理


def get_course(course_id: int = None, user: User = None) -> Course | None:
    """
    通过各种参数获取一个Course对象。
    若指定了用户，则只从已与用户关联的课程中寻找，忽略没有关联的课程。

    :param user: 用户对象。
    :param course_id: 要查找的课程的ID。
    :return: 如果找到，返回相应的Course对象，否则None。
    """
    # 如果同时指定了user和course_id，确保课程是用户所关联的
    if user and course_id:
        association = s.query(student_course_association).filter_by(user_id=user.id, course_id=course_id).one_or_none()
        if association:
            return s.query(Course).filter(Course.id == course_id).one_or_none()
        else:
            return None

    # 如果只有course_id指定
    elif course_id:
        return s.query(Course).filter(Course.id == course_id).one_or_none()

    return None


def get_courses_list(qq_num: str = None, ) -> List[Course]:
    """
        获取数据库内某用户的所有课程。

        :param qq_num: qq号。
        :return: Course 对象列表。
        """
    user = get_user(qq_num=qq_num)
    if user:
        return user.courses
    return []


def get_user(qq_num: str = None, phone_number: str = None, user_id: int = None) -> User | None:
    """
    在数据库里查询用户。

    :param user_id: 用户在数据库内部的 id
    :param qq_num: 用户的 QQ 号
    :param phone_number: 用户的手机号
    :return: User 对象或 None。
    """

    if qq_num:
        return s.query(User).filter(User.qq_num == qq_num).first()
    if phone_number:
        return s.query(User).filter(User.phone_number == phone_number).first()
    if user_id:
        return s.query(User).filter(User.id == user_id).first()

    return None


def get_activity(active_id: str = None, id: int = None) -> SignInActivity | None:
    if active_id:
        activity = s.query(SignInActivity).filter(SignInActivity.active_id == active_id).first()
    elif id:
        activity = s.query(SignInActivity).filter(SignInActivity.id == id).first()
    else:
        activity = None

    return activity


def update_activity(activity: SignInActivity, course: Course, user: User) -> bool:
    try:
        # 查找数据库中是否有相应的activity
        existing_activity = get_activity(active_id=activity.active_id)

        if existing_activity is None:
            # 如果没有找到相应的activity, 引发异常
            raise ValueError(f"No activity found with active_id: {activity.active_id}")

        # 检查activity的user是否存在传入的user
        if user not in existing_activity.users:
            # 如果不存在，就添加用户进关联关系
            existing_activity.users.append(user)

        # 检查activity的course是否正确
        if existing_activity.course[0] != course:
            existing_activity.course = [course]

        # 提交更新
        s.commit()
        return True
    except Exception as e:
        s.rollback()
        raise ValueError(f"Failed to update activity in the database: {e}")


def create_sign_in_activity(activity: SignInActivity, course: Course, user: User) -> bool:
    try:
        # add the sign in activity to the session

        activity.course = [course]
        activity.user = [user]

        s.add(activity)
        # commit the transaction
        s.commit()
        return True
    except Exception as e:
        s.rollback()
        raise Exception(f"添加签到活动到数据库时失败: {e}")
