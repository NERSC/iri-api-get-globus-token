# Publishing nersc-tokens

The package lives in `python/`. Run development commands from the repository root:

```bash
python -m pip install -e ./python build twine
python -m unittest discover -s python/tests -v
python -m build python --outdir dist
python -m twine check dist/*
```

## One-time PyPI setup

A PyPI project owner must configure a GitHub Trusted Publisher at
https://pypi.org/manage/project/nersc-tokens/settings/publishing/ using:

| Field | Value |
| --- | --- |
| PyPI project name | `nersc-tokens` |
| Owner | `NERSC` |
| Repository | `iri-api-get-globus-token` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

The repository's GitHub `pypi` environment allows only tags matching `v*`.
Repository maintainers can add required reviewers as appropriate. No long-lived PyPI API
token is needed for GitHub releases.

See [PyPI's Trusted Publisher documentation](https://docs.pypi.org/trusted-publishers/adding-a-publisher/).

## Release

Version `0.1.0` is already published on PyPI. Every release must use a new version;
PyPI does not allow re-uploading an existing distribution filename.

1. Update `version` in `python/pyproject.toml` (for example, to `0.1.1`) and merge
   the reviewed change.
2. Publish a GitHub release with a matching tag, such as `v0.1.1`.
3. The `publish.yml` workflow tests and builds the wheel and source distribution,
   validates their metadata, and publishes using the configured Trusted Publisher.

The workflow rejects a release tag that does not match the package version.
Users can install the latest published version with `pip install nersc-tokens`.
