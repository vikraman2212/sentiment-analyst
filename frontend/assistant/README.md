# Assistant App

Flutter client for the Sentiment Analyst local workflow.

For full-stack local setup, startup order, backend modes, and shared commands, start with the root [README.md](../../README.md).

## App Commands

From the repository root:

```bash
make frontend-install
make frontend-run
make frontend-analyze
make frontend-test
```

From this directory directly:

```bash
flutter pub get
flutter run
flutter analyze
flutter test
```

## Backend Base URL

The app defaults to `http://localhost:8000` via `lib/core/config.dart`.

Use these values depending on where the app runs:

- iOS simulator on the same Mac: `http://localhost:8000`
- Android emulator: `http://10.0.2.2:8000`
- Physical device on local Wi-Fi: `http://<your-mac-ip>:8000`

The app stores the selected base URL in SharedPreferences using the `api_base_url` key.

## Requirements

- Flutter SDK compatible with `pubspec.yaml`
- A running backend at port `8000`
- Local infrastructure and Ollama started as described in the root README
