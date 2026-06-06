# Ecotone Native Plant Flashcards

This is the working flashcard dashboard recovery package.

Current dashboard data:

- Plant cards: 509
- Batch size: 25 cards
- Front of card: cycling iNaturalist photos
- Back of card: plant identity, traits, habitat/wildlife information, complete record table, and Lepidoptera host count when listed
- Browser memory: exotic marks, missed cards, and mastery scores are saved in localStorage under `nativePlantStats`

## GitHub Pages

For GitHub Pages, `index.html` must be at the repository root and `data/daily_data.js` must remain inside the `data` folder.

## Local updater

Keep `daily_fetch.py` in your local desktop update folder. It is ignored by `.gitignore` so it does not need to be uploaded to GitHub.
