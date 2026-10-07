import 'package:flutter/material.dart';

/// Read-only text the user can long-press to copy (a phone number, a description).
///
/// `SelectableText` is exposed to screen readers as a read-only *text field* (and fails the 48 dp
/// tap-target guideline); a [Text] inside a [SelectionArea] keeps the same copy behaviour with
/// ordinary text semantics.
class SelectableValue extends StatelessWidget {
  const SelectableValue(this.text, {this.style, super.key});
  final String text;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) =>
      SelectionArea(child: Text(text, style: style));
}
