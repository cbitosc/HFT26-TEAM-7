# Camera-trap dashboard data

Subset generated with seed 42 from the provided CCT annotation files. It contains 2500 images. This is a convenience subset across all provided split files; split membership is not exported to the master contract. Sequences are retained as metadata but may be partially sampled.

## Subset summary

- Images: 2500
- Empty: 640 (25.6%)
- Day / night / unknown (day defined as 06:00–17:59 local capture time): 1365 / 1135 / 0
- Missing/unparsed datetimes: 0

### Images per location

- 61: 188
- 120: 188
- 38: 141
- 46: 140
- 100: 135
- 33: 131
- 0: 131
- 115: 124
- 51: 121
- 43: 119
- 28: 112
- 7: 111
- 130: 111
- 88: 111
- 108: 110
- 125: 109
- 78: 107
- 40: 107
- 105: 106
- 90: 98

### Ground-truth species counts

- empty: 640
- opossum: 185
- raccoon: 157
- rabbit: 153
- coyote: 140
- squirrel: 139
- cat: 139
- dog: 136
- car: 134
- bobcat: 133
- bird: 128
- skunk: 128
- rodent: 127
- deer: 125
- badger: 28
- fox: 8

## CSV columns

`image_id` is the dataset image ID. `path` is relative to this data folder. `location` is the dataset location ID (not a human-readable site name). `datetime` is the dataset capture time in ISO format. `blur_score`, `status`, `md_conf`, `bbox`, `species`, and `species_conf` are pipeline-owned fields left blank in `master.csv`. `seq_id` and `frame_num` support encounter grouping. `gt_species` is the benchmark ground-truth class, or `empty` when no animal annotation exists.

Allowed `status` values: `Identified`, `Uncertain`, `Needs Review`, `Empty`. Data lead owns image ID, path, location, datetime and ground-truth helper fields; quality/detection fills blur score, status, detector confidence and bounding box; species role fills predicted species and confidence.

`fake_master.csv` contains 50 rows with synthetic model outputs for dashboard development. Its model values are fake; paths, metadata, and ground-truth labels refer to selected real images.

## Limitations and assumptions

The annotation package contains five split JSONs (`train`, `cis_val`, `trans_val`, `cis_test`, `trans_test`). The subset samples across these files and does not preserve benchmark evaluation split isolation. Location is a numeric dataset ID. A frame with no non-empty category annotation is labeled `empty`. Day/night uses capture hour only; unknown timestamps remain unknown. Sequence integrity is not guaranteed because the target size and balancing can select only part of a sequence.

Encounter counting can follow the blueprint: group detections of the same predicted species at the same location when successive detections are within 30 minutes. This is a pandas implementation inspired by the standard workflows in camtraptor and camtrapR; the project does not depend on either R package.
