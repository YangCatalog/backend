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

from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import DeferredReflection
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class BaseUser(DeferredReflection, Base):
    __abstract__ = True
    Id = Column(Integer, primary_key=True)
    Username = Column(String(255), nullable=False, unique=False)
    Password = Column(String(255), nullable=False)
    Email = Column(String(255), unique=True)
    ModelsProvider = Column(String(255))
    FirstName = Column(String(255))
    LastName = Column(String(255))
    AccessRightsSdo = Column(String(255))
    AccessRightsVendor = Column(String(255))


class User(BaseUser):
    __tablename__ = 'users'


class TempUser(BaseUser):
    __tablename__ = 'users_temp'
