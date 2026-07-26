from datetime import date

VERSES = [
    {
        "text": "Në fakt në se rrëzohen, njëri ngre tjetrin; por mjerë ai që është vetëm dhe rrëzohet, sepse nuk ka njeri që ta ngrejë!",
        "reference": "Predikuesi 4:10"
    },
    {
        "text": "Ja, sa e mirë dhe e kënaqshme është që vëllezërit të banojnë bashkë në unitet!",
        "reference": "Psalmet 133:1"
    },
    {
        "text": "Tani unë nuk lutem vetëm për ta, por edhe për ata që do të besojnë në mua me anë të fjalës së tyre, që të gjithë të jenë një, ashtu si ti, o Atë, je në mua dhe unë në ty; edhe ata të jenë një në ne, që bota të besojë se ti më ke dërguar.",
        "reference": "Gjoni 17:20-21"
    },
    {
        "text": "Sepse, sikurse në një trup kemi shumë gjymtyrë dhe të gjitha gjymtyrët nuk kanë të njëjtën funksion, kështu edhe ne, megjithëse jemi shumë, jemi një trup në Krishtin dhe secili jemi gjymtyrë të njëri-tjetrit.",
        "reference": "Romakëve 12:4-5"
    },
    {
        "text": "Tani vëllezër, ju bëj thirrje në emër të Zotit tonë Jezu Krishtit të flisni që të gjithë të njëjtën gjë dhe të mos keni ndasi midis jush, por të jeni plotësisht të bashkuar, duke pasur një mendje dhe një vullnet.",
        "reference": "1 e Korintasve 1:10"
    },
]


def verse_of_the_day(today=None):
    """Deterministic pick: same verse for everyone all day, changes at
    midnight, and cycles back to the top once it runs past the list."""
    today = today or date.today()
    index = today.timetuple().tm_yday % len(VERSES)
    return VERSES[index]
