% Generated by roxygen2: do not edit by hand
% Please edit documentation in R/aggregate.R
\name{aggregate_indicators}
\alias{aggregate_indicators}
\title{Produce aggregates for all indicators.}
\usage{
aggregate_indicators(df, indicators, cw_list, params)
}
\arguments{
\item{df}{Data frame of individual response data.}

\item{indicators}{Data frame with columns `name`, `var_weight`, `metric`,
`smooth_days`, `compute_fn`, `post_fn`. Each row represents one indicator
to report. `name` is the indicator's API name; `var_weight` is the column
to use for its weights; `metric` is the column of `df` containing the
response value. `smooth_days` determines how many days to aggregate to
produce one day of responses. `compute_fn` is the function that computes
the aggregate response given many rows of data. `post_fn` is applied to the
aggregate data after megacounty aggregation, and can perform any final
calculations necessary.}

\item{cw_list}{Named list of geographic crosswalks, each of which maps a zip5
to a geographic level such as county or state. Aggregates will be produced
for each geographic level.}

\item{params}{Named list of configuration parameters.}
}
\description{
Writes the outputs directly to CSVs in the directory specified by `params`.
Produces output for all available days between `params$start_date -
params$backfill_days` and `params$end_date`, inclusive. (We re-output days
before `start_date` in case there was backfill for those days.)
}
\details{
Warning: The maximum value of `smooth_days` needs to be accounted for in
`run.R` in the `lead_days` argument to `filter_data_for_aggregation`, so
the correct amount of archived data is included, plus the expected backfill
length.
}
