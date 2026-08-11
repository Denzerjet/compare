# Basque locale date format does not handle conditional suffixes (date declination)

Hello,

The Basque date declination grammar requires some logic but we can't introduce due to the software design.

''Here is a clear example of the problem:

    **Current Django Output:** 2025ko urriaren 11a
    **Correct Grammatical Form:** 2025eko urriaren 11

There are two errors here based on conditional rules:

    **Year Suffix:** It should be 2025eko. The suffix changes based on the last sound of the year number. Years ending in a consonant sound (like 2025, bost) must use -eko, while the current output -ko is for years ending in a vowel (like 2024, lau).
    **Day Article:** It should be 11. The -a article should not be added to numbers that already end in the vowel ‘a’. The number 11 in Basque is hamaika, so adding another -a (hamaika-a) is grammatically wrong.''

My proposal is to change the Basque (eu) date template with "(e)ko" instead of "ko" in the year suffix and "(a)" instead of "a" in the day suffix

Reported in django ticket #36679: https://code.djangoproject.com/ticket/36679
