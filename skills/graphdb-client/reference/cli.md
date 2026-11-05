# GraphDB Client — CLI reference (`graphdb <command>`)

- `config print` — print redacted configuration.
- `test --env <name>` — connectivity test per environment.
- `inspect` — showcase SQLQuery rendering: canonical SQL, one-line, fingerprints, timing, redaction.
- `export --schema_name ... --output_folder ...` — table/database export; optional DDL (`-c`), data (`-d`), gzip (`-z`), chunking, filters.
- `import --schema_name ... --input_folder ...` — import DDL/data; `-i` ignore-existing, `-z` gzip.
- `copy --from_env ... --to_env ...` — copy table/database across servers via a temporary export folder.
- `compare --from_env ... --to_env ...` — metadata and row-count comparison with tolerance, or random-sampling mode (`-rs`).
