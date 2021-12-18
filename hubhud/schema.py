from dataclasses import field

import sqlalchemy as rdb
from sqlalchemy.orm import registry


mapper_registry = registry()


class SQLiteArray(rdb.types.TypeDecorator):

    impl = rdb.String
    cache_ok = True

    def __init__(self, coltype):
        self.coltype = coltype
        super().__init__()

    def process_bind_param(self, value, dialect):
        return ",".join(value)

    def process_result_value(self, value, dialect):
        return value.split(",")


def Array(ctype):
    return rdb.ARRAY(ctype).with_variant(SQLiteArray(ctype), "sqlite")


def F(ctype, default=()):

    if isinstance(ctype, rdb.Column):
        md = {"sa": ctype}
    else:
        md = {"sa": rdb.Column(ctype)}
    params = {"metadata": md}
    if default != ():
        params["default"] = default
    return field(**params)


def get_db(db_uri):
    engine = rdb.create_engine(db_uri)
    mapper_registry.metadata.bind = engine
    mapper_registry.metadata.create_all(engine)
    return engine
