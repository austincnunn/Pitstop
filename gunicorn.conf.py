"""Gunicorn config.

With --preload, the master process imports run:app (and opens DB
connections during startup) once, then forks worker processes. Forked
workers inherit the master's open socket file descriptors, including
pooled DB connections -- multiple processes then share the same
underlying Postgres connection, corrupting the wire protocol.
post_fork disposes the inherited pool so each worker opens its own
fresh connections.
"""


def post_fork(server, worker):
    from run import app

    with app.app_context():
        from app import db
        db.engine.dispose()
