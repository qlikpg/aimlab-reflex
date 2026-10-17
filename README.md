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
| Trap-spidershot | 1, naprzemiennie baza przy dolnej krawędzi / losowy cel | 70 px | domyślnie 60 s |

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

## Rzutki SVG i wygląd celu

W panelu GTK3 pole **Wygląd celu** wybiera pomarańczowy rzutek (domyślny), czarny, pomarańczowo-czarny lub klasyczne niebieskie koło. Wybór zapisuje się w `aimlab_settings.json` pod kluczem `target_style` i jest przekazywany przez `--target-style`. Starszy plik ustawień bez tego pola dostaje domyślny wariant pomarańczowy. **Tryb gry Classic** i **wygląd classic** to niezależne ustawienia: każdy wygląd działa w każdym trybie gry.

```bash
.venv/bin/python aimlab_training.py --mode gridshot --mouse-test --screen-x 0 --screen-y 0 --target-style orange
.venv/bin/python aimlab_training.py --mode sixshot --target-style black
.venv/bin/python aimlab_training.py --mode multishot --target-style orange-black
.venv/bin/python aimlab_training.py --target-style classic
```

Źródła grafiki: `assets/targets/clay_target_orange.svg`, `clay_target_black.svg`, `clay_target_orange_black.svg`. Na Linux Mint rasteryzację wykonują systemowe **librsvg2-2** (librsvg ≥ 2.46) i **libcairo2**, wywoływane przez standardowy moduł `ctypes`. Te pakiety są już obecne na laptopie i zostały dodane do instalatora. Nie dodano zależności Pythona ani frameworka GUI. Na innym systemie brak bibliotek powoduje przejście na klasyczny cel.

Przy ładowaniu SVG jest renderowane z antyaliasingiem do RGBA. Przezroczyste marginesy viewBox są odcinane, aby parametr `radius` oznaczał połowę szerokości faktycznej sylwetki, a nie połowę pustego płótna. Docelowa szerokość to `round(2 × radius_po_skalowaniu)` pikseli; wysokość zachowuje proporcje rzutka. Promień referencyjny nadal skaluje się zgodnie z ekranem, tak jak w trybach treningowych.

Wspólne API `TargetAppearance.draw(image, target)` i `TargetAppearance.contains(target, x, y)` w `aimlab_target_styles.py` korzysta z tej samej bitmapy i tego samego zaokrąglonego początku wklejania. Kolory są przeliczane z natywnego, premultiplikowanego ARGB Cairo do RGBA/BGRA OpenCV. Skalowanie i mieszanie premultiplikowanych kolorów zapobiega ciemnym obwódkom. Cache przechowuje maksymalnie osiem rozmiarów; rasteryzacja SVG i skalowanie nie odbywają się w kolejnych klatkach ani po trafieniu w cel o tym samym rozmiarze.

Trafienie SVG wymaga maski alfa ≥ 32/255 w najbliższym pikselu obrazu. Całkowicie przezroczyste narożniki oraz niemal przezroczyste piksele skrajnej krawędzi są wyłączone. Ten próg jest częścią geometrii, nie progiem detektora kamery. Koło zachowuje dotychczasowe piksele rysowania i kolisty obszar trafienia. Rozmieszczanie nadal używa konserwatywnego koła obejmującego rzutek, więc nie ma kolizji ani mniejszego marginesu na HUD.

Brakujący, błędny lub całkowicie przezroczysty SVG powoduje użycie klasycznego koła **zarówno do rysowania, jak i trafień**. Program zapisuje czytelny komunikat z przyczyną do logu i wyświetla `SVG unavailable - classic targets` w oknie treningu. Nie modyfikuje ustawień użytkownika ani plików SVG. Kalibracja, CSV zdarzeń lasera, CSV wyników i definicje pomiarów czasu pozostają niezmienione.

**Kolor lasera:** sprawdzony zielony laser z progami 180/45 nie kolidował z bitmapami tych rzutków w teście cyfrowym. Pomarańczowe elementy mogą natomiast spełniać istniejące progi czerwonego detektora — przy czerwonym laserze wybierz czarny rzutek lub klasyczne niebieskie koło i sprawdź maskę na rzeczywistej projekcji. Detektor nie został zmieniony.

Testy `tests/test_target_styles.py` sprawdzają wszystkie trzy SVG, identyczną geometrię, kolory RGBA/BGR, krawędzie, skalowanie, zgodność maski z pozycją obrazu także dla ułamkowych środków i po przycięciu na brzegu ekranu, brak trafień w narożnikach, cache, restart trybów oraz fallback. Test GTK sprawdza zapis i przekazanie wszystkich czterech wariantów. Lokalny pomiar samego renderera przy 1920×1080 i sześciu celach: mediana około 3,0 ms/klatkę dla kół i 3,5 ms dla rzutków, przy zachowanym limicie około 30 FPS. Nie jest to pomiar opóźnienia ani FPS sprzętowego rzutnika.

Dokumentacja użytych API: [librsvg render_document](https://gnome.pages.gitlab.gnome.org/librsvg/Rsvg-2.0/method.Handle.render_document.html), [formaty obrazu i bufor Cairo](https://www.cairographics.org/manual/cairo-Image-Surfaces.html).

## Trap-spidershot

Nowy tryb zachowuje naprzemienną sekwencję Spidershot, ale rozdziela dwa rodzaje celów:

1. **Baza:** zawsze klasyczne niebieskie koło, niezależnie od pola „Wygląd celu”. Środek ma `x=(szerokość−1)/2`, `y=wysokość−1−promień`. Dolna krawędź aktywnego koła dotyka ostatniego wiersza projekcji; ozdobna obwódka jest przycinana do ekranu. Promień nadal skaluje się z rozdzielczością.
2. Po trafieniu bazy pojawia się **losowy cel w wybranym przez użytkownika wyglądzie**, z taką samą metodą losowania i marginesami jak w Spidershot. Po trafieniu wraca baza. Pozycja losowa jest odsunięta od bazy, powyżej niej; kierunek i odległość zmieniają się. Cele pozostają nieruchome.

W panelu wybierz **Trap-spidershot** oraz wygląd rzutka. Zmiana trybu nie zmienia Twojego wyboru wyglądu; dotyczy on tylko celu losowego. Niebieska baza ma kolisty obszar trafienia, a rzutek wybraną maskę alfa. Gdy wybrany jest wygląd klasyczny, oba cele są niebieskimi kołami.

Domyślnie: 60 s, promień 70 px przy 1920×1080, jeden aktywny cel; czas i promień są konfigurowalne. Statystyki środek→bok, powrót i pełne cykle działają jak w Spidershot, przy czym „środek” oznacza teraz bazę przy dolnej krawędzi. Instrukcje klawiszy przeniesiono na górę, aby nie zasłaniały bazy. Detekcja impulsów, kalibracja, wyniki i reguły czasu pozostają niezmienione.

```bash
.venv/bin/python aimlab_training.py --mode trap-spidershot --target-style orange --mouse-test --screen-x 0 --screen-y 0
```

### Podgląd maski na tle i pomiar błędu kalibracji

„Podgląd i maska” pokazuje teraz obraz kamery z maską zaznaczoną na magenta.
Klawisz **B** przełącza ten widok na dotychczasową maskę binarną. Suwaki
progów działają jak wcześniej. Podgląd nie zmienia detektora ani kalibracji.

Po zapisanej kalibracji kliknij **STOP**, następnie **Pomiar błędu**.
Na wybranym ekranie pojawi się tło łąki z czarno-białą tarczą podzieloną na cztery części. Wyłącz laser
i kliknij dokładnie środek tej tarczy w oknie kamery **AimLab IRL**.
Powtórz dla 25 punktów siatki 5×5 (od 5% do 95% szerokości i wysokości). Nie klikaj obrazu na projektorze.
Program przelicza kliknięcie istniejącą homografią i porównuje je ze znaną
pozycją środka tarczy. Wyniki są w pikselach wybranego ekranu projektora:

- `dx_px`, `dy_px`: pozycja wyliczona minus rzeczywista pozycja krzyżyka;
  dodatnie wartości oznaczają przesunięcie w prawo / w dół.
- `error_px`: odległość między tymi pozycjami.
- RMS: pierwiastek średniej kwadratów odległości z dotychczasowych punktów.
- max: największa zmierzona odległość.

Wynik obejmuje dokładność wskazania myszą i obrazowania kamery. To pomiar
niezależnych punktów kontrolnych, bez automatycznej korekty kalibracji.
**N** zaczyna nową serię; **Q/Esc** lub STOP kończy pomiar. Próbki z czasem UTC
są dopisywane do `aimlab_calibration_check.csv` (osobno od zdarzeń lasera).
Po 25. próbce podsumowanie pozostaje w oknie kamery.

CLI kamery: `--check-calibration --projector-width 1920 --projector-height 1080
--screen-x 1920 --screen-y 0 --show-mask` wraz z dotychczasowymi argumentami
kamery i progów. Wymiary odnoszą się do aktualnego trybu wyświetlania.

Punkty oznaczono tarczami w czterech naprzemiennych czarno-białych ćwiartkach. W pomiarze błędu klikaj środek tarczy. Podstawowa kalibracja nadal wymaga czterech zewnętrznych rogów białej ramki (LG → PG → PD → LD).

### Kalibracja wideo (Classic)

Wybierz kamerę i ekran projektora, następnie kliknij **Kalibracja**.
Etap 1: wskaż cztery zewnętrzne rogi ramki myszą. W oknie potwierdzenia
wybierz „Potwierdź i przejdź do lasera”, „Powtórz” lub „Anuluj”.
Nowe rogi zastąpią poprzednią kalibrację dopiero po potwierdzeniu.
Etap 2: panel automatycznie zwolni kamerę i uruchomi kalibrację laserową. Strzelaj laserem dokładnie w środek każdej z 25 tarcz.
Cel pozostaje aż do wykrycia świeżego impulsu wewnątrz środkowej części tarczy widocznej w kamerze. Pudło wyświetla MISS i wymaga ponowienia strzału. Gaś laser między strzałami
(minimum 150 ms). Początkowe 0,8 s każdego celu jest pomijane dla usunięcia
starych klatek. Program używa istniejącego detektora i progów panelu. Przed każdym celem mierzy obraz tła i tarczy bez lasera; zgaś laser w tym czasie.
Nagranie zawiera wyłącznie klatki z wykrytymi impulsami; analiza odczytuje
z niego pozycje lasera i ponownie sprawdza trafienie. Korekta korzysta z niezależnie zaobserwowanych środków tarcz, zamiast zakładać idealne trafienie w środek.
Nie trzeba zmieścić się w ustalonym czasie. Q/Esc lub STOP przerywa pomiar.

20 punktów służy dopasowaniu (RANSAC, minimum 18 zgodnych), pięć osobnych
punktów na przekątnej służy kontroli. Korekta wymaga RMS ≤8 px i maksymalnego
błędu ≤15 px na punktach kontrolnych, w pikselach aktualnego ekranu.
Jeżeli wcześniejsza kalibracja tej samej kamery i rozdzielczości ma mniejszy
lub równy błąd kontrolny, pozostaje zachowana. Poprzedni plik jest kopiowany
do `aimlab_calibration.previous.json`; nowy zachowuje dotychczasowy format
czterech rogów i zapisuje dodatkowo błędy kontroli. To metoda eksperymentalna:
ruch kamery, ekspozycja automatyczna i słaba widoczność mogą uniemożliwić
pomiar. Po korekcie sprawdź dokładność przyciskiem „Pomiar błędu”.

Nagranie MJPG znajduje się wyłącznie w RAM (`/dev/shm`, wymagane 100 MB wolne).
Plik jest usuwany z katalogu natychmiast po otwarciu i istnieje tylko przez
otwarty deskryptor do zakończenia analizy. Jest zwalniany po sukcesie, błędzie,
STOP/Q/Esc, a także po zabiciu procesu. Nie archiwizujemy ani nie wysyłamy wideo.
Pozostają tylko kalibracja, jej poprzednia wersja i tekstowe wyniki pomiaru.
CLI: `python aimlab_video_calibration.py --camera /dev/video2 --width 1920
--height 1080 --screen-x 1920 --screen-y 0`.

Po zakończeniu lub przerwaniu kalibracji wybrany tryb treningu pozostaje bez zmian. Kalibracja jest jednym procesem z dwoma etapami i jednym przyciskiem. Start treningu automatycznie uruchamia kamerę i czeka na wczytanie kalibracji.

Etap laserowy wyszukuje tarczę w obszarze przewidywanym przez potwierdzoną kalibrację myszy i kompensuje globalną zmianę jasności między klatkami. Niejednoznaczna lub niewidoczna tarcza powoduje ponowienie odczytu w tym samym oknie, zamiast zamknięcia etapu. Zgaś laser podczas przygotowywania tarczy; Q/Esc lub STOP nadal przerywa pomiar.
