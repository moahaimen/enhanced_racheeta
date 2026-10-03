import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Standard page frame: safe area, scrolling, a centred column capped at a readable width (so
/// phones and tablets share one layout), and consistent padding.
class AppScaffold extends StatelessWidget {
  const AppScaffold({
    required this.body,
    this.title,
    this.actions,
    this.scrollable = true,
    this.bottomNavigationBar,
    super.key,
  });

  final Widget body;
  final String? title;
  final List<Widget>? actions;
  final bool scrollable;
  final Widget? bottomNavigationBar;

  @override
  Widget build(BuildContext context) {
    final content = Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: RacheetaSpacing.maxContentWidth,
        ),
        child: Padding(
          padding: const EdgeInsets.all(RacheetaSpacing.lg),
          child: body,
        ),
      ),
    );
    return Scaffold(
      appBar: title == null
          ? null
          : AppBar(title: Text(title!), actions: actions),
      bottomNavigationBar: bottomNavigationBar,
      body: SafeArea(
        child: scrollable
            ? LayoutBuilder(
                builder: (context, constraints) => SingleChildScrollView(
                  child: ConstrainedBox(
                    constraints: BoxConstraints(
                      minHeight: constraints.maxHeight,
                    ),
                    child: content,
                  ),
                ),
              )
            : content,
      ),
    );
  }
}
