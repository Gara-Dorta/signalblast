# Releasing

Notes for the maintainers on how to make a release and how the repository is set up for it.

## Making a release

The release tag has to be signed with a key in [.github/allowed_signers](.github/allowed_signers), otherwise the release workflow fails before publishing anything.
Create and push the tag locally, as tags created in the GitHub UI aren't signed:
```bash
git tag -s v1.2.3 -m v1.2.3
git push origin v1.2.3
```

Pushing a `v*` tag starts the [release workflow](.github/workflows/publish-pypi.yml), don't create the GitHub release yourself. The workflow:
1. Checks the tag signature, runs the tests and checks that the build is reproducible.
2. Publishes to TestPyPI.
3. Waits for the approval of the `pypi` environment, approve it from the workflow run with **Review deployments**.
4. Publishes to PyPI, then pushes and signs the docker image.
5. Creates the GitHub release, with generated notes and `SHA256SUMS` and `IMAGE-DIGESTS` attached.

Check the published release with `scripts/verify-release.sh v1.2.3`, see the [README](README.md#reproducible-builds).

## Signing key

The tags are signed with an SSH key used only for signing:
```bash
ssh-keygen -t ed25519 -C "signalblast signing" -f ~/.ssh/id_ed25519_signing
git config gpg.format ssh
git config user.signingkey ~/.ssh/id_ed25519_signing.pub
git config tag.gpgSign true
```
The public key is in [.github/allowed_signers](.github/allowed_signers) and is added to GitHub as a **Signing Key** in https://github.com/settings/ssh/new.

When replacing the key, add the new one to `allowed_signers` and keep the old one with `valid-before="YYYYMMDD"`, so that the older tags still verify.
