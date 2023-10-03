from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.db_models import Base
from config import c
from loguru import logger as l

l.info("连接到数据库")

try:
    engine = create_engine(c.db.sqlalchemy_db_url)
except AttributeError as e:
    l.error(f"数据库链接填写有误，请参考文档。填写了：{e}")
    exit(1)
except Exception as e:
    l.error(f"未知错误： {e}")
    exit(1)

try:
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    db_session = Session()
except Exception as e:
    l.error(f"创建数据库时发生未知错误： {e}")
    exit(1)

l.success("连接到数据库成功")
