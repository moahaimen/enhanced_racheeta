from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = "apps.notifications"
    label = "notifications"
    verbose_name = "Notifications"

    def ready(self) -> None:
        # Receivers subscribe to other modules' domain events here, so the
        # emitting modules never import (or know about) notifications.
        from . import receivers

        receivers.connect()
