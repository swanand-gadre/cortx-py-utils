#!/usr/bin/env python3

"""
 ****************************************************************************
 Filename:          storage.py
 _description:      Interface for Databases

 Creation Date:     6/10/2019
 Author:            Alexander Nogikh
                    Dmitry Didenko

 Do NOT modify or remove this copyright and confidentiality notice!
 Copyright (c) 2001 - $Date: 2015/01/14 $ Seagate Technology, LLC.
 The code contained herein is CONFIDENTIAL to Seagate Technology, LLC.
 Portions are also trade secret. Any use, duplication, derivation, distribution
 or disclosure of this code, for any reason, not expressly authorized is
 prohibited. All other rights are expressly reserved by Seagate Technology, LLC.
 ****************************************************************************
"""

from abc import ABC, abstractmethod
from typing import Type, Union, Any
from eos.utils.data.access import Query
from eos.utils.data.access import ExtQuery
from eos.utils.data.access import IFilter
from eos.utils.data.access import BaseModel


class IDataBase(ABC):
    """Abstract Storage Interface"""

    @abstractmethod
    async def store(self, obj: BaseModel):
        """Store object into Storage

            :param Object obj: Arbitrary model object for storing into DB

        """
        pass

    @abstractmethod
    async def get(self, query: Query):
        """Get object from Storage by Query

            :param Query query: query object which describes request to Storage

        """
        pass

    @abstractmethod
    async def get_by_id(self, obj_id: Any) -> Union[BaseModel, None]:
        """
        Simple implementation of get function.
        Important note: in terms of this API 'id' means BaseModel.primary_key reference. If model
        contains 'id' field please use ordinary get call. For example,

            await db(YourBaseModel).get(Query().filter_by(Compare(YourBaseModel.id, "=", obj_id)))

        This API call is equivalent to

            await db(YourBaseModel).get(Query().filter_by(
                                                    Compare(YourBaseModel.primary_key, "=", obj_id)))

        :param Any obj_id:
        :return: BaseModel if object was found by its id and None otherwise
        """
        pass

    @abstractmethod
    async def update(self, filter_obj: IFilter, to_update: dict) -> int:
        """
        Update object in Storage by filter

        :param IFilter filter_obj: filter object which describes what objects need to update
        :param dict to_update: dictionary with fields and values which should be updated
        :return: number of entries updated
        """
        pass

    @abstractmethod
    async def update_by_id(self, obj_id: Any, to_update: dict) -> bool:
        """
        Update base model in db by id (primary key)

        :param Any obj_id: id-value of the object which should be updated (primary key value)
        :param dict to_update: dictionary with fields and values which should be updated
        :return: `True` if object was updated and `False` otherwise
        """
        pass

    @abstractmethod
    async def delete(self, filter_obj: IFilter) -> int:
        """
        Delete objects in DB by Query

        :param IFilter filter_obj: filter object to perform delete operation
        :return: number of deleted entries
        """
        pass

    @abstractmethod
    async def delete_by_id(self, obj_id: Any) -> bool:
        """
        Delete base model by its id

        :param Any obj_id: id of the object to be deleted
        :return: BaseModel if object was found by its id and None otherwise
        :return: `True` if object was deleted successfully and `False` otherwise
        """
        pass

    @abstractmethod
    async def sum(self, ext_query: ExtQuery):
        """Sum Aggregation function

            :param ExtQuery ext_query: Extended query which describes how to perform sum aggregation

        """
        pass

    @abstractmethod
    async def avg(self, ext_query: ExtQuery):
        """Average Aggregation function

            :param ExtQuery ext_query: Extended query which describes how to perform average
                                       aggregation

        """
        pass

    @abstractmethod
    async def count(self, filter_obj: IFilter = None) -> int:
        """
        Returns count of entities for given filter_obj

        :param filter_obj: filter object to perform count operation
        :return:
        """
        pass

    @abstractmethod
    async def count_by_query(self, ext_query: ExtQuery):
        """
        Count Aggregation function

        :param ExtQuery ext_query: Extended query which describes to perform count aggregation
        :return:
        """
        pass

    @abstractmethod
    async def max(self, ext_query: ExtQuery):
        """Max Aggregation function

            :param ExtQuery ext_query: Extended query which describes how to perform Max aggregation

        """
        pass

    @abstractmethod
    async def min(self, ext_query: ExtQuery):
        """Min Aggregation function

            :param ExtQuery ext_query: Extended query which describes how to perform Min aggregation

        """
        pass


class AbstractDataBaseProvider(ABC):
    """
    A class for data storage access.

    Below you can see its intended usage.
    Suppose db is an instance of AbstractDbProvider.

    await db(SomeModel).get(some_query)
    await db(some_model_instance).get(some_query)  # we can avoid passing model class

    """
    def __call__(self, model: Union[BaseModel, Type[BaseModel]]) -> IDataBase:
        if isinstance(model, BaseModel):
            model = type(model)

        return self.get_storage(model)

    @abstractmethod
    def get_storage(self, model: Type[BaseModel]) -> IDataBase:
        pass
