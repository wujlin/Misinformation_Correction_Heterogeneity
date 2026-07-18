# Reddit Data Access Notes

## Current Status

Reddit for Researchers API access was not approved. The rejection was received on July 4, 2026.

The project therefore does not assume live Reddit API access. The repository should be treated as a code repository with local-only data assets.

## Data-Access Policy

The default project position is:

- do not use browser login cookies as a data-access method;
- do not commit Reddit credentials, browser sessions, cookies, or API tokens;
- do not redistribute raw Reddit content through GitHub;
- keep raw, interim, processed, and prediction files local unless a separate data-sharing review allows release;
- use only derived summaries, figures, code, and documentation in the public repository.

## Optional OAuth Utility

The repository retains `src/reddit_collect.py` as an optional utility for users who have their own valid Reddit API access.

If valid OAuth credentials are available, create a local `.env` file:

```text
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=misinformation-correction-pilot/0.1 by u/YOUR_USERNAME
```

The `.env` file is ignored by Git.

The current project does not rely on this route because Reddit for Researchers access was not granted.

If OAuth credentials are absent, the collector stops by default. The script has an explicit `--allow-public-json` option for users who independently determine that unauthenticated public JSON endpoints are appropriate for their own use case, but this route is not the default project workflow.

## Archive and Public-Dataset Route

The current empirical work uses locally prepared datasets and derived files. The key local data sources are documented in [`docs/datasets.md`](datasets.md).

The scripts support two non-live-data routes:

1. a public COVID-19 vaccine Reddit dataset used for the first topic-specific feasibility and mechanism analysis;
2. local Watchful1/Pushshift-style archive files, if available to the researcher under the relevant data-use conditions.

Raw archive files, raw comments, raw submissions, and derived comment-level files are local-only.

## Responsible-Building Boundary

The API rejection means the public repository should not claim live Reddit API access or imply that readers can reproduce the collection step through this project.

If the project reapplies for access later, the application should include:

- a precise research question;
- the exact data fields needed;
- the requested time window and subreddits;
- privacy and de-identification procedures;
- data-retention and deletion plan;
- public-output boundary;
- ethics review or institutional approval status, if available.

Until then, public documentation should describe the data as locally prepared Reddit discussion data and should not imply ongoing Reddit API collection.
