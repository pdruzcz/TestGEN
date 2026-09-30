import 'package:flutter/material.dart';

/// Story 6.12 (AC6) — komunikat braku połączenia z serwerem.
class OfflineMessage extends StatelessWidget {
  const OfflineMessage({super.key, required this.onRetry});

  /// Akcja przycisku "Ponów" — przeładowanie WebView.
  final VoidCallback onRetry;

  static const String message =
      'Brak połączenia z serwerem. '
      'Sprawdź połączenie internetowe i spróbuj ponownie.';

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: Theme.of(context).colorScheme.surface,
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off, size: 64, color: Colors.grey),
              const SizedBox(height: 16),
              Text(
                message,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text('Ponów'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
