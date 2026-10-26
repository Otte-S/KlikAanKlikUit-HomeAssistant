# Publishing

## Release preparation

1. Run the tests and format checks listed in the README.
2. Confirm that the GitHub **Tests** and **Validate** workflows pass for the release commit.
3. Test configuration, options, a classic light, a dimmer and cloud recovery against an ICS-2000. Include an ECO-DIM.07 or another type-34 Zigbee dimmer when verifying issue #1.
4. Confirm that existing entity IDs and custom names survive an upgrade from 2.x.
5. Review the breaking changes in CHANGELOG.md and README.md.
6. Merge the reviewed release branch and create a GitHub release whose tag matches the version in manifest.json, for example `v3.0.0`.

HACS uses GitHub releases when available. A tag on its own is not a published release. Before a release exists, HACS custom repositories use the default branch.

## Default HACS catalog

The repository needs a public description, relevant topics, enabled issues, a license, passing HACS validation and passing Hassfest validation.

The integration includes its brand images in `custom_components/klikaanklikuit/brand`. The HACS documentation also requires the integration to be present in Home Assistant Brands for default catalog inclusion. The proposed assets and submission text are in `publication/brands`.

The default catalog change is one entry in the alphabetically sorted `integration` list at `hacs/default`:

```json
"Otte-S/KlikAanKlikUit-HomeAssistant"
```

Create the submission from the repository owner's personal GitHub account. Use a branch created from `hacs/default`'s `master` branch and allow maintainer edits. The submission text is in `publication/hacs-default-pr.md`.

Catalog publication depends on the external repositories accepting their pull requests. A passing validation workflow does not mean the catalog submission has been accepted.

## Existing installations using the old repository

The retired URL is `Otte-S/KlikAanKlikUit-HA`. Replace that repository in HACS with `Otte-S/KlikAanKlikUit-HomeAssistant`. Preserve the configured integration in Home Assistant, download the current version, restart and verify its entities.

## Verification record

The regression suite targets Home Assistant 2026.9.3, 2026.10.1 and 2026.10.4 with Python 3.14. Physical ICS-2000 command delivery and ECO-DIM.07 behavior require the hardware checks above. The experimental momentary input sensors do not provide guaranteed press events.
