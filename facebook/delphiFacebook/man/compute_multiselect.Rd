% Generated by roxygen2: do not edit by hand
% Please edit documentation in R/contingency_calculate.R
\name{compute_multiselect}
\alias{compute_multiselect}
\title{Multiselect wrapper for `compute_binary`}
\usage{
compute_multiselect(response, weight, sample_size, total_represented)
}
\arguments{
\item{response}{a vector of binary (0 or 1) responses}

\item{weight}{a vector of sample weights for inverse probability weighting;
invariant up to a scaling factor}

\item{sample_size}{The sample size to use, which may be a non-integer (as
responses from ZIPs that span geographical boundaries are weighted
proportionately, and survey weights may also be applied)}

\item{total_represented}{Number of people represented in sample, which may
be a non-integer}
}
\value{
a list of named percentages and other descriptive statistics
}
\description{
Multiselect wrapper for `compute_binary`
}
