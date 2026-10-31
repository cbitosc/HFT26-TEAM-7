# encounter_count.R - independent events via 30-minute gap rule.
# Reads data/processed/detections_for_r.csv, writes data/processed/encounters.csv
# (run from the project root; encounter.py sets the working directory)
suppressPackageStartupMessages({ library(dplyr); library(lubridate) })

df <- read.csv("data/processed/detections_for_r.csv", stringsAsFactors = FALSE)
df$datetime <- ymd_hms(df$datetime, quiet = TRUE)
df <- df %>% filter(!is.na(datetime))

df <- df %>%
  arrange(location_id, species_common, datetime) %>%
  group_by(location_id, species_common) %>%
  mutate(gap = as.numeric(difftime(datetime, lag(datetime), units = "mins")),
         new_event = is.na(gap) | gap > 30,
         event_id = cumsum(new_event)) %>%
  ungroup()

events <- df %>%
  group_by(location_id, species_common, event_id) %>%
  summarise(event_start = min(datetime), event_end = max(datetime),
            image_count = n(), .groups = "drop")

effort <- df %>%
  group_by(location_id) %>%
  summarise(trap_nights = as.numeric(difftime(max(datetime), min(datetime), units = "days")),
            .groups = "drop")

events <- left_join(events, effort, by = "location_id")
events$event_start <- format(events$event_start, "%Y-%m-%d %H:%M:%S")
events$event_end   <- format(events$event_end,   "%Y-%m-%d %H:%M:%S")

write.csv(events[, c("location_id", "species_common", "event_start", "event_end",
                     "image_count", "trap_nights")],
          "data/processed/encounters.csv", row.names = FALSE)
cat(sprintf("Wrote %d encounter events\n", nrow(events)))
