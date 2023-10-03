from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Sequence, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# 中间表 - 用于学生和课程之间的多对多关系
student_course_association = Table(
    'student_course', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('course_id', Integer, ForeignKey('courses.id'))
)

activity_course_association = Table(
    'activity_course', Base.metadata,
    Column('activity_id', Integer, ForeignKey('sign_in_activities.id')),
    Column('course_id', Integer, ForeignKey('courses.id'))
)

user_activity_association = Table(
    'user_activity', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('activity_id', Integer, ForeignKey('sign_in_activities.id'))
)


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, Sequence('user_id_seq'), primary_key=True)
    xxt_user_id = Column(String(20), nullable=False, unique=True, comment="XXT User ID")
    qq_num = Column(String(15), nullable=True, unique=True, index=True, comment="QQ Number")  # 相当于用户使用本机器人的 token，谨慎修改
    name = Column(String(50), nullable=True, comment="学生姓名")
    cookies = Column(String(500), nullable=True, comment="学习通网页cookies")
    phone_number = Column(String(15), nullable=False,index=True, comment="手机号")
    password = Column(String(256), nullable=False, comment="由于学习通喜欢换加密算法，只能存储明文密码，请注意。")
    is_admin = Column(Boolean, nullable=False, default=False, comment="是否管理员")
    is_banned = Column(Boolean, default=False, nullable=False, comment="是否被封禁")
    usage_count = Column(Integer, default=0, nullable=False ,comment="使用次数")

    courses = relationship("Course", secondary=student_course_association, back_populates="students")
    activities = relationship("SignInActivity", secondary=user_activity_association, back_populates="users")


class Course(Base):
    __tablename__ = 'courses'

    id = Column(Integer, Sequence('course_id_seq'), primary_key=True)
    name = Column(String(30), nullable=False, index=True, comment="课名")
    course_id = Column(String(30), nullable=False, comment="courseId")
    cpi = Column(String(30), nullable=False, comment="cpi")
    class_id = Column(String(30), nullable=False, index=True, unique=True, comment="clazzId")
    teacher_name = Column(String(50), nullable=True, comment="教师名")
    check_in_count = Column(Integer, default=0, nullable=False, comment="总签到次数")

    students = relationship("User", secondary=student_course_association, back_populates="courses")
    activities = relationship("SignInActivity", secondary=activity_course_association, back_populates="course")


class SignInActivity(Base):
    __tablename__ = 'sign_in_activities'

    # 一般
    id = Column(Integer, Sequence('activity_id_seq'), primary_key=True)
    name = Column(String(100), nullable=False, comment="活动名称/nameOne")
    type_name = Column(String(20), nullable=False, comment="活动类型名称")
    start_time = Column(Integer, nullable=False, comment="开始时间（时间戳）/startTime")
    end_time = Column(Integer, nullable=True, comment="结束时间（时间戳，如为空就是教师手动结束）/endTime")
    status = Column(Integer, nullable=False, comment="活动状态，0为未签到，1为已签到，...")

    # 签到相关
    require_photo = Column(Boolean, nullable=True, comment="是否需要提交照片（照片签到）, 对应'ifphoto'字段")
    require_location = Column(Boolean, nullable=True, comment="是否需要提交位置信息（位置签到，扫码签到）")
    solve = Column(String(200), nullable=True, comment="签到活动的解决方法（token，位置，手势...）")

    # 原始数据 TODO:把这些字段的意义搞清楚，去掉不必要的字段
    user_status = Column(Integer, nullable=False, comment="userStatus")
    other_id = Column(Integer, nullable=False, comment="otherId")  # 签到类型（普通，手势，位置...）
    group_id = Column(Integer, nullable=False, comment="groupId")
    source = Column(Integer, nullable=False, comment="source")
    is_look = Column(Integer, nullable=False, comment="isLook")
    release_num = Column(Integer, nullable=False, comment="releaseNum")
    type = Column(Integer, nullable=False, comment="type")
    attend_num = Column(Integer, nullable=False, comment="attendNum")
    active_type = Column(Integer, nullable=False, comment="activeType")
    active_id = Column(String(30), index=True, unique=True, nullable=False, comment="id/activeId")
    location_range = Column(Integer, nullable=True, comment="locationRange")

    course = relationship("Course", secondary=activity_course_association, back_populates="activities")
    users = relationship("User", secondary=user_activity_association, back_populates="activities")
