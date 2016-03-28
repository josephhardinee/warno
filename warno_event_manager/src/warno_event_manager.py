import psycopg2
import requests
import psutil
import json
import os

from flask import Flask, request, g

from WarnoConfig import config
from WarnoConfig import utility
from WarnoConfig import database
from WarnoConfig.models import EventWithValue, EventWithText, ProsensingPAF, InstrumentDataReference, User
from WarnoConfig.models import Instrument, Site, InstrumentLog, PulseCapture, EventCode



# Located http://flask.pocoo.org/snippets/35/
class ReverseProxied(object):
    '''Wrap the application in this middleware and configure the
    front-end server to add these headers, to let you quietly bind
    this to a URL other than / and to an HTTP scheme that is
    different than what is used locally.

    In nginx:
    location /myprefix {
        proxy_pass http://192.168.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /myprefix;
        }

    :param app: the WSGI application
    '''
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        server = environ.get('HTTP_X_FORWARDED_SERVER', '')
        if server:
            environ['HTTP_HOST'] = server
        return self.app(environ, start_response)


# Located http://flask.pocoo.org/snippets/35/
class ReverseProxied(object):
    '''Wrap the application in this middleware and configure the
    front-end server to add these headers, to let you quietly bind
    this to a URL other than / and to an HTTP scheme that is
    different than what is used locally.

    In nginx:
    location /myprefix {
        proxy_pass http://192.168.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /myprefix;
        }

    :param app: the WSGI application
    '''
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        server = environ.get('HTTP_X_FORWARDED_SERVER', '')
        if server:
            environ['HTTP_HOST'] = server
        return self.app(environ, start_response)

app = Flask(__name__)
app.wsgi_app = ReverseProxied(app.wsgi_app)

is_central = 0
cf_url = ""
cfg = None

config_path = "/opt/data/config.yml"
headers = {'Content-Type': 'application/json'}

cert_verify=False

@app.before_request
def before_request():
    """Before each Request.

    Connects to the database.
    """


@app.teardown_request
def teardown_request(exception):
    """Teardown for Requests.

    Closes the database connection if connected.

    Parameters
    ----------
    exception: optional, Exception
        An Exception that may have caused the teardown.
    """

    db = getattr(g, 'db', None)
    if db is not None:
        db.close()


@app.teardown_appcontext
def shutdown_session(exception=None):
    """Closes database session on request or application teardown.

    Parameters
    ----------
    exception: optional, Exception
        An Exception that may have caused the teardown.

    """
    database.db_session.remove()


@app.route("/eventmanager/event", methods=['POST'])
def event():
    """Event comes as a web request with a JSON packet.  The JSON is loaded into dictionary, and the event code is extracted.
    Dependent on the event code, different functions are called.

    If it is part of a predefined set of special event codes, calls a new function to handle it, depending on the
    event code.  Passes the message in to the call, then returns the return of whichever sub-function was called.

    If it is not a special case, it extracts the information from the packet and saves the event to the database.
    If the 'is_central' flag is not set, it then forwards the packet on to the 'cf_url' (both specified in *config.yml*).

    Returns
    -------
    The original message packet if a sub-function was not called, the sub-function's return if it was called.

    """
    msg = request.data
    msg_struct = dict(json.loads(msg))

    msg_event_code = msg_struct['Event_Code']
    # Request for the event code for a given description
    if msg_event_code == utility.EVENT_CODE_REQUEST:
        save_instrument_data_reference(msg, msg_struct)
        return get_event_code(msg, msg_struct)

    # Request a site id from site name
    elif msg_event_code == utility.SITE_ID_REQUEST:
        return get_site_id(msg, msg_struct)

    # Request an instrument id from instrument name
    elif msg_event_code == utility.INSTRUMENT_ID_REQUEST:
        return get_instrument_id(msg, msg_struct)
    elif msg_event_code == utility.PULSE_CAPTURE:
        return save_pulse_capture(msg, msg_struct)
    elif msg_event_code == utility.INSTRUMENT_LOG:
        return save_instrument_log(msg, msg_struct)
    # Event is special case: 'prosensing_paf' structure
    elif msg_event_code == utility.PROSENSING_PAF:
        return save_special_prosensing_paf(msg, msg_struct)

    # Any other event
    else:
        timestamp = msg_struct['Data']['Time']
        try:
            # If it can cast as a number, save as a number.  If not, save as text
            float_value = float(msg_struct['Data']['Value'])
            event_wv = EventWithValue()
            event_wv.event_code_id = msg_event_code
            event_wv.time = timestamp
            event_wv.instrument_id = msg_struct['Data']['Instrument_Id']
            event_wv.value = float_value

            database.db_session.add(event_wv)
            database.db_session.commit()
            print("Saved Value Event")
        except ValueError:
            event_wt = EventWithText()
            event_wt.event_code_id = msg_event_code
            event_wt.time = timestamp
            event_wt.instrument_id = msg_struct['Data']['Instrument_Id']
            event_wt.text = msg_struct['Data']['Value']

            database.db_session.add(event_wt)
            database.db_session.commit()
            print("Saved Text Event")
        # If application is at a site instead of the central facility, passes data on to be saved at central facility
        if not is_central:
            payload = json.loads(msg)
            requests.post(cf_url, json=payload, headers=headers, verify=cert_verify)
        return msg


def save_special_prosensing_paf(msg, msg_struct):
    """Inserts the information given in 'msg_struct' into the database, with all of the values being mapped into columns
    for the database.  If the 'is_central' flag is not set, it then forwards the packet on to the 'cf_url'
    (both specified in *config.yml*).

    Parameters
    ----------
    msg: JSON
        JSON message structure, expected format:
        {Event_Code: *code*, Data: {Time: *ISO DateTime*, Site_Id: *Integer*, Instrument_Id: *Integer*,
        Value: *Dictionary of database column names mapped to their values*}}
    msg_struct: dictionary
        Decoded version of msg, converted to python dictionary.

    Returns
    -------
    The original message 'msg' passed to it.

    """

    timestamp = msg_struct['Data']['Time']
    sql_query_a = "INSERT INTO prosensing_paf(time, site_id, instrument_id"
    sql_query_b = ") VALUES ('%s', %s, %s" % (timestamp, msg_struct['Data']['Site_Id'], msg_struct['Data']['Instrument_Id'])
    for key, value in msg_struct['Data']['Value'].iteritems():
        sql_query_a = ', '.join([sql_query_a, key])
        #Converts inf and -inf to Postgresql equivalents
        if ("-inf" in str(value)):
            sql_query_b = ', '.join([sql_query_b, "'-Infinity'"])
        elif  ("inf" in str(value)):
            sql_query_b = ', '.join([sql_query_b, "'Infinity'"])
        else:
            try:
                float(value)
                sql_query_b = ', '.join([sql_query_b, "%s" % value])
            except ValueError:
                sql_query_b = ', '.join([sql_query_b, "'%s'" % value])
    sql_query = ''.join([sql_query_a, sql_query_b, ")"])

    database.db_session.execute(sql_query)
    database.db_session.commit()

    if not is_central:
        payload = json.loads(msg)
        requests.post(cf_url, json=payload, headers=headers, verify=cert_verify)
    return msg


def save_instrument_log(msg, msg_struct):
    """Inserts the information given in 'msg_struct' into the database 'instrument_logs' table, with all of the values
    being mapped into columns for the database.

    Parameters
    ----------
    msg: JSON
        JSON message structure, expected format:
        {Event_Code: *code*, Data: {Time: *ISO DateTime*, Author_Id: *Integer*, Instrument_Id: *Integer*,
        Status: *Integer status code*, Contents: *Log Message*, Supporting_Images: *Image*}}
    msg_struct: dictionary
        Decoded version of msg, converted to python dictionary.

    Returns
    -------
    The original message 'msg' passed to it.

    """

    new_log = InstrumentLog()
    new_log.time = msg_struct['Data']['time']
    new_log.instrument_id = msg_struct['Data']['instrument_id']
    new_log.author_id = msg_struct['Data']['author_id']
    new_log.status = msg_struct['Data']['status']
    new_log.contents = msg_struct['Data']['contents']
    new_log.supporting_images = msg_struct['Data']['supporting_images']

    database.db_session.add(new_log)
    database.db_session.commit()

    return msg



def save_pulse_capture(msg, msg_struct):
    """Inserts the information given in 'msg_struct' into the database 'pulse_captures' table, with all of the values
    being mapped into columns for the database.  If the 'is_central' flag is not set, it then forwards the packet on
    to the 'cf_url' (both specified in *config.yml*).

    Parameters
    ----------
    msg: JSON
        JSON message structure, expected format:
        {Event_Code: *code*, Data: {Time: *ISO DateTime*, Site_Id: *Integer*, Instrument_Id: *Integer*,
        Value: *Array of Floats*}}
    msg_struct: dictionary
        Decoded version of msg, converted to python dictionary.

    Returns
    -------
    The original message 'msg' passed to it.

    """

    new_pulse = PulseCapture()
    new_pulse.time = msg_struct['Data']['Time']
    new_pulse.instrument_id = msg_struct['Data']['Instrument_Id']
    new_pulse.data = msg_struct['Data']['Value']

    database.db_session.add(new_pulse)
    database.db_session.commit()

    if not is_central:
        payload = json.loads(msg)
        requests.post(cf_url, json=payload, headers=headers, verify=cert_verify)
    return msg

def get_instrument_id(msg, msg_struct):
    """Searches the database for any instruments where the instrument abbreviation matches 'msg_struct['Data']'.  If the
    'is_central' flag is set and there is no instrument, returns a -1 to indicate nothing was found, but if it was found,
    returns the instrument's information to be saved. If the 'is_central' flag is not set, it then forwards the
    packet on to the 'cf_url' (both specified in *config.yml*) and returns whatever the central facility determines
    the instrument id is, saving the returned site.

    Parameters
    ----------
    msg: JSON
        JSON message structure, expected format: {Event_Code: *code*, Data: *instrument abbreviation*}
    msg_struct: dictionary
        Decoded version of msg, converted to python dictionary.

    Returns
    -------
    The instrument id or information determined by the function.

    Returned in the form of a string structured as
    {"Event_code": *integer event code*, "Data": {"Instrument_Id": *integer instrument id*, "Site_Id":
    *integer site id instrument is at*, "Name_Short": *string instrument abbreviation*, "Name_Long":
    *string full instrument name*, "Type": *string type of instrument*, "Vendor": *string instrument's vendor*,
    "Description": *string description of instrument*, "Frequency_Band":
    *two character frequency band instrument operates at*}}.

    If no instrument was found, the instrument id is passed as -1.

    """
    db_instrument = database.db_session.query(Instrument).filter(Instrument.name_short == msg_struct['Data']).first()

    # If there is an instrument with a matching name, returns all info to a site or just the id to an agent.
    if db_instrument:
        print("Found Existing Instrument")
        return '{"Event_code": %i, "Data": {"Instrument_Id": %s, "Site_Id": %s, "Name_Short": "%s", "Name_Long": "%s", ' \
               '"Type": "%s", "Vendor": "%s", "Description": "%s", "Frequency_Band": "%s"}}' \
               % (utility.INSTRUMENT_ID_REQUEST, db_instrument.id, db_instrument.site_id, db_instrument.name_short,
                  db_instrument.name_long, db_instrument.type, db_instrument.vendor,
                  db_instrument.description, db_instrument.frequency_band)
    else:
        # If it does not exist at the central facility, returns an error indicator
        if is_central:
            return '{"Data": {"Instrument_Id": -1}}'
        # If it does not exist at a site, requests the site information from the central facility
        else:
            payload = json.loads(msg)
            response = requests.post(cf_url, json=payload, headers=headers, verify=cert_verify)
            cf_msg = dict(json.loads(response.content))
            cf_data = cf_msg['Data']
            # Need to add handler for if there is a bad return from CF (if clause above)
            new_instrument = Instrument()
            new_instrument.id = cf_data['Instrument_Id']
            new_instrument.site_id = cf_data['Site_Id']
            new_instrument.name_short = cf_data['Name_Short']
            new_instrument.name_long = cf_data['Name_Long']
            new_instrument.type = cf_data['Type']
            new_instrument.vendor = cf_data['Vendor']
            new_instrument.description = cf_data['Description']
            new_instrument.frequency_band = cf_data['Frequency_Band']

            database.db_session.add(new_instrument)
            database.db_session.commit()
            utility.reset_db_keys()

            print ("Saved New Instrument")
            return '{"Event_code": %i, "Data": {"Instrument_Id": %s, "Site_Id": %s, "Name_Short": "%s", "Name_Long": "%s", ' \
                   '"Type": "%s", "Vendor": "%s", "Description": "%s", "Frequency_Band": "%s"}}' \
                   % (utility.INSTRUMENT_ID_REQUEST, cf_data['Instrument_Id'], cf_data['Site_Id'], cf_data['Name_Short'],
                      cf_data['Name_Long'], cf_data['Type'], cf_data['Vendor'], cf_data['Description'], cf_data['Frequency_Band'])



def get_site_id(msg, msg_struct):
    """Searches the database for any sites where the site abbreviation matches 'msg_struct['Data']'.  If the
    'is_central' flag is set and there is no site, returns a -1 to indicate nothing was found, but if it was found,
    returns the site's information to be saved. If the 'is_central' flag is not set, it then forwards the packet on
    to the 'cf_url' (both specified in *config.yml*) and returns whatever the central facility determines the site
    id is, saving the returned site.

    Parameters
    ----------
    msg: JSON
        JSON message structure, expected format: {Event_Code: *code*, Data: *site abbreviation*}
    msg_struct: dictionary
        Decoded version of msg, converted to python dictionary.

    Returns
    -------
    The site id or information determined by the function.

    Returned in the form of a string structured as
    {"Event_code": *integer event code*, "Data": {"Site_Id": *integer site id*, "Latitude":
    *float latitude coordinate*, "Longitude": *float longitude coordinate*, "Name_Short": *string site abbreviation*, "Name_Long":
    *string full site name*, "Facility": *string facility name*, "Mobile": *boolean true if is a mobile site*,
    "Location Name": *string location name*}}.


    If no site was found, the site id is passed as -1.

    """

    db_site = database.db_session.query(Site).filter(Site.name_short == msg_struct['Data']).first()

    # If there is a site with a matching name, returns all info to a site or just the id to an agent.
    if db_site:
        print("Found Existing Site")
        return '{"Event_code": %i, "Data": {"Site_Id": %s, "Name_Short": "%s", "Name_Long": "%s", "Latitude": "%s", ' \
               '"Longitude": "%s", "Facility": "%s", "Mobile": "%s", "Location_Name": "%s"}}' \
               % (utility.SITE_ID_REQUEST, db_site.id, db_site.name_short, db_site.name_long, db_site.latitude,
                  db_site.longitude, db_site.facility, db_site.mobile, db_site.location_name)

    else:
        # If it does not exist at the central facility, returns an error indicator
        if is_central:
            return '{"Data": {"Site_Id": -1}}'
        # If it does not exist at a site, requests the site information from the central facility
        else:
            payload = json.loads(msg)
            response = requests.post(cf_url, json=payload, headers=headers, verify=cert_verify)
            cf_msg = dict(json.loads(response.content))
            cf_data = cf_msg['Data']
            # Need to add handler for if there is a bad return from CF (if clause above)
            new_site = Site()
            new_site.id = cf_data['Site_Id']
            new_site.name_short = cf_data['Name_Short']
            new_site.name_long = cf_data['Name_Long']
            new_site.latitude = cf_data['Latitude']
            new_site.longitude = cf_data['Longitude']
            new_site.facility = cf_data['Facility']
            new_site.mobile = cf_data['Mobile']
            new_site.location_name = cf_data['Location_Name']

            database.db_session.add(new_site)
            database.db_session.commit()
            utility.reset_db_keys()

            print ("Saved New Site")
            return '{"Event_code": %i, "Data": {"Site_Id": %s, "Name_Short": "%s", "Name_Long": "%s", "Latitude": "%s", ' \
               '"Longitude": "%s", "Facility": "%s", "Mobile": "%s", "Location_Name": "%s"}}' \
               % (utility.SITE_ID_REQUEST, cf_data['Site_Id'], cf_data['Name_Short'], cf_data['Name_Long'],
                  cf_data['Latitude'], cf_data['Longitude'], cf_data['Facility'], cf_data['Mobile'], cf_data['Location_Name'])


def save_instrument_data_reference(msg, msg_struct):
    """Checks to see if there is already an instrument data reference for this event code, and if there isn't, creates
    one. Instrument data references are used to allow the servers to track which events are pertinent to a particular
    instrument (some events are for all instruments, some only for specific instrument types).  If an instrument data
    reference is to be added, this function also determines whether the reference is 'special' or not.  If there is an
    entire special table devoted to the event (where 'description' is the table name), then it is classified as 'special'.

    Parameters
    ----------
    msg: JSON
        JSON message structure, expected format:
        {Event_Code: *code*, Data: {instrument_id: *instrument id*, description: *event description*}}
    msg_struct: dictionary
        Decoded version of msg, converted to python dictionary.

    """
    db_refs = database.db_session.query(InstrumentDataReference)\
        .filter(InstrumentDataReference.instrument_id == msg_struct['Data']['instrument_id'])\
        .filter(InstrumentDataReference.description == msg_struct['Data']['description']).all()
    if not db_refs:
        special = "false"
        # "special" indicates whether this particular data description has its own table
        rows = database.db_session.execute('''SELECT column_name FROM information_schema.columns WHERE table_name = :table''', dict(table = msg_struct['Data']['description'])).fetchall()
        if rows:
            special = "true"
        new_instrument_data_ref = InstrumentDataReference()
        new_instrument_data_ref.instrument_id = msg_struct['Data']['instrument_id']
        new_instrument_data_ref.description = msg_struct['Data']['description']
        new_instrument_data_ref.special = special

        database.db_session.add(new_instrument_data_ref)
        database.db_session.commit()
        print("Saved new instrument data reference")


def get_event_code(msg, msg_struct):
    """Searches the database for any event codes where the description matches 'msg_struct['Data']'.  If the
    'is_central' flag is set and there is no event code, creates the event code in the database and returns it. If the
    'is_central' flag is not set, it then forwards the packet on to the 'cf_url' (both specified in *config.yml*) and
    returns whatever the central facility determines the event code is.

    Parameters
    ----------
    msg: JSON
        JSON message structure, expected format: {Event_Code: *code*, Data: *description*}
    msg_struct: dictionary
        Decoded version of msg, converted to python dictionary.

    Returns
    -------
    The site id determined by the function, in the form of a string structured as
    '{"Site_Id: *site id*}'.

    """

    db_code = database.db_session.query(EventCode).filter(EventCode.description == msg_struct['Data']['description']).first()
    # If the event code defined here, return it downstream
    if db_code:
        print("Found Existing Event Code")
        return '{"Event_Code": %i, "Data": {"description": "%s", "instrument_id": %s}}' % (
            db_code.event_code, msg_struct['Data']['description'], msg_struct['Data']['instrument_id'])

    # If it is not defined at the central facility, inserts a new entry into the table and returns the new code
    elif is_central:
        # Gets the highest current event code number
        max_id = database.db_session.query(EventCode.event_code).order_by(EventCode.event_code.desc()).first()[0]
        # Manually sets the new ID to be the next available ID
        insert_id = max_id + 1
        # ID's 1-9999 are reserved for explicitly set event codes, such as 'instrument_id_request'
        # Generated event codes have id's of 10000 or greater
        if insert_id < 10000:
            insert_id = 10000

        new_ec = EventCode()
        new_ec.event_code = insert_id
        new_ec.description = msg_struct['Data']['description']

        database.db_session.add(new_ec)
        database.db_session.commit()

        new_event_code = database.db_session.query(EventCode.event_code).filter(
                EventCode.description == msg_struct['Data']['description']).first()[0]

        print("Created New Event Code")
        return '{"Event_Code": %i, "Data": {"description": "%s", "instrument_id": %s}}' % (
            new_event_code, msg_struct['Data']['description'], msg_struct['Data']['instrument_id'])

    # If it is not defined at a site, requests the event code from the central facility
    else:
        payload = json.loads(msg)
        response = requests.post(cf_url, json=payload, headers=headers, verify=cert_verify)
        cf_msg = dict(json.loads(response.content))

        new_ec = EventCode()
        new_ec.event_code = cf_msg['Event_Code']
        new_ec.description = cf_msg['Data']['description']

        database.db_session.add(new_ec)
        database.db_session.commit()
        utility.reset_db_keys()

        print("Saved Event Code")
        return '{"Event_Code": %i, "Data": {"description": "%s", "instrument_id": %s}}' % (
            cf_msg['Event_Code'], cf_msg['Data']['description'], cf_msg['Data']['instrument_id'])



def initialize_database():
    """Initializes the database.  If the database is specified in config.yml as a 'test_db', the database is wiped when
    at the beginning to ensure a clean load.  If it is not a test database, a utility function is called to attempt to
    load in a postgresql database dumpfile if it exists.  First, the tables are initialized, and then if no basic database
    entries exists (users, sites, event codes), they are created.  Then, if it is designated a test database, any table
    that does not contain any entries will be filled with demo data.

    """
    print("Initialization Function")
    # If it is a test database, first wipe and clean up the database.
    if cfg['database']['test_db']:
        database.db_session.execute("DROP SCHEMA public CASCADE;")
        database.db_session.execute("CREATE SCHEMA public;")
        database.db_session.commit()
        # If it is not a test database, first attempt to load database from an existing postgres dumpfile



    utility.upgrade_db()

    # If there there are no users in the database (which any active db should have users) and it is not a test db,
    # attempt to load in a dumpfile.
    if not cfg['database']['test_db']:
        db_user = database.db_session.query(User).first()
        if db_user == None:
            utility.load_dumpfile()
            utility.reset_db_keys()

    # If there are still no users, assume the database is empty and populate the basic information
    db_user = database.db_session.query(User).first()
    if db_user == None:
        print("Populating Users")
        utility.load_data_into_table("database/schema/users.data", "users")
    else:
        print("Users in table.")

    db_site = database.db_session.query(Site).first()
    if db_site == None:
        print("Populating Sites")
        utility.load_data_into_table("database/schema/sites.data", "sites")
    else:
        print("Sites in table.")

    db_event_code = database.db_session.query(EventCode).first()
    if db_event_code == None:
        print("Populating Event Codes")
        utility.load_data_into_table("database/schema/event_codes.data", "event_codes")
    else:
        print("Event_codes in table.")

    # If it is set to be a test database, populate extra information.
    if cfg['database']['test_db']:
        print ("Test Database Triggered")
        test_tables = [
                       "instruments",
                       "instrument_logs",
                       "prosensing_paf",
                       "events_with_text",
                       "events_with_value",
                       "pulse_captures",
                       "table_references",
                       "instrument_data_references"
                   ]
        for table in test_tables:
            result = database.db_session.execute("SELECT * FROM %s LIMIT 1" % table).fetchone()
            if result == None:
                print("Populating %s" % table)
                utility.load_data_into_table("database/schema/%s.data" % table, table)
            else:
                print("%ss in table." % table)
    else:
        print ("Test Database is a falsehood")

    # Without this, the database prevents the server from running properly.
    utility.reset_db_keys()
    database.db_session.remove()

@app.route('/eventmanager')
def hello_world():
    """Calculates very basic information and returns a string with it.  Used to verify that the event manager is
    operational and accessible from the outside.

    Returns
    -------
    String message with basic information such as current CPU usage.
    """
    ret_message = 'Hello World! Event Manager is operational. CPU Usage on Event Manager VM is: %g \n ' % psutil.cpu_percent()
    ret_message2 = '\n Site is: %s' % os.environ.get('SITE')
    return ret_message + ret_message2


if __name__ == '__main__':
    cfg = config.get_config_context()

    if cfg['type']['central_facility']:
        is_central = 1
    else:
        cf_url = cfg['setup']['cf_url']
        cert_verify = cfg['setup']['cert_verify']

    initialize_database()

    app.run(host='0.0.0.0', port=80, debug=True)
