import psycopg2
import numpy as np
import pandas
from sqlalchemy import create_engine


DB_HOST = '192.168.50.100'
DB_NAME = 'warno'
DB_USER = 'warno'
DB_PASS = 'warno'


def table_exists(table_name, curr):
    SQL = "SELECT relname FROM pg_class WHERE relname = %s;"
    curr.execute(SQL, (table_name,))
    if curr.fetchone() == None:
        return False
    else:
        return True


def drop_table(table_name, curr):
    SQL = "DROP TABLE IF EXISTS %s;"
    try:
        curr.execute(SQL, (table_name,))
    except Exception, e:
        print(e)


def create_table_from_file(filename, curr):
    f = open(filename)
    try:
        curr.execute(f.read())
    except Exception, e:
        print(e)


def initialize_database(curr, path="schema/"):
    # First element of each is the table name, second is file name.
    # Only necessary because "instrument_logs" table is "logs.data", "logs.schema"
    schema_list = [
                   ["users", "users"],
                   ["sites", "sites"],
                   ["instruments", "instruments"],
                   ["instrument_logs", "log"],
                   ["usage", "usage"],
                   ["prosensing_paf", "prosensing_paf"],
                   ["event_codes", "event_codes"],
                   ["events_with_text", "events_with_text"],
                   ["events_with_value", "events_with_value"],
                   ["pulse_captures", "pulse_captures"],
                   ["table_references", "table_references"],
                   ["instrument_data_references", "instrument_data_references"]
                   ]

    for schema in schema_list:
        if not table_exists(schema[0], curr):
            print("Initializing relation %s", schema[0])
            create_table_from_file("%s/%s.schema" % (path, schema[1]), curr)


def load_data_into_table(filename, table, conn):
    df = pandas.read_csv(filename)
    keys = df.keys()
    engine = create_engine('postgresql://warno:warno@192.168.50.100:5432/warno')
    df.to_sql(table, engine, if_exists='append', index=False, chunksize=900)


def dump_table_to_csv(filename, table, server=None):

    if server is None:
        server = create_engine('postgresql://warno:warno@192.168.50.100:5432/warno')
    else:
        server = create_engine(server)

    df = pandas.read_sql_table(table, server)
    df.to_csv(filename, index=False)


def connect_db():
    return psycopg2.connect("host=%s dbname=%s user=%s password=%s" % (DB_HOST, DB_NAME, DB_USER, DB_PASS))
