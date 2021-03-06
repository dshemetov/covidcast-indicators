% Generated by roxygen2: do not edit by hand
% Please edit documentation in R/contingency_aggregate.R
\name{summarize_aggs}
\alias{summarize_aggs}
\title{Perform calculations across all groupby levels for all aggregations.}
\usage{
summarize_aggs(df, crosswalk_data, aggregations, geo_level, params)
}
\arguments{
\item{df}{a data frame of survey responses}

\item{crosswalk_data}{An aggregation, such as zip => county or zip => state,
as a data frame with a "zip5" column to join against.}

\item{aggregations}{Data frame with columns `name`, `var_weight`, `metric`,
`group_by`, `compute_fn`, `post_fn`. Each row represents one aggregate
to report. `name` is the aggregate's base column name; `var_weight` is the
column to use for its weights; `metric` is the column of `df` containing the
response value. `group_by` is a list of variables used to perform the
aggregations over. `compute_fn` is the function that computes
the aggregate response given many rows of data. `post_fn` is applied to the
aggregate data after megacounty aggregation, and can perform any final
calculations necessary.}

\item{geo_level}{a string of the current geo level, such as county or state,
being used}

\item{params}{a named list with entries "s_weight", "s_mix_coef",
"num_filter"}
}
\description{
Perform calculations across all groupby levels for all aggregations.
}
