import os

from distutils import util


def to_bool(env, default='false'):
    """
    Convert a string to a bool.
    """
    return bool(util.strtobool(os.getenv(env, default)))
