# -*- coding: utf-8 -*-
"""Ndihmës të përbashkët për të gjitha blueprint-et."""
from datetime import date

# Vargje biblike të thjeshta për "Vargu Biblik i Ditës" te paneli i kampistit.
# Rrotullohen sipas ditës së vitit, pa kërkuar lidhje me internet apo API.
_VERSES = [
    ("Filipianëve 4:13", "Të gjitha i bëj dot me anë të Krishtit që më jep fuqi."),
    ("Jozueu 1:9", "A nuk të urdhërova? Ji i fortë dhe trim; mos ki frikë dhe mos u trondit."),
    ("Psalmet 23:1", "Zoti është bariu im, nuk do të kem asnjë mungesë."),
    ("Isaia 40:31", "Ata që kanë shpresë te Zoti fitojnë përsëri forcë, ngjiten me krahë si shqiponja."),
    ("Romakëve 8:28", "Për ata që e duan Perëndinë të gjitha gjërat bashkëveprojnë për të mirë."),
    ("Fjalët e Urta 3:5-6", "Ki besim tek Zoti me gjithë zemër dhe mos u mbështet në gjykimin tënd."),
    ("Mateu 6:33", "Kërkoni më parë mbretërinë e Perëndisë dhe drejtësinë e tij."),
    ("Psalmet 118:24", "Kjo është dita që bëri Zoti; të gëzohemi dhe të kënaqemi në të."),
    ("Galatasve 6:9", "Të mos lodhemi duke bërë të mirën, sepse në kohën e duhur do të korrim."),
    ("Numrat 6:24-26", "Zoti të bekoftë dhe të ruajttë. Zoti të bëjë të shkëlqejë fytyrën e tij mbi ty."),
    ("2 Timoteut 1:7", "Perëndia nuk na dha frymë frike, por force, dashurie dhe urtësie."),
    ("Psalmet 27:1", "Zoti është drita ime dhe shpëtimi im; nga kush do të kem frikë?"),
    ("Jakobi 1:2-3", "E konsideroni një gëzim të madh kur ndeshni prova të ndryshme."),
    ("Zbulesa 21:5", "Ja, unë i bëj të gjitha gjërat të reja."),
]


def verse_of_the_day():
    """Kthen (referenca, teksti) të njëjtë gjatë gjithë ditës, pa gjendje/DB."""
    idx = date.today().timetuple().tm_yday % len(_VERSES)
    ref, text = _VERSES[idx]
    return ref, text


def allowed_upload_extension(filename: str, allowed: set) -> bool:
    if "." not in filename:
        return False
    ext = "." + filename.rsplit(".", 1)[1].lower()
    return ext in allowed
