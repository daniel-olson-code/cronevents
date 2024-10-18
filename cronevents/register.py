import os
import sys
import subprocess
import importlib


import cronevents.event_manager


def register_events(file_path, postgres):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f'File not found: {file_path}')

    env = {
        **os.environ,
        'REGISTER_CRON_EVENT': 'true'
    }

    if postgres:
        env['CRON_EVENTS_USING_POSTGRES'] = 'true'
        env['POSTGRES_HOST'], env['POSTGRES_PORT'], env['POSTGRES_USER'], env['POSTGRES_PASSWORD'], env['POSTGRES_DATABASE'] = postgres.split(':')

    p = subprocess.Popen([sys.executable, file_path], env=dict({**os.environ, 'REGISTER_CRON_EVENT': 'true'}))
    p.wait()

    # os.environ['REGISTER_CRON_EVENT'] = 'true'
    # importlib.reload(cronevents.event_manager)
    #
    # module_name = os.path.splitext(os.path.basename(file_path))[0]
    # spec = importlib.util.spec_from_file_location(module_name, file_path)
    # module = importlib.util.module_from_spec(spec)
    # spec.loader.exec_module(module)
    # del module
    #
    # os.environ['REGISTER_CRON_EVENT'] = 'false'
    # importlib.reload(cronevents.event_manager)

