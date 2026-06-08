# Flutter Frontend

Music recommendation frontend for the SW Maestro AI study project.

## Setup

```bash
flutter pub get
flutter run
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
