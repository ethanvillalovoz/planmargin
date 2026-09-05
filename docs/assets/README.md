# README screenshot provenance

`planmargin-new-experiment.png` is an unmodified screenshot captured September 5,
2026, from the current working implementation's first-run form. A separate
clean checkout installed the locked dependencies and ran
`planmargin-prepare-planning --accept-waymo-terms` against the authorized source.
Its actual planning-only API served readiness; no results were prepopulated.
The browser forwarded API traffic to that checkout's local port without changing
responses. The capture contains no scene geometry, source identifiers, or token.
No image generation or page-content injection was used.

`planmargin-test-health.png` and `planmargin-models.png` are unmodified full-page
screenshots of the running frontend at implementation revision
`987434d811b84d18e94e41ecceb463939fb16861`, captured on September 4, 2026.

Both were captured from `http://localhost:4200` without a local evidence session.
They show public aggregate records already bundled in the repository:

- Test health: saved campaign checks and held engineering decisions; not live
  fleet monitoring.
- Models: a prediction study, baseline comparison, and reproduction links;
  not the controller used by the planning campaign.

No page content was injected, no API responses were mocked, and no image
generation was used. These captures contain no licensed scene geometry,
camera frames, trajectories, source identifiers, or credentials.

The older versioned PNGs here are historical assets, not current README images.
