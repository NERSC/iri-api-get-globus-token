# Publishing nersc-tokens

The package lives in `python/`. Run development commands from the repository root:

```bash
python -m pip install -e ./python build twine
python -m unittest discover -s python/tests -v
python -m build python --outdir dist
python -m twine check dist/*
```

## One-time PyPI setup

A PyPI project owner must configure a GitHub Trusted Publisher. For a new project,
add a pending publisher at https://pypi.org/manage/account/publishing/ using:

| Field | Value |
| --- | --- |
| PyPI project name | `nersc-tokens` |
| Owner | `NERSC` |
| Repository | `iri-api-get-globus-token` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

For an existing project, add the same publisher under its Publishing settings.
The repository's GitHub `pypi` environment allows only tags matching `v*`.
Repository maintainers can add required reviewers as appropriate. No long-lived PyPI API
token is needed. Adding a pending publisher does not create the PyPI project;
the first successful upload does that.

See [PyPI's Trusted Publisher documentation](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

## Release

1. Update `version` in `python/pyproject.toml` and merge the reviewed change.
2. Publish a GitHub release with a matching tag, such as `v0.1.0`.
3. The `publish.yml` workflow tests and builds the wheel and source distribution,
   validates their metadata, and publishes using the configured Trusted Publisher.

The workflow rejects a release tag that does not match the package version.
After the first successful release, users can run `pip install nersc-tokens`.
