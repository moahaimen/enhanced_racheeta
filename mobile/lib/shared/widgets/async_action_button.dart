import 'package:flutter/material.dart';

/// The mobile counterpart of the web `ApiActionButton`: the project's mandatory loading rule.
///
/// While [onPressed] runs the button shows a circular progress indicator (and [pendingLabel]),
/// is disabled, and ignores further taps, so a backend action can never be submitted twice.
/// The action owns its error handling; the button always returns to idle afterwards.
enum AsyncButtonStyle { primary, secondary }

class AsyncActionButton extends StatefulWidget {
  const AsyncActionButton({
    required this.label,
    required this.onPressed,
    this.pendingLabel,
    this.icon,
    this.confirm,
    this.style = AsyncButtonStyle.primary,
    super.key,
  });

  final String label;
  final String? pendingLabel;
  final IconData? icon;
  final AsyncButtonStyle style;

  /// Optional gate asked BEFORE the action starts (e.g. a confirmation dialog). No progress is
  /// shown while the user decides; returning false abandons the action.
  final Future<bool> Function()? confirm;

  /// Null disables the button (e.g. an incomplete form).
  final Future<void> Function()? onPressed;

  @override
  State<AsyncActionButton> createState() => _AsyncActionButtonState();
}

class _AsyncActionButtonState extends State<AsyncActionButton> {
  bool _pending = false;
  bool _asking = false;

  Future<void> _run() async {
    if (_pending || _asking) return; // duplicate tap
    final action = widget.onPressed;
    if (action == null) return;
    final gate = widget.confirm;
    if (gate != null) {
      _asking = true;
      final approved = await gate();
      _asking = false;
      if (!approved || !mounted) return;
    }
    setState(() => _pending = true);
    try {
      await action();
    } finally {
      if (mounted) setState(() => _pending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final foreground = widget.style == AsyncButtonStyle.primary
        ? Theme.of(context).colorScheme.onPrimary
        : Theme.of(context).colorScheme.primary;
    final leading = _pending
        ? SizedBox.square(
            dimension: 20,
            child: CircularProgressIndicator(
              strokeWidth: 2.5,
              color: foreground,
            ),
          )
        : (widget.icon != null ? Icon(widget.icon, size: 20) : null);
    final text = _pending
        ? (widget.pendingLabel ?? widget.label)
        : widget.label;
    final child = Row(
      mainAxisSize: MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (leading != null) ...[leading, const SizedBox(width: 8)],
        Flexible(child: Text(text, textAlign: TextAlign.center)),
      ],
    );
    // `onPressed: null` is what disables a Material button; keep it null while pending.
    final handler = (_pending || widget.onPressed == null) ? null : _run;
    final button = widget.style == AsyncButtonStyle.primary
        ? FilledButton(onPressed: handler, child: child)
        : OutlinedButton(onPressed: handler, child: child);
    return Semantics(
      button: true,
      enabled: handler != null,
      // Tells screen readers a request is in progress.
      liveRegion: _pending,
      child: button,
    );
  }
}

/// Primary (filled) action.
class PrimaryButton extends AsyncActionButton {
  const PrimaryButton({
    required super.label,
    required super.onPressed,
    super.pendingLabel,
    super.icon,
    super.confirm,
    super.key,
  }) : super(style: AsyncButtonStyle.primary);
}

/// Secondary (outlined) action.
class SecondaryButton extends AsyncActionButton {
  const SecondaryButton({
    required super.label,
    required super.onPressed,
    super.pendingLabel,
    super.icon,
    super.confirm,
    super.key,
  }) : super(style: AsyncButtonStyle.secondary);
}
