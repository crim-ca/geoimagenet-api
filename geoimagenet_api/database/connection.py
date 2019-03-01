from contextlib import contextmanager

from sqlalchemy.exc import OperationalError
from geoimagenet_api import config
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


class _ConnectionManager:
    """Handles the creation of the engine and sessions.

    This class is instantiated only once.

    This permits creating the engine and session factory only once, but
    adds the possibility to manually recreate them using a new configuration.
    """

    def __init__(self):
        self._engine = None
        self._session_maker = None
        self.reload_config()

    @property
    def engine(self):
        return self._engine

    @contextmanager
    def get_db_session(self):
        session = self._session_maker()
        try:
            yield session
        finally:
            self._session_maker.remove()

    def reload_config(self):
        """This function is mostly useful for unit tests.
        When calling it, there shouldn't be any checked-out connections.
        """
        if self._engine is not None:
            self._engine.dispose()
        verbose_sqlalchemy = config.get("verbose_sqlalchemy", bool)
        self._engine = create_engine(
            config.get_database_url(),
            convert_unicode=True,
            echo=verbose_sqlalchemy,
            pool_size=20,
            max_overflow=10,
            # ping connection status before checkout
            # to avoid connection errors on database restarts
            pool_pre_ping=True,
        )
        self._session_maker = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=self._engine)
        )


connection_manager = _ConnectionManager()


def wait_for_db_connection(seconds=30):
    """Wait for a successful database connection for a specified time"""
    engine = connection_manager.engine
    while seconds >= 1:
        try:
            engine.execute("SELECT 1;")
            return
        except OperationalError:
            print(f"Can't connect to postgis url. Retrying {seconds}s. ({engine.url})")
            seconds -= 1
            import time

            time.sleep(1)
    import sys

    sys.exit(1)
