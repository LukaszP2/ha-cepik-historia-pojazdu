# CEPiK Historia Pojazdu – Home Assistant Custom Component

[![GitHub Release](https://img.shields.io/github/v/release/LukaszP2/ha-cepik-historia-pojazdu?style=flat-square)](https://github.com/LukaszP2/ha-cepik-historia-pojazdu/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)


[![Otwórz repozytorium w HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=LukaszP2&repository=ha-cepik-historia-pojazdu&category=integration)
[![Dodaj integrację do Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=cepik_historia_pojazdu)

*(🇬🇧 English description below)*

---

## 🇵🇱 Opis

Integracja Home Assistant z polskim rejestrem CEPiK (Centralna Ewidencja Pojazdów i Kierowców) oraz usługą historiapojazdu.gov.pl.

### Główne funkcje
- Ważność badania technicznego (przeglądu rejestracyjnego)
- Status i ważność ubezpieczenia OC
- Status kradzieży pojazdu w bazach CEPiK
- Ostatni odnotowany przebieg (odczyt licznika)
- Podstawowe dane techniczne pojazdu (marka, model, rok produkcji)

### Instalacja przez HACS (Niestandardowe repozytorium)

### 🚀 Szybka instalacja (1 kliknięcie przez My Home Assistant)

[![Otwórz repozytorium w HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=LukaszP2&repository=ha-cepik-historia-pojazdu&category=integration)

Po zainstalowaniu i ponownym uruchomieniu Home Assistant, kliknij poniższy przycisk, aby skonfigurować integrację:

[![Dodaj integrację do Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=cepik_historia_pojazdu)



1. Upewnij się, że masz zainstalowany **HACS** w Home Assistant.
2. W HACS przejdź do: **Integracje** -> menu w prawym górnym rogu (trzy kropki) -> **Niestandardowe repozytoria** (*Custom repositories*).
3. W polu **Repozytorium** wklej adres:
   ```text
   https://github.com/LukaszP2/ha-cepik-historia-pojazdu
   ```
4. W polu **Kategoria** wybierz: **Integracja** (*Integration*).
5. Kliknij **Dodaj**, a następnie wyszukaj **CEPiK Historia Pojazdu** i kliknij **Pobierz**.
6. Uruchom ponownie Home Assistant.

### Konfiguracja

1. W Home Assistant przejdź do: **Ustawienia** -> **Urządzenia oraz usługi** -> **Dodaj integrację**.
2. Wyszukaj **CEPiK Historia Pojazdu**.
3. Postępuj zgodnie z instrukcjami na ekranie.

---

## 🇬🇧 Description

Home Assistant integration for the Polish CEPiK vehicle registry (historiapojazdu.gov.pl).

### Installation via HACS (Custom Repository)

1. Open **HACS** in Home Assistant.
2. Navigate to **Integrations** -> top right menu (three dots) -> **Custom repositories**.
3. Enter repository URL:
   ```text
   https://github.com/LukaszP2/ha-cepik-historia-pojazdu
   ```
4. Category: **Integration**.
5. Click **Add**, find **CEPiK Historia Pojazdu**, and install.
6. Restart Home Assistant.

---

## Licencja / License

Projekt objęty licencją [MIT](LICENSE).