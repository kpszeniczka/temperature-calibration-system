# System Wzorcowania Czujników Temperatury

## Opis

System umożliwia przeprowadzenie automatycznego procesu wzorcowania czujników temperatury (PT100, termopary typu K, S) z wykorzystaniem:
- **Termometru precyzyjnego Cropico 3001** (protokół SCPI przez RS-232)
- **Pieca kalibracyjnego Pegasus** (protokół Modbus RTU)

Aplikacja realizuje pełny cykl wzorcowania zgodnie z normą ISO/IEC 17025, włącznie z:
- Automatyczną stabilizacją temperatury pieca
- Weryfikacją równowagi termicznej
- Wielokrotnym pomiarem w każdym punkcie kalibracyjnym
- Obliczaniem niepewności pomiarowej według przewodnika GUM
- Klasyfikacją czujników według norm IEC 60751 (PT100) i IEC 60584 (termopary)
- Generowaniem świadectw wzorcowania w formacie PDF

## Architektura systemu

```
┌─────────────────────────────────────────────────────────────┐
│                    Warstwa prezentacji                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │   MainWindow    │  │CalibrationWindow│  │   Dialogs   │  │
│  └────────┬────────┘  └────────┬────────┘  └──────┬──────┘  │
└───────────┼────────────────────┼─────────────────┼──────────┘
            │                    │                 │
┌───────────┼────────────────────┼─────────────────┼──────────┐
│           ▼                    ▼                 ▼          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              CalibrationEngine                       │    │
│  │   - Kontrola procesu wzorcowania                    │    │
│  │   - Zarządzanie sekwencją pomiarową                 │    │
│  │   - Weryfikacja stabilności i równowagi             │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│           ┌─────────────┼─────────────┐                     │
│           ▼             ▼             ▼                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ Statistics  │ │ Uncertainty │ │  Database   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│                    Warstwa logiki                           │
└─────────────────────────────────────────────────────────────┘
            │                              │
┌───────────┼──────────────────────────────┼──────────────────┐
│           ▼                              ▼                  │
│  ┌─────────────────┐            ┌─────────────────┐        │
│  │  CropicoDevice  │            │  PegasusFurnace │        │
│  │     (SCPI)      │            │   (Modbus RTU)  │        │
│  └────────┬────────┘            └────────┬────────┘        │
│           │   Warstwa komunikacji        │                  │
└───────────┼──────────────────────────────┼──────────────────┘
            │                              │
            ▼                              ▼
     ┌─────────────┐              ┌─────────────┐
     │ Cropico 3001│              │Piec Pegasus │
     └─────────────┘              └─────────────┘
```

## Struktura projektu

```
temperature-calibration-system/
├── main.py                 # Punkt wejścia aplikacji
├── config.py               # Konfiguracja systemu
├── devices/                # Sterowniki urządzeń
│   ├── cropico.py          # Obsługa termometru Cropico 3001
│   ├── furnace.py          # Obsługa pieca Pegasus
│   ├── simulators.py       # Symulatory urządzeń
│   └── port_scanner.py     # Skanowanie portów COM
├── calibration/            # Logika wzorcowania
│   ├── engine.py           # Silnik procesu wzorcowania
│   ├── statistics.py       # Obliczenia statystyczne
│   └── uncertainty.py      # Obliczenia niepewności (GUM)
├── data/                   # Zarządzanie danymi
│   ├── database.py         # Baza danych SQLite
│   ├── logger.py           # Logowanie pomiarów
│   └── report_generator.py # Generowanie świadectw PDF
├── gui/                    # Interfejs graficzny
│   ├── main_window.py      # Okno główne
│   ├── calibration_window.py # Okno procesu wzorcowania
│   └── dialogs.py          # Okna dialogowe
├── api/                    # API zdalnego dostępu
│   └── remote_api.py       # REST API + WebSocket
├── requirements.txt        # Zależności Python
└── README.md
```

## Wymagania

- Python 3.8+
- System operacyjny: Windows 10/11 (wymagane porty COM)

## Instalacja

1. Sklonuj repozytorium:
```bash
git clone https://github.com/[username]/temperature-calibration-system.git
cd temperature-calibration-system
```

2. Utwórz środowisko wirtualne:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

3. Zainstaluj zależności:
```bash
pip install -r requirements.txt
```

## Uruchomienie

### Tryb z urządzeniami fizycznymi
```bash
python main.py
```

### Tryb symulacji (bez sprzętu)
Ustaw w pliku `config.py`:
```python
USE_SIMULATORS = True
```

## Funkcjonalności

### Obsługiwane typy czujników
| Typ | Norma | Klasy dokładności |
|-----|-------|-------------------|
| PT100 | IEC 60751 | AA, A, B, C |
| Termopara K | IEC 60584 | Klasa 1, 2 |
| Termopara S | IEC 60584 | Klasa 1, 2 |

### Kanały pomiarowe
- **A0** - kanał referencyjny (termometr wzorcowy)
- **B0-B4** - kanały dla czujników wzorcowanych

### API zdalnego dostępu
System udostępnia REST API oraz WebSocket do zdalnego monitorowania:
- `GET /api/status` - status systemu
- `POST /api/calibration/start` - rozpoczęcie wzorcowania
- `WS /ws/realtime` - dane w czasie rzeczywistym

## Obliczanie niepewności

System implementuje pełny budżet niepewności zgodnie z GUM:

**Składowe niepewności typu B:**
- Niepewność termometru referencyjnego: 0.01°C
- Rozdzielczość przyrządu: 0.001°C
- Stabilność temperatury pieca: 0.02°C
- Jednorodność pola temperatury: 0.05°C
- Dryft międzywzorcowy: 0.01°C

**Niepewność rozszerzona:** U = k · u_c (k=2, poziom ufności ~95%)

## Technologie

- **Python 3.8+** - język programowania
- **PyQt5** - interfejs graficzny
- **pyserial** - komunikacja szeregowa
- **pymodbus** - protokół Modbus RTU
- **NumPy** - obliczenia numeryczne
- **SQLite** - baza danych
- **ReportLab** - generowanie PDF
- **FastAPI** - REST API
- **Matplotlib** - wizualizacja danych