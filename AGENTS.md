# Maintenance contract

- Read README.md, the relevant Markdown skill and structured configuration before editing.
- Authoritative implementation: src/pipeline.py and src/config.py. Preserve version, authors and licensing metadata.
- Make scoped changes in small modules. Update public usage and negative-path checks together.
- Validation entry: `python -m unittest discover -s tests -v`. Record the failing case, passing case, command and scope in the PR.
- A passing offline check is not external-service acceptance or a release. Never use live credentials or send messages to validate a change without task authorization.
- Keep generated outputs separate from editable Markdown, YAML and implementation sources.
