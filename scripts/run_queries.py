"""Run every statement in a .sql file against the configured database and
print row counts and the first rows. Used to verify docs/course-queries.sql.

    python scripts/run_queries.py docs/course-queries.sql [--rows 5]
"""

import os
import re
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection  # noqa: E402


def statements(text):
    body = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('--'))
    for chunk in body.split(';'):
        if chunk.strip():
            yield chunk.strip()


def portable(sql):
    if connection.vendor == 'sqlite':
        sql = re.sub(r"CURRENT_TIMESTAMP\s*-\s*INTERVAL\s*'(\d+) days'", r"datetime('now', '-\1 days')", sql)
    return sql


def main(path, rows=5):
    text = open(path, encoding='utf-8').read()
    failures = 0
    with connection.cursor() as cursor:
        for n, sql in enumerate(statements(text), start=1):
            try:
                cursor.execute(portable(sql))
                fetched = cursor.fetchall()
                columns = [c[0] for c in cursor.description]
                print(f'-- query {n}: {len(fetched)} rows; columns: {", ".join(columns)}')
                for row in fetched[:rows]:
                    print('   ', row)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f'-- query {n}: ERROR {exc}')
    return failures


if __name__ == '__main__':
    args = sys.argv[1:]
    limit = int(args[args.index('--rows') + 1]) if '--rows' in args else 5
    sys.exit(1 if main(args[0], limit) else 0)
