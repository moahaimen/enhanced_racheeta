"""Remove demo data — and refuse whenever ownership cannot be proven.

Guarantee (docs/DEMO_DATA.md): the only rows ever deleted are
  1. rows registered in `DemoRecord`;
  2. auto-created many-to-many link rows that disappear with them;
  3. "demo-internal" rows that the deletion reaches, i.e. rows created later by activity among
     demo objects (a booking made while demonstrating, the login token of a demo account) whose
     every reference to a non-reference model points at a registered or to-be-deleted row.
If the deletion would also delete or modify any other row (a real user who booked a demo
provider, a real review of a demo provider...), `ClearRefused` is raised and, because everything
runs in one transaction, NOTHING has been changed. Reference data (geography, specialties,
billing plans) is only ever referenced, never a root and never deleted.

Django raises `ProtectedError` eagerly for PROTECT foreign keys even when the protecting rows are
being deleted too, so deletion proceeds in dependency layers: a model whose rows are still protected
by other demo rows waits until those are gone.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from django.apps import apps
from django.db import transaction
from django.db.models import ProtectedError, RestrictedError
from django.db.models.deletion import Collector

from .models import DemoRecord

# Models a demo row may point at without being demo-owned: shared reference data.
REFERENCE_LABELS = frozenset(
    {
        "geography.Country",
        "geography.Governorate",
        "geography.City",
        "specialties.Specialty",
        "billing.Plan",
        "contenttypes.ContentType",
    }
)
# A conversation has no owner of its own: its participants and messages carry the ownership, and
# the conversation itself is deleted only once no participant remains (`_empty_conversations`).
CONTAINER_LABELS = frozenset({"chat.Conversation"})
# Rows a demo account leaves behind through a SET NULL link (they would be orphaned, not deleted):
# (model, field pointing at the account). Only rows of REGISTERED accounts are ever selected.
ACCOUNT_OWNED = (
    ("token_blacklist.OutstandingToken", "user"),  # refresh-token bookkeeping of a demo login
    ("audit.AuditEvent", "actor"),  # audit entries written while acting as a demo account
)
MAX_PASSES = 60


class ClearRefused(Exception):
    """Ownership could not be proven; nothing was deleted."""


@dataclass
class Plan:
    registered: Counter = field(default_factory=Counter)  # label -> registered rows found
    internal: Counter = field(default_factory=Counter)  # label -> unregistered demo-internal rows
    links: Counter = field(default_factory=Counter)  # auto-created many-to-many link rows
    stale_registry_rows: int = 0
    deleted: int = 0
    dry_run: bool = False


def _registered() -> dict[str, set[str]]:
    by_label: dict[str, set[str]] = defaultdict(set)
    for label, pk in DemoRecord.objects.values_list("model_label", "object_pk").iterator():
        by_label[label].add(pk)
    return by_label


def _is_internal(instance, allowed: set[tuple[str, str]]) -> bool:
    """True if every reference of `instance` to a non-reference model is to an allowed row."""
    for fld in instance._meta.concrete_fields:
        if not (fld.is_relation and (fld.many_to_one or fld.one_to_one)):
            continue
        value = getattr(instance, fld.attname)
        if value is None:
            continue
        label = fld.related_model._meta.label
        if label in REFERENCE_LABELS or label in CONTAINER_LABELS or (label, str(value)) in allowed:
            continue
        return False
    return True


def _describe(instance) -> str:
    return f"{instance._meta.label}:{instance.pk}"


def _victims(collector: Collector) -> list:
    out: list = []
    for instances in collector.data.values():
        out.extend(instances)
    for qs in collector.fast_deletes:
        out.extend(list(qs))
    return out


def _empty_conversations(collector: Collector) -> list:
    """A chat conversation has no foreign key to its reservation or account; once all its
    participants are being deleted the empty conversation goes too (never one that keeps a
    participant who is not part of this deletion)."""
    from apps.chat.models import Conversation, ConversationParticipant

    participants = [v for v in _victims(collector) if isinstance(v, ConversationParticipant)]
    if not participants:
        return []
    doomed = {p.pk for p in participants}
    out = []
    for conversation in Conversation.objects.filter(
        pk__in={p.conversation_id for p in participants}
    ):
        keeps = ConversationParticipant.objects.filter(conversation=conversation).exclude(
            pk__in=doomed
        )
        if not keeps.exists():
            out.append(conversation)
    return out


def _check_layer(collector: Collector, allowed, registered_ids, plan: Plan) -> None:
    victims = _victims(collector)
    allowed |= {(v._meta.label, str(v.pk)) for v in victims}
    offenders = []
    for victim in victims:
        label = victim._meta.label
        ident = (label, str(victim.pk))
        if victim._meta.auto_created:  # many-to-many link row: vanishes with its owner
            plan.links[label] += 1
        elif ident in registered_ids:
            continue
        elif _is_internal(victim, allowed):
            plan.internal[label] += 1
        else:
            offenders.append(victim)
    for lists in collector.field_updates.values():
        for objs in lists:
            for obj in objs:
                if (obj._meta.label, str(obj.pk)) not in allowed and not _is_internal(obj, allowed):
                    offenders.append(obj)
    if offenders:
        raise ClearRefused(
            "the deletion would also change or remove rows that are not demo data: "
            + ", ".join(sorted({_describe(o) for o in offenders})[:10])
            + (" ..." if len(offenders) > 10 else "")
        )


def _adopt_blockers(blockers, pending, allowed, plan: Plan) -> bool:
    """Rows that PROTECT demo rows must themselves be demo-internal; queue them for deletion."""
    candidates = allowed | {(b._meta.label, str(b.pk)) for b in blockers}
    offenders = [b for b in blockers if not _is_internal(b, candidates)]
    if offenders:
        raise ClearRefused(
            "a row that is not demo data references demo data: "
            + ", ".join(sorted({_describe(o) for o in offenders})[:10])
        )
    grew = False
    for blocker in blockers:
        bucket = pending.setdefault(blocker._meta.model, [])
        if any(b.pk == blocker.pk for b in bucket):
            continue
        bucket.append(blocker)
        allowed.add((blocker._meta.label, str(blocker.pk)))
        plan.internal[blocker._meta.label] += 1
        grew = True
    return grew


def execute(*, dry_run: bool = False, using: str = "default") -> Plan:
    """Verify and delete in ONE transaction. `dry_run` does everything, then rolls back."""
    plan = Plan(dry_run=dry_run)
    with transaction.atomic(using=using):
        registered = _registered()
        registered_ids = {(label, pk) for label, pks in registered.items() for pk in pks}
        allowed = set(registered_ids)
        pending: dict = {}
        for label, pks in registered.items():
            model = apps.get_model(label)
            found = list(model._base_manager.using(using).filter(pk__in=pks))
            plan.stale_registry_rows += len(pks) - len(found)
            if found:
                pending[model] = found
                plan.registered[label] = len(found)

        account_pks = registered.get("accounts.Account", set())
        for label, fld in ACCOUNT_OWNED:
            model = apps.get_model(label)
            extra = [
                row
                for row in model._base_manager.using(using).filter(**{f"{fld}__in": account_pks})
                if (label, str(row.pk)) not in registered_ids
            ]
            if extra:
                pending.setdefault(model, []).extend(extra)
                allowed |= {(label, str(row.pk)) for row in extra}
                plan.internal[label] += len(extra)

        for _ in range(MAX_PASSES):
            if not pending:
                break
            progressed = False
            for model in list(pending):
                # rows may already have gone with an earlier layer's cascade
                batch = list(
                    model._base_manager.using(using).filter(pk__in=[o.pk for o in pending[model]])
                )
                if not batch:
                    del pending[model]
                    progressed = True
                    continue
                collector = Collector(using=using)
                try:
                    collector.collect(batch)
                except (ProtectedError, RestrictedError) as exc:
                    blockers = list(
                        getattr(exc, "protected_objects", None)
                        or getattr(exc, "restricted_objects", ())
                    )
                    if _adopt_blockers(blockers, pending, allowed, plan):
                        progressed = True
                    continue  # retry this model once its protectors are gone
                for conversation in _empty_conversations(collector):
                    bucket = pending.setdefault(type(conversation), [])
                    if all(b.pk != conversation.pk for b in bucket):
                        bucket.append(conversation)
                        allowed.add((conversation._meta.label, str(conversation.pk)))
                        if (conversation._meta.label, str(conversation.pk)) not in registered_ids:
                            plan.internal[conversation._meta.label] += 1
                _check_layer(collector, allowed, registered_ids, plan)
                deleted, _per_model = collector.delete()
                plan.deleted += deleted
                pending[model] = []
                del pending[model]
                progressed = True
            if not progressed:
                raise ClearRefused("deletion is blocked by rows that cannot be classified")
        else:
            raise ClearRefused("could not reach a stable deletion order")

        DemoRecord.objects.all().delete()
        if dry_run:
            transaction.set_rollback(True)
    return plan
