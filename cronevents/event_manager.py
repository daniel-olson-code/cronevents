import math
import inspect
import time
import sys
import subprocess
import shlex
import json
import uuid
import os
import datetime
import traceback

import dotenv
import buelon.helpers.sqlite3_helper
import buelon.helpers.postgres


dotenv.load_dotenv('.env')

# environment variables
USING_POSTGRES = os.environ.get('CRON_EVENTS_USING_POSTGRES', None) == 'true'
REGISTER_CRON_EVENT = os.environ.get('REGISTER_CRON_EVENT', None) == 'true'
# LOG_CRON_EVENT_LOGS = os.environ.get('LOG_CRON_EVENT_LOGS', None) == 'true'  # here for reference. Used in event.py
LOG_CRON_EVENT_TRIGGERS = os.environ.get('LOG_CRON_EVENT_TRIGGERS', None) == 'true'

DEFAULT_DB = buelon.helpers.sqlite3_helper.Sqlite3(
    location=os.path.join('.cronevents', 'event_manager.db')
)
DAYS_OF_THE_WEEK = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


class CronEventError(Exception):
    """
    Exception for cron event errors.
    """


class CronEventSyntaxError(CronEventError):
    """
    Exception for cron event syntax errors.
    """


def get_db():
    if USING_POSTGRES:
        return buelon.helpers.postgres.get_postgres_from_env()
    return DEFAULT_DB


def try_isnan(v):
    try:
        return math.isnan(v)
    except:
        return False


def is_int(value):
    try:
        int(value)
        return True
    except ValueError:
        return False


def try_number(value, _type=float, on_fail_return_value=None, asignment=None, nan_allowed=False):
    try:
        v = _type(value)
        a = isinstance(asignment, list)
        if a:
            if len(asignment) < 1:
                asignment.append(v)
            else:
                asignment[0] = v
        if not nan_allowed and try_isnan(v):
            return on_fail_return_value
        return v if not a else True
    except:
        return on_fail_return_value


def query_at_time_syntax_checker(at: str):
    has_pm = False
    if 'am' in at:
        if 'pm' in at:
            raise CronEventSyntaxError('Only one am/pm is allowed')
        if not at.endswith('am'):
            raise CronEventSyntaxError('Invalid am format near `am`')
    if 'pm' in at:
        if not at.endswith('pm'):
            raise CronEventSyntaxError('Invalid pm format near `pm`')
        has_pm = True

    at = at.replace('am', '').replace('pm', '').strip()

    if at.count(':') > 2:
        raise CronEventSyntaxError('Invalid time format. Max use of `:` is 2')

    if at.count(':') == 2:
        hour, minute, second = at.split(':')
    elif at.count(':') == 1:
        hour, minute = at.split(':')
        second = '0'
    else:
        hour = at
        minute = '0'
        second = '0'

    try:
        hour = int(hour) + 12 if has_pm else int(hour)
        minute = int(minute)
        second = int(second)
    except ValueError:
        raise CronEventSyntaxError(f'Non-int value for time found: `{at}`')

    if 23 < hour < 0:
        raise CronEventSyntaxError(f'Invalid hour value: `{hour}`. Must be 23 < hour < 0')
    if 59 < minute < 0:
        raise CronEventSyntaxError(f'Invalid minute value: `{minute}`. Must be 59 < minute < 0')
    if 59 < second < 0:
        raise CronEventSyntaxError(f'Invalid second value: `{second}`. Must be 59 < second < 0')


def query_syntax_checker(query: str) -> None:
    if not isinstance(query, str):
        raise CronEventSyntaxError('Query must be a string')

    query = query.lower()
    if not query.strip().startswith('every'):
        raise CronEventSyntaxError('Query must start with "every"')

    query = query.replace('every', '').strip()

    if '@' in query:
        if query.count('@') > 1:
            raise CronEventSyntaxError('Only one @ is allowed')
        query, at = query.split('@')
        query_at_time_syntax_checker(at)

    for day in DAYS_OF_THE_WEEK:
        if day in query:
            if query.count(day) > 1:
                raise CronEventSyntaxError(f'Only one {day} is allowed')
            if '' != query.replace(day, '').strip():
                raise CronEventSyntaxError(f'Invalid format. Using day of the week cannot contain other values. (remove: `{query.replace(day, "")}` from `{query}`')
            else:
                return

    units = ['day', 'hour', 'minute', 'second']
    units += [f'{u}s' for u in units]
    tokens = [t.strip() for t in query.split()]
    if 'minus' in tokens:
        before_minus = tokens[:tokens.index('minus')]
        has_unit, has_number = False, False
        for token in before_minus:
            has_unit = has_unit or token in units
            if token in units:
                has_unit = True
            has_number = has_number or is_int(token)

        if not has_unit:
            raise CronEventSyntaxError(f'No unit found in before minus `{query}`')
        if not has_number:
            raise CronEventSyntaxError(f'No number found in before minus `{query}`')

        after_minus = tokens[tokens.index('minus') + 1:]
        has_unit, has_number = False, False
        for token in after_minus:
            has_unit = has_unit or token in units
            has_number = has_number or is_int(token)

        if not has_unit:
            raise CronEventSyntaxError(f'No unit found in after minus `{query}`')
        if not has_number:
            raise CronEventSyntaxError(f'No number found in after minus `{query}`')

        tokens.remove('minus')

    on_number = True

    for token in tokens:
        if on_number:
            if not is_int(token):
                raise CronEventSyntaxError(f'Expected number, got `{token}`')
            on_number = False
        else:
            if token not in units:
                raise CronEventSyntaxError(f'Expected unit, got `{token}`. Available units {", ".join(units)}')
            on_number = True


def temp_file_name():
    if not os.path.exists('.cronevents'):
        os.makedirs('.cronevents')
    if not os.path.exists(os.path.join('.cronevents', 'temp')):
        os.makedirs(os.path.join('.cronevents', 'temp'))
    return os.path.join('.cronevents', 'temp', f'temp_{uuid.uuid4().hex}.json')


def temp_save_json(data):
    filename = temp_file_name()
    with open(filename, 'w') as f:
        json.dump(data, f)
    return filename


def invoke(module, func, args, kwargs):
    event_id = f'e{uuid.uuid1().hex}'
    script = '-c "import cronevents.event;cronevents.event.main()"'  # os.path.join(os.getcwd(), 'event.py')
    cmd = f'{sys.executable} {script} {event_id} {module} {func} {temp_save_json(args)} {temp_save_json(kwargs)}'
    print('running', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), module, func)  # , f'"{cmd}"')

    subprocess.Popen(
        shlex.split(cmd),
        env=dict(os.environ)
    )

    if LOG_CRON_EVENT_TRIGGERS:
        get_db().upload_table('cron_event_triggers', [{
            'id': event_id,
            'epoch': time.time(),
            'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'cmd': cmd,
            'module': module,
            'func': func,
            'args': json.dumps(args),
            'kwargs': json.dumps(kwargs),
        }], id_column='id')


def create_event(module, func, args, kwargs, query):
    get_db().upload_table('cronevents', [{
        'id': f'{module}|{func}',
        'query': query,
        'last': datetime.datetime.utcfromtimestamp(time.time()),
        'module': module,
        'func': func,
        'args': json.dumps(args),
        'kwargs': json.dumps(kwargs),
    }], id_column='id')


def get_word_before_word(word: str, txt: str):
    if word not in txt:
        return ''
    return txt.split(word)[0].strip().split(' ')[-1].strip().split('\n')[-1].strip().split('\t')[-1].strip()


def parse_time(s: str):
    m = 0
    if 'minus' in s:
        m = parse_time(s.split('minus')[-1])
        s = s.split('minus')[0]
    v = 0
    if 'day' in s:
        x = try_number(get_word_before_word('day', s), on_fail_return_value=1.0)
        v += 86400 * x
    if 'hour' in s:
        x = try_number(get_word_before_word('hour', s), on_fail_return_value=1.0)
        v += 3600 * x
    if 'minute' in s:
        x = try_number(get_word_before_word('minute', s), on_fail_return_value=1.0)
        v += 60 * x
    if 'second' in s:
        x = try_number(get_word_before_word('second', s), on_fail_return_value=1.0)
        v += x
    return (v if v > 0 else 86400) - m


def parse_time_timedelta(s: str):
    def force_int(x):
        return try_number(x, _type=int, on_fail_return_value=0)

    def strip_list(l):
        return [x.strip() for x in l]

    query = s.split('@')[-1]
    q = query.lower().split('am')[0].split('pm')[0]

    if q.count(':') == 0:
        hr, _min, sec = force_int(q), 0, 0
    elif q.count(':') == 1:
        hr, _min = strip_list(q.split(':'))
        sec = 0
    elif q.count(':') == 2:
        hr, _min, sec = strip_list(q.split(':'))
    else:
        hr, _min, sec = 0, 0, 0

    if 'pm' in query.lower() and int(hr) < 12:
        hr = force_int(hr) + 12

    return datetime.timedelta(hours=force_int(hr), minutes=force_int(_min), seconds=force_int(sec))


def ready(row):
    try:
        # print('ready', row)
        # t = row['time']
        # _type = row['type']
        query: str = row['query'].lower()
        last = (row['last'] + (row['last'].utcoffset() or datetime.timedelta(seconds=0))).timestamp()

        if any([d in query for d in DAYS_OF_THE_WEEK]):
            last = datetime.datetime.fromtimestamp(last, datetime.UTC)
            now_utc = datetime.datetime.now(datetime.UTC)
            if abs((now_utc - last).days) < 5:  # can only run once a week
                return False
            if now_utc.strftime('%A').lower() in query:
                if '@' in query:
                    t = parse_time_timedelta(query)
                    current_utc_time = datetime.timedelta(hours=now_utc.hour, minutes=now_utc.minute,
                                                          seconds=now_utc.second)
                    return current_utc_time >= t
                return True
            return False

        if '@' not in query:
            t = parse_time(row['query'])  # - 10.
            # print('t', t, time.time() - last)
            return time.time() - last > t
        else:  # _type == '@':
            time_to = parse_time(query.split('@')[0]) if 'every' in query else 86400 - 30
            query = query.split('@')[-1]
            q = query.lower().split('am')[0].split('pm')[0]
            if q.count(':') == 0:
                hr, _min, sec = str(try_number(q, int, on_fail_return_value='0')).strip(), '0', '0'
            elif q.count(':') == 1:
                hr, _min, sec = tuple([*tuple(map(lambda s: s.strip(), q.split(':'))), '0'])
            elif q.count(':') == 2:
                hr, _min, sec = tuple(map(lambda s: s.strip(), q.split(':')))
            elif q.count(':') == 1:
                hr, _min, sec = tuple(q.split(':'))
            else:
                hr, _min, sec = '0', '0', '0'
            if 'pm' in query.lower() and int(hr) < 12:
                hr = str(int(hr) + 12)
            # every 1 day @ 8:00:00 AM
            # if '@' in query:
            # hr, _min, sec = tuple(map(lambda s: s.strip(),
            #     (query.split('@')[-1].lower().split('am')[0].split('pm')[0]).split(':')))
            # if 'pm' in query.lower() and int(hr) < 12:
            #     hr = str(int(hr) + 12)
            force_zero = lambda x: '0' + f'{x}' if len(x) == 1 else f'{x}'
            hr, _min, sec = force_zero(hr), force_zero(_min), force_zero(sec)
            time_to_execute = datetime.datetime.strptime(
                datetime.datetime.utcnow().strftime('%Y-%m-%d') + f' {hr}:{_min}:{sec}',
                '%Y-%m-%d %H:%M:%S'
            )
            # print('time_to_execute', time_to_execute, datetime.datetime.now(), time.time() - last, datetime.datetime.now().strftime('%Y-%m-%d') + f' {hr}:{_min}:{sec}')
            days = math.floor((time_to-1) / 60 / 60 / 24)
            datetime.datetime.fromtimestamp(last)
            datetime.datetime.fromtimestamp(time.time())
            enough_time_past = (datetime.datetime.fromtimestamp(time.time()) - datetime.timedelta(days=days)).date() > datetime.datetime.fromtimestamp(last).date()
            return time_to_execute < datetime.datetime.utcnow() and enough_time_past  # time.time() - last > time_to
    except Exception as e:
        print('error in ready', e)
        traceback.print_exc()
        return False

def run(row):
    module, func, args, kwargs = row['module'], row['func'], json.loads(row['args']), json.loads(row['kwargs'])
    invoke(module, func, args, kwargs)


def update(row):
    row['last'] = datetime.datetime.utcfromtimestamp(time.time())  # datetime.datetime.now(datetime.UTC)  # time.time()
    get_db().upload_table('cronevents', [row], id_column='id')


def event(query: str, module: str=None, func: str=None, args: list = None, kwargs: dict = None):
    def __func(f):
        nonlocal module, func
        if REGISTER_CRON_EVENT:
            query_syntax_checker(query)
            _module, _func = os.path.basename(inspect.getmodule(f).__file__).split('.')[0], f.__name__
            module, func = module if isinstance(module, str) else _module, func if isinstance(func, str) else _func

            db = get_db()
            try:
                vals = db.download_table(sql=f"select * from cronevents where module='{module}' and func='{func}'")
            except:
                vals = None

            if vals:
                print('modifying event', module, func)
                vals[0]['query'] = query
                vals[0]['args'] = json.dumps(args or [])
                vals[0]['kwargs'] = json.dumps(kwargs or {})
                db.upload_table('cronevents', vals, id_column='id')
            else:
                print('adding event', module, func)
                create_event(module, func, args or [], kwargs or {}, query)
        return f
    return __func


def main():
    print('version 0.0.28')
    while True:
        try:
            for row in get_db().download_table('cronevents'):
                if ready(row):
                    run(row)
                    update(row)
        except buelon.helpers.postgres.psycopg2.errors.UndefinedTable:
            print('No events have been registered')
            time.sleep(10.)
        except Exception as e:
            print('error ->', e)
            traceback.print_exc()
        time.sleep(2.)


if __name__ == '__main__':
    main()












