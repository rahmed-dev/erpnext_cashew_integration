# Data Flow

```mermaid
flowchart TD
    A[Accountant uploads Cashew CSV] --> B[Import Run DocType created]
    B --> C[Parse and pre-validate rows]
    C --> D[Lookup default category mapping table]
    D --> E[Preview: accountant reviews and overrides exceptions]
    E --> F[Queue background job]
    F --> G[Final validation before posting]

    G -->|missing mapping / invalid row| H[Mark row error]
    G -->|mapped/overridden and valid| I[Classify transaction]

    I -->|Income| J[Create Sales Invoice]
    I -->|Expense > threshold| K[Create Purchase Invoice]
    I -->|Expense <= threshold| L[Create Journal Entry]

    J --> M[Persist row result]
    K --> M
    L --> M
    H --> M

    M --> N[Update Import Log summary]
    N --> O[Generate diagnostics CSV]
    O --> P[Accountant reviews status and downloads report]
```

## Notes

- Processing is asynchronous via queue for reliability at 100-1000 rows/file.
- Idempotency guard prevents reposting the same source transaction on re-run.
- Default mapping comes from mapping table; accountant can override in preview for exceptions.
- Rows with unresolved validation or mapping errors are blocked from posting and reported in diagnostics.
