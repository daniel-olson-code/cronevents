import os
import sys
import time
import shlex
import subprocess
import threading
import queue
import datetime
import platform

import pexpect
import cronevents.event_manager
import buelon.helpers.sqlite3_helper
import buelon.helpers.postgres


LOG_CRON_EVENT_LOGS = os.environ.get('LOG_CRON_EVENT_LOGS', None) == 'true'


class EventLogger:
    def __init__(self, event_id):
        self.event_id = event_id
        self.db = cronevents.event_manager.get_db()

        self.queue = queue.Queue()
        self.current_index = -1
        self.last_log = time.time()

        self.thread = None

    def start_logger(self):
        self.thread = threading.Thread(target=self.logger)
        self.thread.start()

    def stop_logger(self):
        self.queue.put(None)
        if self.thread:
            self.thread.join()
            self.thread = None

    def __del__(self):
        self.stop_logger()

    def create_row(self, logs: list[str] | list[tuple[str, float]]):
        for log in logs:
            self.current_index += 1

            if isinstance(log, tuple):
                log, t = log
            else:
                t = time.time()

            yield {
                'event_id': self.event_id,
                'index': self.current_index,
                'line': log,
                # 'epoch': t,
                'utc_time': datetime.datetime.fromtimestamp(time.time(), tz=datetime.timezone.utc),  # datetime.datetime.fromtimestamp(t, datetime.UTC)
            }

    def upload(self, logs: list[str] | list[tuple[str, float]]):
        table = list(self.create_row(logs))
        try:
            upload_logs(self.db, self.event_id, table)
        except:
            self.db = cronevents.event_manager.get_db()
            upload_logs(self.db, self.event_id, table)

    def log(self, s):
        self.queue.put(s)

    def logger(self):
        current_log = []
        while True:
            log = self.queue.get()
            if log is None:
                break

            current_log.append((log, time.time()))

            if time.time() - self.last_log > 1 or len(current_log) > 100:
                self.upload(current_log)
                current_log = []
                self.last_log = time.time()

        if current_log:
            self.upload(current_log)


def upload_logs(db, event_id, logs):
    if logs:
        kwargs = {}
        index_query = 'create index if not exists event_logs_event_id_idx on cron_events_log (event_id);'
        if isinstance(db, buelon.helpers.postgres.Postgres):
            index_query = 'create index if not exists event_logs_event_id_idx on cron_events_log using hash (event_id);'
            kwargs['partition'] = 'event_id'
            kwargs['partition_query'] = f'''CREATE TABLE if not exists "cron_events_log_{event_id}" 
                                    PARTITION OF "cron_events_log" FOR VALUES IN ('{event_id}');'''

        db.upload_table(
            f'cron_events_log',
            logs,
            id_column=['event_id', 'index'],
            **kwargs
        )
        db.query(index_query)


def main():
    try:
        # get event id
        event_id = sys.argv[-5]

        # get module
        og_module = module = sys.argv[-4]

        # get function name
        func = sys.argv[-3]

        # get args
        args = sys.argv[-2]

        # get kwargs
        kwargs = sys.argv[-1]

        # print(module, func, args, kwargs)

        script = '-c "import cronevents.event_run;cronevents.event_run.main()"'  # os.path.join(os.getcwd(), 'event_run.py')
        cmd = f'{sys.executable} {script} {module} {func} {args} {kwargs}'

        if LOG_CRON_EVENT_LOGS:
            logger = EventLogger(event_id)
            logger.start_logger()

        if platform.system() != 'Windows':
            p = pexpect.spawn(
                cmd,
                cwd=os.getcwd(),
                env=dict(os.environ),
                timeout=60 * 60 * 24 * 7,  # 1 week
            )

            while not p.eof():
                line = p.readline()
                if LOG_CRON_EVENT_LOGS:
                    logger.log(line.decode('utf-8').strip())
        else:
            process = subprocess.Popen(
                shlex.split(cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.getcwd(),
                env=dict(os.environ)
            )

            if not LOG_CRON_EVENT_LOGS:
                process.wait()
            else:
                out, err = process.communicate()

                lines = out.decode().splitlines() + err.decode().splitlines()
                n = 1000
                for i in range(0, len(lines), n):
                    logger.upload(lines[i:i + n])

        if LOG_CRON_EVENT_LOGS:
            logger.stop_logger()
    finally:
        try:
            os.remove(sys.argv[-2])
        except:
            pass
        try:
            os.remove(sys.argv[-1])
        except:
            pass


if __name__ == '__main__':
    main()

