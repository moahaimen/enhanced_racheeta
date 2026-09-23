"""ASGI entrypoint.

The project is ASGI-ready: switch the production server to an ASGI worker
(e.g. `uvicorn config.asgi:application`) when async views or WebSockets are
introduced. See docs/ARCHITECTURE.md.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()
