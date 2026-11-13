# Virtual monorepos (VMR)

A virtual monorepo combines several Git repositories into one workspace with
[git-repo](https://gerrit.googlesource.com/git-repo). A *manifest repository* holds XML
manifests (e.g. `default.xml`) listing the member repositories, the revision each one
tracks and the symlinks between them. PTk ships git-repo (XC-CE fork) and wraps it as
`ptk vmr`; see the [CLI reference](docs/reference/cli.rst) for all options. The same
guide is part of the documentation: [docs/guides/vmr.rst](docs/guides/vmr.rst).

## Layout

```text
my_vmr/                    workspace root, not a Git repository
├── .repo/                 git-repo data: manifest checkout, Git objects of all members
├── shared_kit/            member repository
└── product/               member repository (.git points into ../.repo)
    └── kit -> ../shared_kit/kit    linkfile from the manifest
```

- Symlinks between members are `<linkfile>` entries of the manifest. `repo sync` creates
  them; never create or commit them by hand (list them in `.gitignore`). To add, change
  or remove one, change the manifest repository.
- Members are checked out at the commit the manifest resolves (detached HEAD). Switch to
  a branch inside a member before committing.
- A member's `.git` points into `.repo`. Never replace it (`git init`, cloning or copying
  another repository into the folder): the member leaves the VMR.

## Prerequisites (Windows)

- Developer Mode enabled (or admin rights); otherwise symlinks are not created.
- `git config --global core.symlinks true` and `core.longpaths true`, set before the first
  sync. Repositories checked out earlier contain one-line text files instead of symlinks:
  check the VMR out again.
- A short workspace path, e.g. `C:\git\my_vmr`.
- No separate git-repo installation: `ptk vmr` runs the shipped one, and new VMRs install
  it from a local copy without a download. The PTk installer adds a `repo` command
  (`ptk vmr repo -- ...`) unless another `repo` is already on `PATH`.

## Daily work

| Command | Purpose |
|---|---|
| `ptk vmr init URL -b develop --dir C:\git\my_vmr` | New VMR from a manifest repository branch. Inside a VMR, URL defaults to its manifest repository. Another manifest file: `ptk vmr repo -- init -u URL -m develop.xml`. |
| `ptk vmr sync` | Fetch and update every member, recreate the symlinks (`repo sync -j<cores> --current-branch`). |
| `ptk vmr sync -l` | Local only: recreate missing or broken symlinks without network access. |
| `ptk vmr status` | Branch, commit, local changes and ahead/behind of every member. |
| `ptk vmr reinit -b release/x` | Switch the VMR to another manifest branch. Stops on uncommitted changes or unpushed commits (`--force` switches anyway). |
| `ptk vmr manifest -o vmr_manifest.xml` | Revision-locked manifest: every member at its current commit. |
| `ptk vmr init --manifest vmr_manifest.xml --dir C:\git\repro` | Reproduce a state exactly, e.g. from the `vmr_manifest.xml` a CI run uploaded. |
| `ptk vmr repo -- start feature/x --all` | Any other git-repo command (`forall`, `diff`, `start`, `info` ...). |

Open a member folder (not the VMR root) in the editor and use normal Git commands there.
For a change across members, create the same branch name in each of them
(`ptk vmr repo -- start feature/x --all`).

## DOs and DON'Ts

- Preview cleans with `git clean -ndx`; prefer `git clean -fd`. `git clean -x` and
  `git stash --all` remove ignored files, i.e. the symlinks.
- Delete a symlink only as a link (`rm kit`, `cmd /c rmdir kit`). Recursive deletes that
  follow the link (`rm -rf kit/`, `Remove-Item -Recurse`, `rmdir /s`) delete the files of
  the other member.
- Recover symlinks with `ptk vmr sync -l`.

## PTk in a VMR

PTk detects the VMR from `.repo` and treats every configured member as a repository with
its own alias and configuration ([configuration](docs/guides/configuration.rst)).
`ptk repos` lists them; `ptk jobs` lists their jobs. Inside a member folder, commands go
to that member without the alias prefix; at the root, use `ptk ALIAS JOB`.
`ptk init --config-dir PATH` initializes all unconfigured members. Workspace workflows
(`workflows/NAME.ptk.yml` at the root) run jobs of several members; see
[workflows](docs/guides/workflows.rst). Maintainer lists, credentials and tools stay per
member.

## CI and releases

- Generated GitHub workflows check the VMR out with the members' manifest (`cx.vmr`).
  Their `manifest-branch` input selects the manifest revision; `checkout-ref` checks out
  the branch of an open pull request in every member that has one. See
  [GitHub Actions](docs/guides/github-actions.rst).
- With `cx.vmr.upload_manifest: true` every run uploads `vmr_manifest.xml` into its upload
  folders, so each artifact can be traced and rebuilt.
- Freezing a release: write `ptk vmr manifest --revision PRODUCT=release/x` to a file in
  the product repository's release branch (the product follows its branch, every other
  member stays at its commit) and check release branches out from that file
  (`repo init --standalone-manifest -u file://...`). Rewriting the file with every release
  candidate gives its Git history per candidate. No branches in the manifest repository
  are needed.
- Validating a shared member: a pull request in a shared repository can trigger the
  consumer's PR workflow with `checkout-ref` set to its branch, so the consumer builds
  with the change before it is merged.
- `checkout-ref` per member: no branch of that name → the manifest's commit; branch with an
  open pull request → its merge result; branch without an open pull request → the checkout
  fails. A change across members needs the same branch name and an open pull request in
  each.
