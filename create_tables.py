import sqlalchemy
from api.models import Base

engine = sqlalchemy.create_engine('mysql://yang:pass@127.0.0.1:3306/yang_catalog')
Base.metadata.create_all(engine)
