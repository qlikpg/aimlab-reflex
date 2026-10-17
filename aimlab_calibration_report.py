"""Human-readable calibration report; usable by the GTK system interpreter."""

def format_report(report):
    status = report.get('status')
    title = {'applied':'Kalibracja zakończona pomyślnie — zapisano korektę.',
             'unchanged':'Kalibracja sprawdzona pomyślnie — poprzednia jest równie dobra lub lepsza.',
             'cancelled':'Kalibracja przerwana — nie zapisano korekty.',
             'failed':'Kalibracja nieudana — nie zapisano korekty.'}.get(status,
                 'Brak potwierdzonego wyniku kalibracji.')
    lines = [title]
    if report.get('message'):
        lines.append(report['message'])
    lines.append(f"Punkty: {report.get('hits',0)}/25 | pudła: {report.get('misses',0)} | ponowienia obrazu: {report.get('retries',0)}")
    lines.append(f"Czas: {report.get('duration_s',0):.1f} s")
    metrics = report.get('metrics',{})
    if metrics:
        lines.append(f"Błąd na 5 niezależnych punktach (piksele rzutnika):")
        lines.append(f"RMS przed: {metrics['rms_before_px']:.2f} → po: {metrics['rms_after_px']:.2f} px")
        lines.append(f"Maks. błąd przed: {metrics['max_before_px']:.2f} → po: {metrics['max_after_px']:.2f} px")
        lines.append(f"Zastosowane przesunięcie (średnia z 25 punktów): X {metrics['shift_x_px']:+.2f}, Y {metrics['shift_y_px']:+.2f} px")
        lines.append(f"Największe przesunięcie: {metrics['max_shift_px']:.2f} px")
        lines.append('Dodatnie X: w prawo; dodatnie Y: w dół. Korekta może różnić się w różnych miejscach ekranu.')
    lines.append('Nagranie usunięte.' if report.get('video_removed') else 'Brak potwierdzenia zwolnienia nagrania.')
    lines.append('Kalibracja wstępna myszą pozostaje zapisana; raport dotyczy etapu laserowego.')
    return '\n'.join(lines)
