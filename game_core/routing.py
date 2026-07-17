from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/fifa/<int:session_id>/', consumers.FifaConsumer.as_asgi()),
]
