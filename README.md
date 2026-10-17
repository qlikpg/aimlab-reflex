# AimLab IRL — MVP na Linuxa

## Panel bez terminala — 17 października 2026

W menu aplikacji Linux Mint wyszukaj **AimLab IRL**. Panel korzysta z systemowego GTK i uruchamia programy kamery oraz treningu w istniejącym środowisku `.venv`. Alternatywnie: `bash start_panel.sh` w folderze projektu.

1. Podłącz kamerę Trust i rzutnik HDMI. Kliknij **Odśwież urządzenia**, wybierz kamerę i ekran projekcji. Panel nie wybiera automatycznie kamery laptopa w zastępstwie odłączonej kamery Trust.
2. **Kalibracja** uruchamia kamerę i białą planszę. W podglądzie kamery wskaż cztery zewnętrzne rogi ramki: lewy górny, prawy górny, prawy dolny, lewy dolny. Nie trzeba wciskać C. Jeśli kamera już działa, najpierw kliknij **STOP**.
3. Poczekaj na status kamery **gotowa**, następnie kliknij **Start treningu**. Plansza zostanie zamknięta, a sesja uruchomi się na wybranym ekranie.
4. **STOP** zamyka trening, planszę oraz kamerę. Zamknięcie panelu również zatrzymuje jego procesy.

**Podgląd i maska** pozwala sprawdzić detekcję. Progi panelu domyślnie wynoszą 180/45 dla zielonego lasera. Suwaki w masce działają na żywo; kliknięcie **Zapisz ustawienia** podczas działania kamery zachowuje aktualne progi z maski w `aimlab_settings.json`. Przy wyłączonej kamerze można zmienić wartości w panelu i je zapisać. Parametry kamery i ekranu są blokowane podczas jej pracy.

Panel nie przesuwa okien ani nie zmienia ustawień ekranów systemu; korzysta z wykrytej geometrii. Dla różnych rozdzielczości dobierz promień celu. Kamera niegotowa, brak kalibracji lub zbyt duży cel blokują uruchomienie sesji. Log błędów: `aimlab_panel.log`.

Panel wymaga pakietów `python3-gi` oraz `gir1.2-gtk-3.0` (na tym laptopie są już zainstalowane). Instalator uwzględnia je dla nowej instalacji. Przy przenoszeniu na inny laptop trzeba ponownie skonfigurować skrót aplikacji. Kalibracja zapisuje też identyfikator urządzenia, a zmiana ścieżki kamery wymaga ponownej kalibracji; nie wykrywa automatycznie przestawienia sprzętu ani zastąpienia go innym pod tą samą ścieżką.

Podgląd kamery USB, wykrywanie zielonego lub czerwonego punktu lasera (domyślnie zielonego) i zapis trafień po kalibracji obrazu projektora. Wymaga Pythona 3.11+ oraz sesji graficznej. Obsługa konkretnej kamery Trust Tyro 23637 wymaga testu na sprzęcie.

## Uruchomienie

Na Linux Mint 22 / Ubuntu / Debian można użyć instalatora:

```bash
bash install_linux.sh
bash start_linux.sh
```

Instalator używa `sudo` do pakietów systemowych i instaluje NumPy oraz OpenCV w lokalnym `.venv`. Starter domyślnie wybiera `/dev/video2`; inna kamera: `bash start_linux.sh --camera /dev/video0`.

Otwórz terminal w folderze zawierającym te pliki:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r aimlab_requirements.txt
python aimlab_irl_camera_mvp.py --camera 0
```

Jeśli brakuje modułu venv, na Debianie/Ubuntu zainstaluj `python3-venv`. OpenCV wymaga bibliotek graficznych systemu; przy błędzie dotyczącym `libGL.so.1` na Debianie/Ubuntu zainstaluj `libgl1`.

## Pierwszy test

1. Zamocuj kamerę i obejmij kadrem cały obraz projektora.
2. Naciśnij **C**, następnie kliknij rogi: lewy górny, prawy górny, prawy dolny, lewy dolny.
3. Naciśnij **M**, aby sprawdzić maskę wybranego koloru lasera.
4. Wyceluj laserem w obszar projekcji. Trafienia zapisują się w `aimlab_hits.csv` jako piksele kamery i współrzędne `u,v` w zakresie 0–1.
5. Zgaś laser na przynajmniej 150 ms przed następnym trafieniem. Ciągłe świecenie generuje pojedyncze trafienie.

Kalibracja zapisuje się w `aimlab_calibration.json`. Po przestawieniu kamery lub projektora wykonaj ją ponownie. Zmiana rozdzielczości unieważnia zapisane ustawienia. Skrypt nie weryfikuje automatycznie zmiany kamery.

Klawisze: **C** kalibracja, **R** usuń kalibrację, **M** maska, **S** zrzut, **I** diagnostyka, **Q/Esc** wyjście. Klawisze działają przy aktywnym oknie podglądu.

## Kamera i detekcja

```bash
ls /dev/video*
python aimlab_irl_camera_mvp.py --camera /dev/video0
python aimlab_irl_camera_mvp.py --camera 1
python aimlab_irl_camera_mvp.py --green-min 180 --green-delta 45
python aimlab_irl_camera_mvp.py --laser-color red --red-min 180 --red-delta 45
python aimlab_irl_camera_mvp.py --width 1920 --height 1080
```

Zamknij inne aplikacje korzystające z kamery. Sprawdź uprawnienia do wybranego urządzenia; nie uruchamiaj programu jako root. Kamera może udostępniać kilka urządzeń, z których tylko część dostarcza obraz. Żądana rozdzielczość i 30 FPS mogą nie być obsługiwane — rzeczywistą rozdzielczość wypisuje program, a zmierzony FPS pokazuje **I**.

Unikaj elementów projekcji w kolorze lasera. Przy fałszywych trafieniach podnieś progi, np. `--green-min 230 --green-delta 90` (dla czerwonego: `--laser-color red --red-min 230 --red-delta 90`). Dostosuj `--min-area` i `--max-area` do rozmiaru plamki. Detektor wybiera jeden punkt na klatkę; elementy sceny w kolorze lasera mogą nadal powodować fałszywe wykrycia. Testuj impulsy co najmniej 100 ms.

Skrypt kamery służy do detekcji. Znacznik czasu oznacza przetworzenie klatki, a nie dokładny moment emisji lasera. Używaj lasera bezpiecznego dla oczu i unikaj oczu oraz powierzchni odbijających.

## Trening na rzutniku

Po kalibracji zostaw program kamery uruchomiony i zamknij planszę kalibracyjną. W drugim terminalu w tym folderze uruchom:

```bash
.venv/bin/python aimlab_training.py
```

Domyślny układ: rzutnik 1920×1080 po prawej stronie ekranu laptopa, na pozycji x=1920, y=0. Inny układ ustawisz argumentami `--width`, `--height`, `--screen-x`, `--screen-y`.

Po trzech sekundach pojawia się niebieski cel. Trafienie w koło zalicza cel i po krótkiej przerwie wyświetla kolejny. Pudło pozostawia cel. Sesja obejmuje 10 celów (`--targets`), promień wynosi 70 pikseli (`--radius`). Zgaś laser między strzałami. Spacja w aktywnym oknie treningu rozpoczyna nową sesję; Q/Esc kończy trening. Kamera działa niezależnie.

Wyniki trafień i pudeł zapisują się w osobnym `aimlab_training_*.csv`. Historyczne zdarzenia z pliku kamery są pomijane. Czas reakcji jest orientacyjny: obejmuje opóźnienie kamery, przetwarzania, wyświetlacza i projektora. Trening odczytuje tylko zdarzenia wewnątrz skalibrowanej projekcji; strzały poza nią nie są liczone jako pudła. Zmiana kalibracji w trakcie treningu wymaga ponownego uruchomienia treningu.

Przy prześwietleniu punktu lasera do bieli potrzebne jest dostrojenie ekspozycji kamery. Zwiększenie mocy może pogorszyć detekcję.

## Krajobraz jako tło treningu

Domyślne tło to dostarczony krajobraz łąki w `assets/meadow.png`. Trening ładuje je raz przy uruchomieniu, dopasowuje do ekranu bez rozciągania proporcji i rysuje cele nad obrazem. Obraz może być lekko przycięty na ekranach o innych proporcjach. Statystyki mają przyciemniony pasek dla czytelności.

Z panelu wystarczy kliknąć Start treningu po przygotowaniu kamery i kalibracji. Alternatywne tło: `--background /ścieżka/obraz.png`. Dawne ciemne tło: `--plain-background`. Brak pliku obrazu daje komunikat błędu zamiast pustego ekranu.

Test obrazu i niebieskiego celu przy zielonych progach 180/45 nie wykazał fałszywych detekcji na pliku źródłowym ani po skalowaniu. Rzeczywista projekcja może zmienić kolory i wymaga sprawdzenia maski na kamerze.
