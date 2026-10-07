import 'dart:async';

import 'package:dio/dio.dart' show ResponseBody;
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/features/auth/application/providers.dart';
import 'package:racheeta_mobile/features/push/push_registration.dart';
import 'package:racheeta_mobile/features/push/push_timing.dart';

import 'support/comms_support.dart';
import 'support/fake_backend.dart';

/// Server-side ownership simulation for the FCM token, implementing the backend's ordering
/// protocol (`backend/apps/notifications/push_service.py`).
///
/// The "server" owns ONE token row `(owner, active, seq)`. A request is applied at the moment its
/// handler is released (its arrival/commit), the account is taken from the bearer token, and the
/// decision is made against the stored sequence under the (implicit) row lock:
///
/// * stored seq null → applied; stored seq S → applied only if the request's seq > S;
/// * an older/equal/missing seq changes nothing (register answers 409 `stale_ownership`, an exact
///   replay by the active owner is 200, unregister answers 204);
/// * an unregister for an unknown token leaves an inactive ordering marker.
///
/// The assertions are about who OWNS the token at the end, never about client-side state.
const _register = '/api/v1/notifications/push-devices/';
const _unregister = '/api/v1/notifications/push-devices/unregister/';
const _login = '/api/v1/auth/login';
const _logout = '/api/v1/auth/logout';

class TokenServer {
  /// bearer → logical account
  final Map<String, String> accountOf = {'Bearer aA': 'A', 'Bearer aB': 'B'};

  String? _owner;
  bool _active = false;
  int? _seq;

  /// The account that currently receives pushes through the token (null: nobody).
  String? get owner => _active ? _owner : null;
  int? get storedSeq => _seq;

  final List<String> log = <String>[];

  /// Every sequence the server received, in arrival order, per endpoint.
  final List<int> registerSeqs = <int>[];
  final List<int> unregisterSeqs = <int>[];
  int registerCalls = 0;
  int unregisterCalls = 0;

  /// register call number (1-based) → gate holding its arrival at the server.
  final Map<int, Completer<void>> registerGates = {};

  /// register call number → the client sees a transport error but the request still reaches the
  /// server later, when the completer is completed (a request lingering in the network).
  final Map<int, Completer<void>> stragglers = {};

  ResponseBody _device() => FakeBackend.json(200, {
    'id': 'f1',
    'platform': 'ANDROID',
    'is_active': true,
    'last_registered_at': '2026-10-03T08:00:00Z',
  });

  ResponseBody _stale() => FakeBackend.json(409, {
    'error': {
      'code': 'stale_ownership',
      'message': 'This registration was superseded by a newer one.',
    },
  });

  /// Returns true when the register was applied.
  bool _applyRegister(String who, int? seq, int call, {required bool late}) {
    final tag = '$who#$call${late ? '(late)' : ''}';
    final stored = _seq;
    final accepts = stored == null || (seq != null && seq > stored);
    if (!accepts) {
      final replay = seq != null && seq == stored && _owner == who && _active;
      log.add('${replay ? 'replay' : 'rejected:stale'}:register:$tag');
      return replay;
    }
    _owner = who;
    _active = true;
    if (seq != null) _seq = seq;
    log.add('commit:register:$tag');
    return true;
  }

  Future<ResponseBody> onRegister(SeenRequest r) async {
    final call = ++registerCalls;
    final who = accountOf[r.authorization] ?? '?';
    final seq = (r.body! as Map)['ownership_seq'] as int?;
    if (seq != null) registerSeqs.add(seq);
    final straggler = stragglers[call];
    if (straggler != null) {
      unawaited(
        straggler.future.then(
          (_) => _applyRegister(who, seq, call, late: true),
        ),
      );
      return FakeBackend.networkDown(r);
    }
    final gate = registerGates[call];
    if (gate != null) await gate.future;
    return _applyRegister(who, seq, call, late: false) ? _device() : _stale();
  }

  Future<ResponseBody> onUnregister(SeenRequest r) async {
    unregisterCalls++;
    final who = accountOf[r.authorization] ?? '?';
    final seq = (r.body! as Map)['ownership_seq'] as int?;
    if (seq != null) unregisterSeqs.add(seq);
    final stored = _seq;
    if (_owner == null) {
      if (seq != null) {
        _owner = who; // inactive ordering marker
        _active = false;
        _seq = seq;
        log.add('marker:unregister:$who');
      }
    } else if (_owner == who &&
        (stored == null || (seq != null && seq > stored))) {
      _active = false;
      if (seq != null) _seq = seq;
      log.add('commit:unregister:$who');
    } else {
      log.add('noop:unregister:$who');
    }
    return FakeBackend.noContent();
  }
}

Future<void> _settle([int ms = 80]) =>
    Future<void>.delayed(Duration(milliseconds: ms));

class Rig {
  Rig(this.h, this.server, this.source);
  final Harness h;
  final TokenServer server;
  final FakePushSource source;

  dynamic get session => h.container.read(sessionControllerProvider.notifier);

  Future<void> login(String who) async {
    await session.login(email: '$who@t.io', password: 'pw');
    await _settle();
  }
}

Future<Rig> _rig({
  Duration hookTimeout = const Duration(milliseconds: 150),
}) async {
  final server = TokenServer();
  final source = FakePushSource();
  final h = Harness(
    storedRefresh: null,
    autoRestore: true,
    extraOverrides: [
      pushSourceProvider.overrideWithValue(source),
      beforeLogoutProvider.overrideWith(
        (ref) =>
            () => ref
                .read(pushRegistrationProvider.notifier)
                .unregisterForLogout(),
      ),
      logoutHookTimeoutProvider.overrideWithValue(hookTimeout),
      // far beyond any test: correctness must come from the server's sequence ordering, never
      // from the delayed repair
      pushRepairDelayProvider.overrideWithValue(const Duration(minutes: 30)),
    ],
  );
  addTearDown(h.dispose);
  h.backend
    ..on('POST', _login, (r) {
      final who = (r.body! as Map)['email'].toString().split('@').first;
      return FakeBackend.json(200, tokens('a$who', 'r$who'));
    })
    ..on('GET', '/api/v1/me', (r) {
      final who = r.authorization == 'Bearer aA' ? 'A' : 'B';
      return FakeBackend.json(
        200,
        accountJson(
          id: who == 'A'
              ? '11111111-1111-4111-8111-111111111111'
              : '99999999-9999-4999-8999-999999999999',
          name: 'Account $who',
        ),
      );
    })
    ..on('POST', _logout, (_) => FakeBackend.noContent())
    ..on('POST', _register, server.onRegister)
    ..on('POST', _unregister, server.onUnregister);
  h.container.listen(pushRegistrationProvider, (_, _) {});
  await h.container.read(sessionControllerProvider.notifier).restored;
  return Rig(h, server, source);
}

/// No registration by A may commit after B's registration did.
void _expectAOnlyBeforeB(TokenServer server) {
  final log = server.log;
  final lastA = log.lastIndexWhere((e) => e.startsWith('commit:register:A'));
  final firstB = log.indexWhere((e) => e.startsWith('commit:register:B'));
  expect(firstB, isNonNegative, reason: log.join(', '));
  expect(lastA, lessThan(firstB), reason: log.join(', '));
}

void main() {
  group('server-side ownership converges to the current account', () {
    test('baseline: A registers, signs out, B signs in: owner is B', () async {
      final r = await _rig();
      await r.login('A');
      expect(r.server.owner, 'A');
      await r.session.logout();
      await _settle();
      expect(r.server.owner, isNull, reason: 'unregistered before logout');
      await r.login('B');
      expect(r.server.owner, 'B');
    });

    test('A\'s registration is delayed across logout and B\'s sign-in: it completes first, B ends as owner', () async {
      final r = await _rig();
      r.server.registerGates[1] = Completer<void>();
      await r.login('A');
      expect(r.server.registerCalls, 1, reason: 'A\'s request is in flight');
      await r.session
          .logout(); // hook gives up after 150 ms; credentials are cleared
      await r.login('B');
      // B's registration must NOT reach the server while A's is still in flight
      expect(r.server.registerCalls, 1);
      expect(r.server.owner, isNull);
      r.server.registerGates[1]!
          .complete(); // A's request finally reaches the server
      await _settle(200);
      expect(r.server.owner, 'B', reason: r.server.log.join(', '));
      _expectAOnlyBeforeB(r.server);
    });

    test(
      'the opposite order (A commits before B even starts) also ends with B',
      () async {
        final r = await _rig();
        r.server.registerGates[1] = Completer<void>();
        await r.login('A');
        r.server.registerGates[1]!.complete(); // A commits right away
        await _settle();
        expect(r.server.owner, 'A');
        await r.session.logout();
        await r.login('B');
        expect(r.server.owner, 'B');
      },
    );

    test('logout while A\'s registration is in flight: the unregister is ordered after it, stale register completes last, B is the owner', () async {
      final r = await _rig();
      r.server.registerGates[1] = Completer<void>();
      await r.login('A');
      final logout = r.session
          .logout(); // hook queues the unregister behind A's register
      await _settle(60);
      expect(
        r.server.unregisterCalls,
        0,
        reason: 'the unregister must wait for the in-flight register',
      );
      await logout; // bound expired (150 ms): credentials cleared, A's request still pending
      await r.login('B');
      r.server.registerGates[1]!
          .complete(); // the stale register completes at the worst moment
      await _settle(250);
      expect(r.server.owner, 'B', reason: r.server.log.join(', '));
      // A's stale register committed first; B's registration came strictly after it, and A's own
      // unregister (carrying A's bearer) can only deactivate A's registration, never B's.
      _expectAOnlyBeforeB(r.server);
      expect(r.server.unregisterCalls, 1);
    });

    test(
      'logout whose bound is long enough: register, then unregister, then B',
      () async {
        final r = await _rig(hookTimeout: const Duration(seconds: 2));
        r.server.registerGates[1] = Completer<void>();
        await r.login('A');
        final logout = r.session.logout();
        await _settle(60);
        r.server.registerGates[1]!.complete();
        await logout;
        await r.login('B');
        expect(r.server.owner, 'B');
        _expectAOnlyBeforeB(r.server);
        expect(r.server.log.first, 'commit:register:A#1');
      },
    );

    test('KEY: a request the client gave up on commits AFTER B registered — the server rejects it as stale and B stays the owner, with no repair involved', () async {
      final r = await _rig();
      r.server.stragglers[1] = Completer<void>();
      await r.login(
        'A',
      ); // A's POST fails on the client; it is still in the network
      await r.session.logout();
      await r.login('B');
      expect(r.server.owner, 'B', reason: 'B registered after A\'s failure');
      r.server.stragglers[1]!
          .complete(); // the old A request finally reaches the server
      await _settle(50);
      // immediately, without waiting for any repair (it is set 30 minutes away):
      expect(r.server.owner, 'B', reason: r.server.log.join(', '));
      expect(r.server.log, contains('rejected:stale:register:A#1(late)'));
      expect(
        r.server.log.where((e) => e.startsWith('commit:register:A')),
        isEmpty,
      );
    });

    test('a lost register of A that lands after A\'s logout cannot resurrect A (and B then registers fine)', () async {
      final r = await _rig();
      r.server.stragglers[1] = Completer<void>();
      await r.login('A');
      await r.session.logout(); // unregister(A) carries a newer sequence
      r.server.stragglers[1]!
          .complete(); // the lost register lands after the unregister
      await _settle(50);
      expect(r.server.owner, isNull, reason: r.server.log.join(', '));
      await r.login('B');
      expect(r.server.owner, 'B');
    });

    test('every ownership request carries a sequence; sequences increase across account switches and logouts', () async {
      final r = await _rig();
      for (final who in ['A', 'B', 'A']) {
        await r.login(who);
        await r.session.logout();
        await _settle();
      }
      final all = [...r.server.registerSeqs, ...r.server.unregisterSeqs]
        ..sort();
      expect(r.server.registerSeqs, hasLength(3));
      expect(r.server.unregisterSeqs, hasLength(3));
      expect(all.toSet(), hasLength(6), reason: 'no value is ever reused');
      // in send order the sequences strictly increase: register, unregister, register, ...
      var previous = 0;
      for (var i = 0; i < 3; i++) {
        expect(r.server.registerSeqs[i], greaterThan(previous));
        previous = r.server.registerSeqs[i];
        expect(r.server.unregisterSeqs[i], greaterThan(previous));
        previous = r.server.unregisterSeqs[i];
      }
    });

    test(
      'repeated sign-ins never leave the token with a previous account',
      () async {
        final r = await _rig();
        for (final who in ['A', 'B', 'A', 'B']) {
          await r.login(who);
          expect(r.server.owner, who);
          await r.session.logout();
          await _settle();
        }
        expect(r.server.owner, isNull);
      },
    );

    test(
      'no overlapping ownership requests: only one is ever in flight',
      () async {
        final r = await _rig();
        var inFlight = 0;
        var maxInFlight = 0;
        r.h.backend.on('POST', _register, (req) async {
          inFlight++;
          if (inFlight > maxInFlight) maxInFlight = inFlight;
          await Future<void>.delayed(const Duration(milliseconds: 40));
          inFlight--;
          return r.server.onRegister(req);
        });
        await r.login('A');
        r.source.refreshes.add('fake-fcm-token-2');
        r.source.refreshes.add('fake-fcm-token-3');
        await r.session.logout();
        await r.login('B');
        await _settle(300);
        expect(maxInFlight, 1);
        expect(r.server.owner, 'B');
      },
    );
  });
}
