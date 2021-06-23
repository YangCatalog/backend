# Copyright The IETF Trust 2019, All Rights Reserved
# Copyright 2018 Cisco and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = "Richard Zilincik"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "richard.zilincik@pantheon.tech"

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
