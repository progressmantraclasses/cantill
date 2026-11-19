"""uvicorn entrypoint:  uvicorn app.asgi:application --host 0.0.0.0 --port 8000"""
from asgiref.wsgi import WsgiToAsgi

from . import create_app

flask_app = create_app()
application = WsgiToAsgi(flask_app)
