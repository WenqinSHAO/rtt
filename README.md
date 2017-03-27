# What is it about
The project aims at first detecting changes in RTT time series using changepoint methods;
and then explore the correlation between RTT changes and path changes.

The best method and configuration for detecting RTT changes are identified through evaluation.
Meanwhile we expose the problem of detecting IP path changes not caused by load balancing for RIPE Atlas built-in traceroute
measurements, where the Paris ID changes over time. Several detection heuristics are proposed.

All the methods proposed in this project, such as scoring method in evaluation, path change detection algorithm, etc., can 
be used in a standalone manner, decoupled from the context of this project.

We provide a dataset of real RTT time series collected form RIPE Atlas, manually labelled with moments of change.
It serves as ground truth in change detection method evaluation.
Tools for manual labelling are available at 
* Visual inspection tool for very long RTT traces [https://github.com/WenqinSHAO/rtt_visual.git](https://github.com/WenqinSHAO/rtt_visual.git).
* Generator of synthetic RTT time series [https://github.com/WenqinSHAO/rtt_gen.git](https://github.com/WenqinSHAO/rtt_gen.git).
 
# Documentations
* [Collect measurements from RIPE Atlas](docs/data_collection.md)
* [Collect auxiliary data](docs/auxiliary_data.md)
* [Summarize RTT characters for each Atlas Probe](docs/rtt_summary.md)
* [Detect IP and AS path changes](docs/path_analysis.md)
* [Detect changes in RTT time series](docs/rtt_cpt.md)
* [Evaluate changepoint detection methods](docs/eval_cpt.md)
* [Correlate RTT changes and path changes](docs/corr.md)
