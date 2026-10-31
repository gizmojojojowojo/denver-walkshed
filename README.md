# Denver Walkshed
Compare three hypothetical pedestrian crossings near East Colfax in Denver. Change the walking budget, choose a crossing, then inspect a Census block's route to an eastbound transit stop. [Open the interactive map](https://denver-walkshed.lucky-dove-8583.chatgpt.site)
 
At ten minutes, the existing modeled network serves 1,666 of 6,004 households. The North Quebec Street scenario adds 18, East 17th Avenue adds 12, and North Oneida Street adds 7. Each scenario is compared separately with the same baseline.

## Run it
Serve the checked-in snapshot with Python 3, then open http://localhost:8000.

```sh
python3 -m http.server 8000 --directory dist
```

Run `node verify.mjs` for route and count checks. To regenerate the snapshot, run `python3 scripts/build_snapshot.py`. A browser runs multi-source Dijkstra over the local network. It traces the selected block's route to one of six stops and includes its distance to the sidewalk in the walking budget.

## Interpretation
Block origins use Census internal points and occupied housing units from 2020. The map combines those counts with a city sidewalk and bus-stop inventory. Candidate links require field verification. The calculation assumes a constant pace and omits crossing delays, construction costs, and accessibility barriers. Read [data, attribution, and methods](DATA.md) before interpreting an individual location.
