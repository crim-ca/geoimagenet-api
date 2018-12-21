import alembic.config


def upgrade_head():
    argv = [
        '--raiseerr',
        'upgrade', 'head',
    ]
    alembic.config.main(argv=argv)
