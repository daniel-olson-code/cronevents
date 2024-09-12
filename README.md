# Cron Events

This module provides a way to schedule recurring events using a cron-like syntax.
Events can be scheduled to run at specific intervals or at specific times on specific days.


## Table of Contents
<!--
- [Features](#features)
-->
- [Installation](#installation) <!-- - [Quick Start](#quick-start) -->
- [Learn by Example](#example) 
- [License](#license)

## Installation

`pip install cronevents`


[//]: # (## Quick Start)

[//]: # (1. Get example template: `bue example` &#40;warning: this command will over-write `.env`&#41;)

[//]: # (2. Start Bucket server, Hub and 3 workers: `bue demo`)

[//]: # (3. Upload script and wait for results: `python3 example.py`)


## Learn by Example

```python
"""Cron-like event scheduling module.

This module provides a way to schedule recurring events using a cron-like syntax.
Events can be scheduled to run at specific intervals or at specific times on specific days.

Syntax:
    'every (`Weekday` or `n unit`) [@ hh[:mm[:ss]] ["am" or "pm"]]'

Examples:
    'every 2 days @ 10:00:00 pm'
    'every Monday @ 23'
    'every 5 seconds'

Note:
    Using '@' will run the event at least once a day.
"""

# Uncomment to register events to the event manager
# import os
# os.environ['REGISTER_CRON_EVENT'] = 'true'

from cronevents.event_manager import event


@event('every 31 seconds')
def test():
    """Write 'test' to a file and print it every 31 seconds."""
    with open('test.txt', 'a') as f:
        f.write('test\n')
    print('test')


@event('every 2 days 1 hours 23 minutes 2 seconds')
def test2():
    """Write 'test2' to a file and print 'test2' every 2 days, 1 hour, 23 minutes, and 2 seconds."""
    with open('test.txt', 'a') as f:
        f.write('test2\n')
    print('test2')


@event('every 1 days @ 2:00 pm')
def test3():
    """Write 'test3' to a file and print it daily at 2:00 PM."""
    with open('test.txt', 'a') as f:
        f.write('test3\n')
    print('test3')


@event('every Friday')
def test4():
    """Write 'test4' to a file and print it every Friday."""
    with open('test.txt', 'a') as f:
        f.write('test4\n')
    print('test4')


@event('every Tuesday @ 3:00')
def test5():
    """Write 'test5' to a file and print it every Tuesday at 3:00 AM."""
    with open('test.txt', 'a') as f:
        f.write('test5\n')
    print('test5')
```

## License
* MIT License