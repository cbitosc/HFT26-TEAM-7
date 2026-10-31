"""Refresh the 50-row synthetic prediction fixture from the real subset."""
from pathlib import Path
import json
import random

import pandas as pd

SEED = 42

def main() -> None:
    source = pd.read_csv("data/master.csv", keep_default_na=False).head(50).copy()
    rng = random.Random(SEED)
    for i, row in source.iterrows():
        truth = str(row.get("gt_species", "empty"))
        empty = truth.lower() == "empty"
        status = "Empty" if empty else rng.choices(["Identified", "Uncertain", "Needs Review"], [0.68, 0.22, 0.10])[0]
        source.at[i, "blur_score"] = round(rng.uniform(18, 240), 2)
        source.at[i, "status"] = status
        source.at[i, "md_conf"] = "" if empty else round(rng.uniform(0.55, 0.99), 3)
        source.at[i, "bbox"] = "" if empty else json.dumps([round(rng.uniform(0, 0.5), 3), round(rng.uniform(0, 0.4), 3), round(rng.uniform(0.3, 0.5), 3), round(rng.uniform(0.3, 0.5), 3)])
        source.at[i, "species"] = "empty" if empty else truth
        source.at[i, "species_conf"] = "" if empty else round(rng.uniform(0.45, 0.99), 3)
    output = Path("data/fake_master.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    source.to_csv(output, index=False)
    print(f"Wrote {len(source)} synthetic prediction rows to {output}")


if __name__ == "__main__":
    main()
