# Tasks: Market risk opportunity scanner

- [ ] Define a deterministic market-risk basket (ES/NQ/VX + DXY)
- [ ] Add `universe=market_risk` selector for multi-asset overlays (or document explicit `--pairs` workflow)
- [x] Ensure `--pipeline data` then `--pipeline analytics --matrix` works via Prefect runner
- [x] Choose proxy symbols that populate `Recommend.*|{tf}` and `Roc|{tf}`
- [ ] Document how to use the scan as a risk overlay for forex/crypto opportunities
