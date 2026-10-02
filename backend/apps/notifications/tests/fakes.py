"""In-process stand-in for Firebase. Selected via settings.RACHEETA["PUSH_SENDER"]."""

from apps.notifications.push import PushMessage, PushResult


class RecordingSender:
    calls: list[tuple[str, PushMessage]] = []
    # token -> PushResult to return, or an Exception instance to raise
    outcomes: dict[str, object] = {}

    @classmethod
    def reset(cls) -> None:
        cls.calls = []
        cls.outcomes = {}

    def send(self, token: str, message: PushMessage) -> PushResult:
        type(self).calls.append((token, message))
        outcome = type(self).outcomes.get(token, PushResult.SENT)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
