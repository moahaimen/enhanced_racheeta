import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/api/error_messages.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/app_text_field.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../application/providers.dart';
import '../application/session_core.dart';
import '../application/session_state.dart';
import 'language_switcher.dart';

/// Email + password sign-in against `POST /api/v1/auth/login`. Presence checks only: password
/// rules and credential validation belong to the backend, whose per-field messages are shown.
class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  String? _emailError;
  String? _passwordError;
  String? _formError;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final l10n = AppLocalizations.of(context);
    setState(() {
      _emailError = _email.text.trim().isEmpty ? l10n.fieldRequired : null;
      _passwordError = _password.text.isEmpty ? l10n.fieldRequired : null;
      _formError = null;
    });
    if (_emailError != null || _passwordError != null) return;

    try {
      await ref
          .read(sessionControllerProvider.notifier)
          .login(email: _email.text, password: _password.text);
      // Success: the session state changes and the router moves to the authenticated shell.
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _emailError = error.fieldError('email');
        _passwordError = error.fieldError('password');
        _formError = (_emailError == null && _passwordError == null)
            ? apiErrorMessage(l10n, error)
            : null;
      });
    } on StaleSessionException {
      // Superseded by another operation; nothing to show.
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final session = ref.watch(sessionControllerProvider);
    final expired =
        session is SessionAnonymous &&
        session.endedBy == SessionEndReason.expired;

    return AppScaffold(
      title: l10n.appName,
      actions: const [LanguageSwitcher()],
      body: AutofillGroup(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SizedBox(height: RacheetaSpacing.xl),
            Semantics(
              header: true,
              child: Text(
                l10n.loginTitle,
                style: theme.textTheme.headlineSmall,
              ),
            ),
            const SizedBox(height: RacheetaSpacing.sm),
            Text(l10n.loginIntro, style: theme.textTheme.bodyMedium),
            const SizedBox(height: RacheetaSpacing.xl),
            if (expired) ...[
              _Banner(
                message: l10n.sessionExpired,
                color: theme.colorScheme.primaryContainer,
              ),
              const SizedBox(height: RacheetaSpacing.lg),
            ],
            if (_formError != null) ...[
              Semantics(
                liveRegion: true,
                child: _Banner(
                  message: _formError!,
                  color: theme.colorScheme.errorContainer,
                ),
              ),
              const SizedBox(height: RacheetaSpacing.lg),
            ],
            AppTextField(
              controller: _email,
              label: l10n.emailLabel,
              errorText: _emailError,
              keyboardType: TextInputType.emailAddress,
              textInputAction: TextInputAction.next,
              autofillHints: const [
                AutofillHints.username,
                AutofillHints.email,
              ],
              inputFormatters: [
                FilteringTextInputFormatter.deny(RegExp(r'\s')),
              ],
            ),
            const SizedBox(height: RacheetaSpacing.lg),
            AppTextField(
              controller: _password,
              label: l10n.passwordLabel,
              errorText: _passwordError,
              obscure: true,
              textInputAction: TextInputAction.done,
              autofillHints: const [AutofillHints.password],
              onSubmitted: (_) => _submit(),
            ),
            const SizedBox(height: RacheetaSpacing.xl),
            PrimaryButton(
              label: l10n.loginButton,
              pendingLabel: l10n.loggingIn,
              onPressed: _submit,
            ),
          ],
        ),
      ),
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner({required this.message, required this.color});
  final String message;
  final Color color;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      color: color,
      borderRadius: BorderRadius.circular(12),
    ),
    child: Padding(
      padding: const EdgeInsets.all(RacheetaSpacing.md),
      child: Text(message),
    ),
  );
}
