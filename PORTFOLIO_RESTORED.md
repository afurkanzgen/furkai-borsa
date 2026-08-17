# V15.9.3 Portfolio Restoration

The saved portfolio was restored from the last audited project state.
The portfolio is persisted in `furkai_bist.db` and also seeded by `INITIAL_PORTFOLIO` if the DB is empty.

The app must render saved positions even when live quote data is unavailable. Live price fields may show `—` when the quote provider is unavailable.
