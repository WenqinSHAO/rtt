# RTT summary for ping and traceroute
This document explains how we summarized the RTT measurements for each probe.

## Usage
```
$ python rtt_summary.py
```
The script will read the [config](../config) and measuremet files in [data/](../data/).
It logs the events during calculation in [rtt_summary.log](../rtt_summary) for debugging usages.

## Output
For each measurement id configured in [config](../config), a csv file in the name __rtt_summary_msmid_of_v4/v6.csv__ is generated.
It is a comma ';' separated plain text file providing following columns for each probe:
```
probe_id  raw_length  valid_length  mean           median       min         max         std
10048     33116       31740         157.772612898  155.777885   141.84706   222.35416   7.95685860581
10004     11345       11338         159.789841562  159.41579    143.74512   260.497675  9.10298905283
10007     33074       32997         25.7094228698  24.07242     20.03542    884.554335  18.4515560226
10003     29369       29340         158.042404034  160.1365925  140.242225  409.685735  12.8858858798
10040     27601       26966         179.775035067  176.786785   172.045775  868.60965   27.477574097
10009     33013       32958         18.142862694   17.4679075   12.480995   563.41098   6.72373736648
...
```

## Basic cleaning
For ping measurements, we summarized the RTT using the mininum of the 3 tentatives.
And we only account those positive values that are inferior to 1000ms.
1000ms is the default timeout setting for built-in ping measurements.
Still there are times that obtained ping can largly surpass this limit, till several seconds.
The presence of such extremely large value will severely distort of interpretation of RTT measurements.
The __valid_length__ column in output csv file records the actual number of RTT data taken into consideration in 
calculating mean, median, etc...

For traceroute, we first check if the measurement reaches the destination and then apply the same criteria for ping to
retain the meaningful last hop RTTs.

## Visualization and basic exploration
[R/explorer.R](../R/explorer.R) provides some code to visualize the results of RTT summarization and
compares the RTTs obtained from ping and traceroute.