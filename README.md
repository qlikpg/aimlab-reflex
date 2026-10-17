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

Po trzech sekundach pojawia się niebieski cel. Trafienie w koło zalicza cel i po krótkiej przerwie wyświetla kolejny. Pudło pozostawia cel. Sesja obejmuje 10 celów (`--targets`), promień wynosi domyślnie 70 pikseli przy 1920×1080 (`--radius`, skalowany z ekranem). Zgaś laser między strzałami. Spacja w aktywnym oknie treningu rozpoczyna nową sesję; Q/Esc kończy trening. Kamera działa niezależnie.

Wyniki trafień i pudeł zapisują się w osobnym `aimlab_training_*.csv`. Historyczne zdarzenia z pliku kamery są pomijane. Wiek trafionego celu jest orientacyjny: obejmuje opóźnienie kamery, przetwarzania, wyświetlacza i projektora. Trening odczytuje tylko zdarzenia wewnątrz skalibrowanej projekcji; strzały poza nią nie są liczone jako pudła. Zmiana kalibracji w trakcie treningu wymaga ponownego uruchomienia treningu.

Przy prześwietleniu punktu lasera do bieli potrzebne jest dostrojenie ekspozycji kamery. Zwiększenie mocy może pogorszyć detekcję.

## Krajobraz jako tło treningu

Domyślne tło to dostarczony krajobraz łąki w `assets/meadow.png`. Trening ładuje je raz przy uruchomieniu, dopasowuje do ekranu bez rozciągania proporcji i rysuje cele nad obrazem. Obraz może być lekko przycięty na ekranach o innych proporcjach. Statystyki mają przyciemniony pasek dla czytelności.

Z panelu wystarczy kliknąć Start treningu po przygotowaniu kamery i kalibracji. Alternatywne tło: `--background /ścieżka/obraz.png`. Dawne ciemne tło: `--plain-background`. Brak pliku obrazu daje komunikat błędu zamiast pustego ekranu.

Test obrazu i niebieskiego celu przy zielonych progach 180/45 nie wykazał fałszywych detekcji na pliku źródłowym ani po skalowaniu. Rzeczywista projekcja może zmienić kolory i wymaga sprawdzenia maski na kamerze.

## Tryby treningowe

W panelu GTK3 wybierz **Tryb treningu**, **Czas sesji** i metodę sterowania. Zmiana trybu ustawia jego wartości domyślne. Parametry treningu można zmieniać przy działającej kamerze; podczas gry są blokowane. Panel zachowuje nowe ustawienia w tym samym `aimlab_settings.json`. Starsze ustawienia otwierają się jako Classic z dotychczasowym promieniem i liczbą celów.

| Tryb | Jednocześnie | Promień przy 1920×1080 | Koniec sesji |
|---|---:|---:|---|
| Classic | 1 | 70 px | 10 trafionych celów (konfigurowalne) |
| Gridshot | 3 | 70 px | domyślnie 60 s |
| Sixshot | 6 | 30 px | domyślnie 60 s |
| Multishot | 5 | 55 px | domyślnie 60 s |
| Spidershot | 1, naprzemiennie środek/bok | 70 px | domyślnie 60 s |

Panel pozwala wybrać 30, 60 lub 120 sekund. Gridshot, Sixshot i Multishot pozwalają też zmienić liczbę aktywnych celów (1–24). Spidershot i Classic zawsze pokazują jeden. Promień podawany jest w pikselach referencyjnych 1920×1080, skalowanych współczynnikiem `min(szerokość/1920, wysokość/1080)`. W Sixshot można zwiększyć promień, jeśli dokładność kamery lub projektora jest ograniczona.

Gridshot/Sixshot/Multishot natychmiast zastępują trafiony cel, zachowując liczbę celów. Pozycje są losowane na siatce bez kolizji, z marginesami na obwódki i HUD. Jeśli wybrana liczba lub promień nie mieści się w dostępnej geometrii, panel i CLI zgłaszają czytelny błąd zamiast generować nakładające się cele. Spidershot zaczyna w środku, po trafieniu pokazuje losowy punkt boczny, następnie środek. Kierunki i odległości boczne zmieniają się. Cele są nieruchome; nie ma śledzenia ani animacji ruchu.

### Test myszą, bez kamery i rzutnika

W panelu wybierz **Sterowanie → Test myszą — bez kamery**. Przy jednym ekranie zostanie wybrany ekran laptopa. Klikaj lewym przyciskiem bezpośrednio w oknie OpenCV. Laser pozostaje domyślnym wejściem normalnego treningu. Można też uruchomić:

```bash
.venv/bin/python aimlab_training.py --mode gridshot --mouse-test --screen-x 0 --screen-y 0
.venv/bin/python aimlab_training.py --mode sixshot --mouse-test --screen-x 0 --screen-y 0 --radius 45
.venv/bin/python aimlab_training.py --mode multishot --duration 120 --active-targets 5
.venv/bin/python aimlab_training.py --mode spidershot --duration 60
.venv/bin/python aimlab_training.py --targets 10
```

Ostatnie trzy polecenia bez `--mouse-test` wymagają uruchomionej, skalibrowanej kamery. Wszystkie dotychczasowe argumenty CLI nadal działają. Nowe: `--mode`, `--duration`, `--active-targets`, `--mouse-test`. Spacja zaczyna nową sesję po odliczaniu; Q/Esc wychodzi. Panel STOP kończy proces i zapisuje podsumowanie rozpoczętej sesji.

### Zdarzenia i granice sesji

Detektor, jego progi, domyślne 150 ms zwolnienia, kalibracja i CSV `utc,monotonic_s,pixel_x,pixel_y,u,v` nie zostały zmienione. Jeden wiersz przekazywany jest do wspólnego silnika co najwyżej raz; zduplikowane znaczniki i zdarzenia poza kolejnością są odrzucane. Jeden strzał może trafić najwyżej jeden cel (najbliższy, jeśli doszłoby do kolizji). Jedna fizyczna aktywacja jest rozpoznawana przez dotychczasowy mechanizm uzbrajania kamery — renderer nie zastępuje go dodatkowym opóźnieniem.

Nowe cele mogą być trafione dopiero po prezentacji klatki OpenCV; dla ostrożności moment aktywacji zapisujemy po `waitKey`. Zdarzenia sprzed sesji, sprzed aktywacji wskazanego celu i po końcu sesji nie są zaliczane. Classic zachowuje przerwę 0,6 s między celami; pozostałe tryby nie mają tej przerwy. Przy rozpoczęciu lub restarcie sesji czytnik ustawia się na końcu CSV, a kolejka kliknięć jest czyszczona. Niepełne wiersze są buforowane. Podmiana, skrócenie lub wykryte przepisanie CSV powoduje odrzucenie starych danych i zakończenie trwającej sesji komunikatem o zmianie strumienia. Usunięty plik jest pomijany do jego ponownego pojawienia się. Panel nadal zatrzymuje trening laserowy po utracie gotowości procesu kamery. Tryb myszy nie zależy od stanu kamery.

### Wyniki i definicje metryk

Wyniki pozostają w `aimlab_training_*.csv` w katalogu wskazanym przez `--hits` (domyślnie folder projektu). Pierwsze dziewięć kolumn historycznego formatu pozostaje dostępne. Nowe pliki mają `schema_version=2`, identyfikator trybu i sesji oraz `event_type`: **shot** (strzał) lub **summary** (jedno podsumowanie sesji). Przy liczeniu trafień z wierszy filtruj `event_type=shot`, aby nie doliczać podsumowania. `result` podsumowania rozróżnia ukończenie, restart, zatrzymanie i zmianę strumienia.

- `session_id`: unikatowy identyfikator każdej sesji; `session` pozostaje numerem sesji w pliku.
- `duration_s`: czas od rozpoczęcia gry po odliczaniu do zakończenia; dla ukończonych trybów czasowych dokładny skonfigurowany limit. Przy przerwaniu rzeczywisty krótszy czas.
- `hits`, `misses`: liczby zaliczonych zdarzeń trafienia/pudła. Pudło nie usuwa celu. Strzały fizyczne poza kalibracją nie są emitowane przez detektor i nie wchodzą do celności.
- `accuracy_percent`: `100 × hits / (hits + misses)`; bez strzałów 0%.
- `hits_per_second`: `hits / duration_s`; przy zerowym czasie 0.
- `mean_hit_interval_ms`: średnia różnic kolejnych znaczników czasu **trafień**, z pominięciem pudeł; pusta wartość przy mniej niż dwóch trafieniach. To odstęp między trafieniami, nie fizjologiczny czas reakcji.
- `target_age_ms`: wiek wskazanego celu od jego prezentacji do znacznika strzału. `mean_target_age_ms` jest średnią dla trafień. Dawna kolumna `approx_reaction_ms` zachowana jest jako alias `target_age_ms` dla zgodności, a nie jako nowy pomiar fizjologiczny.
- `target_id`, `target_x/y`, `target_u/v`, `target_radius_px`: tożsamość i geometria celu. Przy pudle wskazujemy najbliższy aktywny, już zaprezentowany cel. Promień jest rzeczywisty po skalowaniu.
- `u/v`, `shot_x/y`: pozycja strzału (znormalizowana i w pikselach projektora). `error_px`: odległość euklidesowa strzału od środka wskazanego celu. Puste pola pozycji w podsumowaniu nie oznaczają zera.
- Spidershot: `mean_center_to_side_ms` to średni odstęp od trafienia środka do następnego trafienia boku; `mean_return_to_center_ms` od trafienia boku do następnego trafienia środka. `full_cycles` liczy ukończone sekwencje **środek → bok → środek**. Brak odpowiednich par daje pustą średnią.

Metryki obejmują opóźnienia kamery, obróbki, OpenCV i projektora. Mysz przechodzi przez ten sam silnik, ale ma inne opóźnienia i jest oznaczona `source=mouse`. `read_results(path)` w `aimlab_training.py` odczytuje zarówno nowy format, jak i starsze wyniki Classic; brakujące historyczne metryki pozostawia puste. Nie przelicza starych plików i ich nie nadpisuje.

### Testy i wydajność

```bash
.venv/bin/python -m unittest discover -s tests -v
python3 -m unittest discover -s tests -p test_panel.py -v
```

Pierwsze polecenie uruchamia testy logiki, zdarzeń, metryk, myszy i renderowania bez kamery/projektora. Opcjonalne testy GTK wymagają systemowego Pythona z GTK3 i sesji graficznej; w innym środowisku są pomijane. Tło i jego paski HUD są przygotowane raz, liczba klatek ograniczona do około 30 FPS. Nie ma nowych zależności ani intensywnych animacji. Kalibracja, detektor i skrypty uruchamiające pozostają bez zmian.
