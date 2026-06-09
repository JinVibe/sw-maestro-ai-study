# Flutter Frontend

Music recommendation frontend for the SW Maestro AI study project.

## Setup

```bash
flutter pub get
flutter run
```

Run against a local backend:

```bash
flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:8001
```

For a physical phone on the same Wi-Fi, use the PC's LAN IP instead:

```bash
flutter run -d <device_id> --dart-define=API_BASE_URL=http://192.168.0.48:8001
```

If platform folders are not present yet, generate them inside this directory:

```bash
flutter create . --platforms=android,web
```

## Structure

```text
lib/
|-- app/                  # App shell and routing entry
|-- core/                 # Shared theme/constants
`-- features/
    `-- recommendation/
        |-- data/         # Mock/API data sources
        |-- domain/       # Feature entities
        `-- presentation/ # State, pages, widgets
```
