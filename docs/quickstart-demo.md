# Quickstart Demo

> **v0.4 compatibility demo:** this exercises the current broad reference
> runtime. It is useful for implementation regression testing, but it is no
> longer the primary product onboarding path. The target experience starts from
> the Localize Anything Agent Skill.

The demo uses a tiny JSON fixture, synthetic local draft output, staging,
deterministic QA, compatibility readiness reports, and a delivery package.

It does not call providers, require credentials, mutate the fixture, or apply
changes back to a project.

```bash
python -m runtime.localize_anything quickstart-demo
```

By default, output is written under `localize-anything-demo-output/`, which is
ignored by git. To choose another location:

```bash
python -m runtime.localize_anything quickstart-demo --output-root /tmp/localize-anything-demo
```

The command prints and writes `quickstart-demo-summary.json`. The summary points
to:

- the copied demo project;
- staged target files;
- the deterministic QA report directory;
- `readiness-authorization-matrix.json`;
- `delivery-readiness-report.json`;
- the delivery package;
- the non-mutating apply plan;
- the public claim boundary note.

Synthetic demo output proves the engineering path works. It is not
provider-backed quality, production-ready translation, locale-complete support,
or full-product localization. It also does not demonstrate the complete target
v1 Standard workflow, independent three-level review, or review-cost reduction.
