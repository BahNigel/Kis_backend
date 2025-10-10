"""
Expose the correct settings depending on DJANGO_ENV
Usage: export DJANGO_ENV=local|production
Default: local
"""
# Select settings package based on DJANGO_ENV variable.
import os
env = os.environ.get("DJANGO_ENV", "local").lower()
if env == "production":
    from .production import *  # noqa
else:
    from .local import *  # noqa
