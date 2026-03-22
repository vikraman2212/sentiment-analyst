import 'package:flutter/material.dart';
import '../core/config.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _controller = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _saved = false;

  @override
  void initState() {
    super.initState();
    getBaseUrl().then((url) => setState(() => _controller.text = url));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  String? _validateUrl(String? value) {
    final trimmed = value?.trim() ?? '';
    if (trimmed.isEmpty) return 'URL is required';
    final uri = Uri.tryParse(trimmed);
    if (uri == null || !uri.hasScheme || !uri.hasAuthority) {
      return 'Enter a valid URL (e.g. http://192.168.1.50:8000)';
    }
    if (uri.scheme != 'http' && uri.scheme != 'https') {
      return 'URL must start with http:// or https://';
    }
    return null;
  }

  Future<void> _save() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final url = _controller.text.trim();
    await setBaseUrl(url);
    if (mounted) setState(() => _saved = true);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('API Base URL', style: theme.textTheme.titleSmall),
              const SizedBox(height: 8),
              TextFormField(
                controller: _controller,
                decoration: const InputDecoration(
                  hintText: 'http://192.168.x.x:8000',
                  border: OutlineInputBorder(),
                ),
                keyboardType: TextInputType.url,
                autocorrect: false,
                validator: _validateUrl,
                onChanged: (_) => setState(() => _saved = false),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _save,
                child: const Text('Save'),
              ),
              if (_saved)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    'Saved',
                    style: TextStyle(color: theme.colorScheme.primary),
                  ),
                ),
              const SizedBox(height: 32),
              _UrlGuide(),
            ],
          ),
        ),
      ),
    );
  }
}

class _UrlGuide extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: EdgeInsets.zero,
      color: theme.colorScheme.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Which URL should I use?',
              style: theme.textTheme.titleSmall
                  ?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            _GuideRow(
              label: 'iOS Simulator',
              value: 'http://localhost:8000',
              icon: Icons.phone_iphone,
            ),
            _GuideRow(
              label: 'Android Emulator',
              value: 'http://10.0.2.2:8000',
              icon: Icons.android,
            ),
            _GuideRow(
              label: 'Physical Device (Wi-Fi)',
              value: 'http://192.168.x.x:8000',
              icon: Icons.wifi,
            ),
            const SizedBox(height: 8),
            Text(
              'Replace 192.168.x.x with your machine\'s local IPv4 address '
              '(found via System Settings → Wi-Fi → Details, or `ipconfig getifaddr en0` in Terminal).',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ],
        ),
      ),
    );
  }
}

class _GuideRow extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;

  const _GuideRow({
    required this.label,
    required this.value,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Icon(icon, size: 18, color: theme.colorScheme.primary),
          const SizedBox(width: 8),
          Expanded(
            child: RichText(
              text: TextSpan(
                style: theme.textTheme.bodySmall,
                children: [
                  TextSpan(
                    text: '$label: ',
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  TextSpan(text: value),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
