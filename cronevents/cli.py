import argparse
import os
import json
import sys
import time

import cronevents.event_manager


def cli():
    parser = argparse.ArgumentParser(description='Buelon command-line interface')
    parser.add_argument('-v', '--version', action='version', version='Cron Events 0.0.28')

    subparsers = parser.add_subparsers(title='Commands', dest='command', required=False)

    # Hub command
    hub_parser = subparsers.add_parser('manager', help='Run the hub')
    hub_parser.add_argument('-p', '--postgres', required=False, help='Postgres connection (host:port:user:password:database)')

    # Register command
    register_parser = subparsers.add_parser('register', help='Register a new event')
    register_parser.add_argument('-p', '--postgres', required=False, help='Postgres connection (host:port:user:password:database)')

    # Parse arguments
    args, remaining_args = parser.parse_known_args()
    # Handle the commands
    if args.command == 'manager':
        if args.postgres:
            os.environ['CRON_EVENTS_USING_POSTGRES'] = 'true'
            (os.environ['POSTGRES_HOST'], os.environ['POSTGRES_PORT'], os.environ['POSTGRES_USER'],
             os.environ['POSTGRES_PASSWORD'], os.environ['POSTGRES_DATABASE']) = args.postgres.split(':')
        cronevents.event_manager.main()
    if args.command == 'register':
        if args.postgres:
            os.environ['CRON_EVENTS_USING_POSTGRES'] = 'true'
            (os.environ['POSTGRES_HOST'], os.environ['POSTGRES_PORT'], os.environ['POSTGRES_USER'],
             os.environ['POSTGRES_PASSWORD'], os.environ['POSTGRES_DATABASE']) = args.postgres.split(':')
        os.environ['REGISTER_CRON_EVENT'] = 'true'
        print('\nthis command current does nothing')
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    cli()
