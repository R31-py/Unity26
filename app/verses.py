"""Verse-of-the-day for the main dashboard's verse card.

Deliberately NOT fetched from any external API — the spec calls for these
to be "hardcoded locally" so the dashboard has zero extra network/DB cost
and works even if a future API integration is down. `verse_of_the_day()`
just picks a deterministic entry from this list based on the calendar day,
so every user sees the same verse on a given day and it rotates on its own
without any admin action.
"""

from datetime import date

# Add/remove/reorder freely — the day-of-year modulo below adapts to
# whatever length this list is.
VERSES = [
    {"text": "Be kind and compassionate to one another, forgiving each other, "
              "just as in Christ God forgave you.", "reference": "Ephesians 4:32"},
    {"text": "I can do all things through him who strengthens me.",
     "reference": "Philippians 4:13"},
    {"text": "Trust in the Lord with all your heart, and do not lean on your "
              "own understanding.", "reference": "Proverbs 3:5"},
    {"text": "The Lord is my shepherd; I shall not want.", "reference": "Psalm 23:1"},
    {"text": "For God so loved the world, that he gave his only Son, that "
              "whoever believes in him should not perish but have eternal life.",
     "reference": "John 3:16"},
    {"text": "Rejoice always, pray without ceasing, give thanks in all "
              "circumstances.", "reference": "1 Thessalonians 5:16-18"},
    {"text": "Love is patient and kind; love does not envy or boast; it is "
              "not arrogant or rude.", "reference": "1 Corinthians 13:4"},
    {"text": "Be strong and courageous. Do not be frightened, for the Lord "
              "your God is with you wherever you go.", "reference": "Joshua 1:9"},
    {"text": "Cast all your anxieties on him, because he cares for you.",
     "reference": "1 Peter 5:7"},
    {"text": "Let all that you do be done in love.", "reference": "1 Corinthians 16:14"},
    {"text": "The joy of the Lord is your strength.", "reference": "Nehemiah 8:10"},
    {"text": "Come to me, all who labor and are heavy laden, and I will give "
              "you rest.", "reference": "Matthew 11:28"},
    {"text": "And we know that for those who love God all things work "
              "together for good.", "reference": "Romans 8:28"},
    {"text": "Give thanks to the Lord, for he is good; his steadfast love "
              "endures forever.", "reference": "Psalm 107:1"},
    {"text": "Do not be anxious about anything, but in everything by prayer "
              "and supplication with thanksgiving let your requests be made "
              "known to God.", "reference": "Philippians 4:6"},
]


def verse_of_the_day(today=None):
    """Deterministic pick: same verse for everyone all day, changes at
    midnight, and cycles back to the top once it runs past the list."""
    today = today or date.today()
    index = today.timetuple().tm_yday % len(VERSES)
    return VERSES[index]
