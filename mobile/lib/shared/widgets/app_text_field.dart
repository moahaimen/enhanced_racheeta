import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../l10n/generated/app_localizations.dart';

/// Labelled text field with an inline error and, for passwords, a visibility toggle.
/// Presentation only: validation rules belong to the backend, which reports them per field.
class AppTextField extends StatefulWidget {
  const AppTextField({
    required this.controller,
    required this.label,
    this.errorText,
    this.obscure = false,
    this.keyboardType,
    this.textInputAction,
    this.autofillHints,
    this.enabled = true,
    this.onSubmitted,
    this.inputFormatters,
    super.key,
  });

  final TextEditingController controller;
  final String label;
  final String? errorText;
  final bool obscure;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final Iterable<String>? autofillHints;
  final bool enabled;
  final ValueChanged<String>? onSubmitted;
  final List<TextInputFormatter>? inputFormatters;

  @override
  State<AppTextField> createState() => _AppTextFieldState();
}

class _AppTextFieldState extends State<AppTextField> {
  late bool _hidden = widget.obscure;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return TextField(
      controller: widget.controller,
      enabled: widget.enabled,
      obscureText: _hidden,
      keyboardType: widget.keyboardType,
      textInputAction: widget.textInputAction,
      autofillHints: widget.autofillHints,
      onSubmitted: widget.onSubmitted,
      inputFormatters: widget.inputFormatters,
      // Credentials must not be learned by keyboards or suggested back.
      autocorrect:
          !widget.obscure && widget.keyboardType != TextInputType.emailAddress,
      enableSuggestions:
          !widget.obscure && widget.keyboardType != TextInputType.emailAddress,
      decoration: InputDecoration(
        labelText: widget.label,
        errorText: widget.errorText,
        errorMaxLines: 3,
        suffixIcon: widget.obscure
            ? IconButton(
                tooltip: _hidden ? l10n.showPassword : l10n.hidePassword,
                icon: Icon(
                  _hidden
                      ? Icons.visibility_outlined
                      : Icons.visibility_off_outlined,
                ),
                onPressed: () => setState(() => _hidden = !_hidden),
              )
            : null,
      ),
    );
  }
}
