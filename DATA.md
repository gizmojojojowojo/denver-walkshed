# East Colfax data and methods

The map compares hypothetical street crossings that could shorten a walk to six eastbound East Colfax Avenue bus stop locations in Denver. The October 31, 2026 snapshot covers roughly 2.4 × 2.1 km. It combines Denver pedestrian linework compiled from 2020 imagery, the city's bus stop and street inventories, and 2020 Census housing occupancy. Construction and service changes since the source surveys can affect any route shown.

| Input | Publisher | Use |
| --- | --- | --- |
| [Sidewalk centerlines](https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/ArcGIS/rest/services/ODC_TRANS_SIDEWALKS_L/FeatureServer/143) | City and County of Denver, with regional aerial imagery from DRCOG | Sidewalks, crosswalks, other paved paths and trails |
| [Bus stop inventory](https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/ArcGIS/rest/services/ODC_TRANS_RTDBUSTOPS_P/FeatureServer/281) | RTD, published by City and County of Denver | Modeled stop locations and directions |
| [Street centerlines](https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/ArcGIS/rest/services/ODC_TRANS_STREET_L/FeatureServer/145) | City and County of Denver | Named street segments crossed by hypothetical links |
| [2020 Census blocks](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/10) | U.S. Census Bureau | Block GEOIDs, internal representative points and housing-unit control totals |
| [2020 PL 94-171 Colorado files](https://www2.census.gov/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171/Colorado/) | U.S. Census Bureau | Table H1 supplies occupied housing units by block |

The source publishers retain their dataset terms. Denver supplies its GIS data as-is and excludes engineering use. Published dates and coordinates describe inventory snapshots. Consult current RTD information for actual service.

## How the estimate works

1. Query intersecting sidewalk segments inside the study envelope from 104.921°W to 104.893°W and 39.731°N to 39.750°N. Convert to local metric coordinates. Preserve shared survey vertices, simplify curves by at most 0.7 m before snapping, subdivide long segments at 25 m, and merge vertices within 0.8 m. This yields an undirected graph with 8,958 nodes and 9,282 unique edges.
2. Select eastbound stops named “Colfax Ave & …” in the Denver inventory. Snap each stop to a pedestrian graph node. The six stop snaps range from 3.1 to 9.7 m. Route distances end at the snapped node.
3. Join 2020 occupied household counts by Census block GEOID through the legacy PL geography file and segment 02. Verify each joined total housing count against TIGERweb and the sum of occupied and vacant units. Place each block's households at its Census internal point. Add its straight-line offset to the nearest sidewalk node to every route distance. Keep inhabited blocks with their internal point inside the envelope and a snap within 150 m. The sample covers 6,004 households across 267 blocks.
4. Run multi-source shortest paths from all stop nodes. Ten minutes at 1.2 m/s gives a 720 m distance budget. For each sampled block inside that threshold, count its occupied units once. The baseline reaches 1,666 households. An unreachable component contributes zero. In this extract, 680 households snap to components without a modeled route to any selected stop.
5. Screen short, approximately perpendicular connections between graph nodes on opposite sides of a named, constructed, ground-level street. The candidate endpoints must already have a finite baseline route. Recompute who falls inside 720 m with a single extra crossing. The selected candidates have distinct streets and are at least 200 m apart. The scenarios were selected for illustrative gains in the default model, so the ranking describes these options only.

| Hypothetical crossing | Added households at 10 minutes | Newly reachable occupied blocks |
| --- | ---: | ---: |
| North Quebec Street | 18 | 1 |
| East 17th Avenue | 12 | 1 |
| North Oneida Street | 7 | 1 |

The Quebec example moves block 1030 in tract 004310 from about 15.8 to 9.6 minutes. That household count represents the location of the whole block. Specific front doors can have different walking distances.

## Limits for interpreting the map

The modeled gap could reflect missing data or a changed crossing. A crew would need to check existing crossings, legal access, geometry, curb ramps, signals, sightlines and right-of-way before deciding whether a project makes sense. The simulator assumes bidirectional travel at constant speed on the retained linework and a direct walk from a block point to its closest sampled sidewalk vertex. It excludes crossing delay, grade, accessibility barriers, cost, ridership and household-level addresses. Routes at the boundary can be longer because the analysis uses a bounded street network. Other bus routes, stops outside the sample and changes after the inventory date also affect real access.

## Rebuild

From the repository root, run the following with Python 3.10 or newer and an internet connection. All dependencies are part of Python's standard library.

```sh
python3 scripts/build_snapshot.py
```

The script downloads public files into a temporary cache, joins and checks the Census records, then writes `dist/corridor.json`. To explicitly select a cache or output use `--cache PATH` or `--out PATH`. A populated cache reproduces its source snapshot. An empty cache retrieves current city inventories, which may change the graph and ranked scenarios. The shipped JSON supports offline analysis and preserves the published snapshot.
