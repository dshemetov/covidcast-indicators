% Generated by roxygen2: do not edit by hand
% Please edit documentation in R/utils.R
\name{megacounty}
\alias{megacounty}
\title{Aggregates counties into megacounties that have low sample size values for a
given day.}
\usage{
megacounty(df_intr, threshold, groupby_vars = c("day", "geo_id"))
}
\arguments{
\item{df_intr}{Input tibble that requires aggregation, with `geo_id`, `val`,
`sample_size`, `effective_sample_size`, and `se` columns.}

\item{threshold}{Sample size value below which counties should be grouped
into megacounties.}

\item{groupby_vars}{Character vector of column names to perform `group_by`
over}
}
\value{
Tibble of megacounties. Counties that are not grouped are not
    included in the output.
}
\description{
Aggregates counties into megacounties that have low sample size values for a
given day.
}
