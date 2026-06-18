# Reddit Data Access Notes

## Default Position

Do not use a Reddit login cookie as the default data access method.

The pilot collector first supports:

1. Reddit OAuth through environment variables.
2. Public Reddit JSON endpoints as a fallback.

Cookie-based scraping creates account-security and terms-of-service risk. It should only be considered after the official or public routes fail, and it should not be committed to the repository.

Current pilot note: public Reddit JSON endpoints may be blocked by Reddit network security and may return a message asking the user to log in or use a developer token. In that case, use Reddit OAuth credentials instead of browser cookies.

## Credentials

Create a `.env` file locally if OAuth is needed:

```text
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=misinformation-correction-pilot/0.1 by u/YOUR_USERNAME
```

The `.env` file is ignored by Git.

The first recommended credential path is a Reddit developer app, not a browser login cookie.

## Pilot Goal

The first data-access goal is not full-scale scraping. The first goal is to verify:

- whether misinformation threads can be found;
- whether comments can be collected;
- whether public correction is frequent enough;
- whether user-level cross-community histories are available enough to build brokerage measures;
- whether exposed-but-silent users can be constructed from thread participation.
