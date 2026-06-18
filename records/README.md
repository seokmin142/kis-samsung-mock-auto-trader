# Mock trading records

The program writes one JSON Lines file per KST trading day:

```text
records/trading_YYYYMMDD.jsonl
```

Records deliberately exclude the account number, app key, app secret, access token,
and HTTP authorization headers. After a mock-trading run, review the file before
committing it to GitHub.
