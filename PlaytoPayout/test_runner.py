import psycopg2
from django.db import connections
from django.test.runner import DiscoverRunner


class ForceDropTestRunner(DiscoverRunner):
    def teardown_databases(self, old_config, **kwargs):
        db = connections['default'].settings_dict
        test_db_name = db.get('TEST', {}).get('NAME') or f"test_{db['NAME']}"
        for c in connections.all():
            c.close()
        # Connect to the maintenance DB to terminate sessions on the test DB
        pg = psycopg2.connect(
            dbname='postgres',
            user=db['USER'],
            password=db['PASSWORD'],
            host=db['HOST'],
            port=db['PORT'],
        )
        pg.autocommit = True
        with pg.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                [test_db_name],
            )
        pg.close()
        super().teardown_databases(old_config, **kwargs)
