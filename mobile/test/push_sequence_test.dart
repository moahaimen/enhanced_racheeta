import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/core/storage/preferences_store.dart';
import 'package:racheeta_mobile/core/time/time_providers.dart';
import 'package:racheeta_mobile/features/auth/application/providers.dart';
import 'package:racheeta_mobile/features/push/push_sequence.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// A store that records the order of reads/writes, to prove "persisted before it is used".
class _SpyStore extends MemoryPreferencesStore {
  _SpyStore();
  final List<String> events = <String>[];
  Object? failNextWrite;

  @override
  int? readPushOwnershipSeq() {
    events.add('read');
    return super.readPushOwnershipSeq();
  }

  @override
  Future<void> writePushOwnershipSeq(int value) async {
    final failure = failNextWrite;
    if (failure != null) {
      failNextWrite = null;
      throw failure;
    }
    events.add('write:$value');
    await super.writePushOwnershipSeq(value);
  }
}

DateTime _at(int micros) =>
    DateTime.fromMicrosecondsSinceEpoch(micros, isUtc: true);

void main() {
  group('PushOwnershipSequence', () {
    test('strictly increases, even when the clock does not move', () async {
      final store = MemoryPreferencesStore();
      final seq = PushOwnershipSequence(store: store, clock: () => _at(1000));
      final values = [for (var i = 0; i < 20; i++) await seq.next()];
      for (var i = 1; i < values.length; i++) {
        expect(values[i], greaterThan(values[i - 1]));
      }
      expect(values.first, 1000);
      expect(values.last, 1019);
    });

    test(
      'the wall clock is an input: a later clock gives a larger value',
      () async {
        var micros = 1000;
        final seq = PushOwnershipSequence(
          store: MemoryPreferencesStore(),
          clock: () => _at(micros),
        );
        expect(await seq.next(), 1000);
        micros = 5000;
        expect(await seq.next(), 5000);
        expect(await seq.next(), 5001);
      },
    );

    test(
      'a wall-clock rollback never produces a smaller or equal value',
      () async {
        var micros = 9000000;
        final seq = PushOwnershipSequence(
          store: MemoryPreferencesStore(),
          clock: () => _at(micros),
        );
        final before = await seq.next();
        micros = 10; // the user (or NTP) moved the clock far back
        final after = await seq.next();
        micros = 0;
        final again = await seq.next();
        expect(after, greaterThan(before));
        expect(again, greaterThan(after));
      },
    );

    test('it is persisted BEFORE it is returned for use', () async {
      final store = _SpyStore();
      final seq = PushOwnershipSequence(store: store, clock: () => _at(500));
      final value = await seq.next();
      expect(store.readPushOwnershipSeq(), value);
      expect(store.events.first, 'read');
      expect(store.events[1], 'write:$value');
    });

    test('app restart: a new allocator over the same store continues, never restarts', () async {
      final store = MemoryPreferencesStore();
      final first = PushOwnershipSequence(store: store, clock: () => _at(100));
      await first.next();
      final last = await first.next();
      // "restart": a brand-new object and a clock that is now far in the past
      final second = PushOwnershipSequence(store: store, clock: () => _at(1));
      expect(await second.next(), last + 1);
    });

    test('overlapping calls are serialised: every caller gets a distinct, increasing value', () async {
      final seq = PushOwnershipSequence(
        store: MemoryPreferencesStore(),
        clock: () => _at(42),
      );
      final values = await Future.wait([
        for (var i = 0; i < 50; i++) seq.next(),
      ]);
      expect(values.toSet(), hasLength(50));
      for (var i = 1; i < values.length; i++) {
        expect(
          values[i],
          greaterThan(values[i - 1]),
          reason: 'issued in call order',
        );
      }
    });

    test('a failed write is reported, consumes nothing and does not break later calls', () async {
      final store = _SpyStore();
      final seq = PushOwnershipSequence(store: store, clock: () => _at(100));
      final first = await seq.next();
      store.failNextWrite = StateError('disk full');
      await expectLater(seq.next(), throwsStateError);
      final next = await seq.next();
      expect(next, greaterThan(first));
    });

    test('values near the server\'s 64-bit limit are kept exactly', () async {
      final big = 4611686018427387904; // 2^62
      final store = MemoryPreferencesStore(null, big);
      final seq = PushOwnershipSequence(store: store, clock: () => _at(1));
      expect(await seq.next(), big + 1);
    });
  });

  group('persistence and wiring', () {
    test('SharedPreferences stores the counter as an integer and survives a reload', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final store = SharedPreferencesStore(prefs);
      expect(store.readPushOwnershipSeq(), isNull);
      final value = await PushOwnershipSequence(
        store: store,
        clock: () => _at(1700000000000000),
      ).next();
      // a new store object over the same backing preferences ("next launch")
      final again = SharedPreferencesStore(
        await SharedPreferences.getInstance(),
      );
      expect(again.readPushOwnershipSeq(), value);
      expect(
        await PushOwnershipSequence(store: again, clock: () => _at(1)).next(),
        value + 1,
      );
    });

    test(
      'the counter is independent of the language preference and of sessions',
      () async {
        final store = MemoryPreferencesStore('en');
        await store.writePushOwnershipSeq(77);
        await store.writeLanguageCode('ar');
        expect(store.readPushOwnershipSeq(), 77);
      },
    );

    test('provider recreation (a new container over the same store) keeps counting', () async {
      final store = MemoryPreferencesStore();
      ProviderContainer container() => ProviderContainer(
        overrides: [
          preferencesStoreProvider.overrideWithValue(store),
          nowProvider.overrideWithValue(() => _at(1000)),
        ],
      );
      final first = container();
      final a = await first.read(pushOwnershipSequenceProvider).next();
      final b = await first.read(pushOwnershipSequenceProvider).next();
      first.dispose();
      final second = container();
      addTearDown(second.dispose);
      final c = await second.read(pushOwnershipSequenceProvider).next();
      expect([a, b, c], [1000, 1001, 1002]);
    });
  });
}
