from sqlalchemy.ext.declarative import DeferredReflection
from api.globalConfig import yc_gc

db = yc_gc.sqlalchemy


class BaseUser(DeferredReflection, db.Model):
    __abstract__ = True
    Id = db.Column(db.Integer, primary_key=True)
    Username = db.Column(db.String(255), nullable=False, unique=False)
    Password = db.Column(db.String(255), nullable=False)
    Email = db.Column(db.String(255), unique=True)
    ModelsProvider = db.Column(db.String(255))
    FirstName = db.Column(db.String(255))
    LastName = db.Column(db.String(255))
    AccessRightsSdo = db.Column(db.String(255))
    AccessRightsVendor = db.Column(db.String(255))


class User(BaseUser):
    __tablename__ = 'users'


class TempUser(BaseUser):
    __tablename__ = 'users_temp'