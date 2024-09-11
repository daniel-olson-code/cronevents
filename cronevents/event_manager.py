import math
import inspect
import time
import io
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

print('version 0.0.26')

USING_POSTGRES = os.environ.get('CRON_EVENTS_USING_POSTGRES', None) == 'true'
CRON_EVENT_CREATION = os.environ.get('CRON_EVENT_CREATION', None) == 'true'

_db = buelon.helpers.sqlite3_helper.Sqlite3(
    location=os.path.join('.cronevents', 'event_manager.db')
)


def get_db():
    global _db
    if USING_POSTGRES:
        return buelon.helpers.postgres.get_postgres_from_env()
    return _db


def try_isnan(v):
    try:
        return math.isnan(v)
    except:
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
    event_id = f'event{uuid.uuid1().hex}'
    script = os.path.join(os.getcwd(), 'event.py')
    cmd = (f'cd {os.getcwd()} && {sys.executable} '
           f'{script} {event_id} {module} {func} {temp_save_json(args)} {temp_save_json(kwargs)}')
    print('running', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f'"{cmd}"')

    subprocess.Popen(
        shlex.split(cmd),
    )

    get_db().upload_table('cron_events_log', [{
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
    get_db().upload_table('events', [{
        'id': f'{module}|{func}',
        'query': query,
        'last': 0,
        'module': module,
        'func': func,
        'args': json.dumps(args),
        'kwargs': json.dumps(kwargs),
    }], id_column='id')


def get_word_before_word(word: str, txt: str):
    if word not in txt:
        return ''
    return txt.split(word)[0].strip().split(' ')[-1].split('\n')[-1].split('\t')[-1]


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


def parse_time_str(s: str):
    query = s  # query.split('@')[-1]
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
    return datetime.datetime.strptime(
        datetime.datetime.utcnow().strftime('%Y-%m-%d') + f' {hr}:{_min}:{sec}',
        '%Y-%m-%d %H:%M:%S'
    )


def ready(row):
    # t = row['time']
    # _type = row['type']
    last = row['last']
    query: str = row['query']
    if '@' not in query:
        t = parse_time(row['query']) - 10.
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


def run(row):
    module, func, args, kwargs = row['module'], row['func'], json.loads(row['args']), json.loads(row['kwargs'])
    invoke(module, func, args, kwargs)


def update(row):
    row['last'] = time.time()
    get_db().upload_table('events', [row], id_column='id')


def event(query: str, module: str=None, func: str=None, args: list = None, kwargs: dict = None):
    def __func(f):
        nonlocal module, func
        if CRON_EVENT_CREATION:
            _module, _func = os.path.basename(inspect.getmodule(f).__file__).split('.')[0], f.__name__
            module, func = module if isinstance(module, str) else _module, func if isinstance(func, str) else _func

            db = get_db()
            vals = db.download_table(sql=f"select * from events where module='{module}' and func='{func}'")
            if vals:
                vals[0]['query'] = query
                vals[0]['args'] = json.dumps(args or [])
                vals[0]['kwargs'] = json.dumps(kwargs or {})
                db.upload_table('events', vals, id_column='id')
            else:
                create_event(module, func, args or [], kwargs or {}, query)
        return f
    return __func


if __name__ == '__main__':
    while True:
        try:
            for row in get_db().download_table('events'):
                if ready(row):
                    run(row)
                    update(row)
        except Exception as e:
            print('error ->', e)
            traceback.print_exc()
        time.sleep(2.)












