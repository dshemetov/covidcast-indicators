# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd


def pull_jhu_data(base_url: str, metric: str, pop_df: pd.DataFrame) -> pd.DataFrame:
    """Pulls the latest Johns Hopkins CSSE data, and conforms it into a dataset

    The output dataset has:

    - Each row corresponds to (County, Date), denoted (FIPS, timestamp)
    - Each row additionally has a column `new_counts` corresponding to the new
      new_counts (either `confirmed` cases or `deaths`), and a column
      `cumulative_counts`, correspond to the aggregate metric from January 22nd
      (as of April 27th) until the latest date.

    Note that the raw dataset gives the `cumulative_counts` metric, from which
    we compute `new_counts` by taking first differences.  Hence, `new_counts`
    may be negative.  This is wholly dependent on the quality of the raw
    dataset.

    We filter the data such that we only keep rows with valid FIPS, or "FIPS"
    codes defined under the exceptions of the README.  The current  exceptions
    include:

    - 70002: Dukes County and Nantucket County in Massachusetts, which are
      reported together
    - 70003: Kansas City, Missouri, which reports counts separately from the
      four counties it intesects (Platte, Cass, Clay, Jackson Counties)

    Parameters
    ----------
    base_url: str
        Base URL for pulling the JHU CSSE data
    metric: str
        One of 'confirmed' or 'deaths'.
    pop_df: pd.DataFrame
        Read from static file "fips_population.csv".

    Returns
    -------
    pd.DataFrame
        Dataframe as described above.
    """
    # Constants
    DROP_COLUMNS = [
        "UID",
        "iso2",
        "iso3",
        "code3",
        "Admin2",
        "Province_State",
        "Country_Region",
        "Lat",
        "Long_",
        "Combined_Key",
        "FIPS",
    ]
    # Two metrics, two schema...
    if metric == "deaths":
        DROP_COLUMNS.append("Population")
    MIN_FIPS = 1000
    MAX_FIPS = 57000
    EXTRA_FIPS = (
        70002,  # Kansas City, MO
        70003,  # Dukes and Nantucket Counties, MA
    )
    # Read data
    df = pd.read_csv(base_url.format(metric=metric))
    # FIPS are missing for some nonstandard FIPS
    null_mask = pd.isnull(df["FIPS"])
    df.loc[null_mask, "FIPS"] = df.loc[null_mask, "UID"].apply(
        lambda x: float(str(x)[3:])
    )
    df = df[
        (
            (df["FIPS"] >= MIN_FIPS)  # US non-state territories
            & (df["FIPS"] < MAX_FIPS)
        )  # "Uncategorized", etc.
        | df["FIPS"].isin(EXTRA_FIPS)
    ]
    # Merge in population LOWERCASE, consistent across confirmed and deaths
    df = pd.merge(df, pop_df, on="FIPS")

    # Conform FIPS
    df["fips"] = df["FIPS"].apply(lambda x: f"{int(x):05d}")
    # Drop unnecessary columns (state is pre-encoded in fips)
    try:
        df.drop(DROP_COLUMNS, axis=1, inplace=True)
    except KeyError as e:
        raise ValueError(
            "Tried to drop non-existent columns. The dataset "
            "schema may have changed.  Please investigate and "
            "amend DROP_COLUMNS."
        )
    # Check that columns are either FIPS or dates
    try:
        columns = list(df.columns)
        columns.remove("fips")
        columns.remove("population")
        # Detects whether there is a non-date string column -- not perfect
        _ = [int(x.replace("/", "")) for x in columns]
    except ValueError as e:
        print(e)
        raise ValueError(
            "Detected unexpected column(s) "
            "after dropping DROP_COLUMNS. The dataset "
            "schema may have changed. Please investigate and "
            "amend DROP_COLUMNS."
        )
    # Reshape dataframe
    df = df.melt(
        id_vars=["fips", "population"],
        var_name="timestamp",
        value_name="cumulative_counts",
    )
    # timestamp: str -> datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    # Add a dummy first row here on day before first day
    min_ts = min(df["timestamp"])
    df_dummy = df.loc[df["timestamp"] == min_ts].copy()
    df_dummy.loc[:, "timestamp"] = min_ts - pd.Timedelta(days=1)
    df_dummy.loc[:, "cumulative_counts"] = 0
    df = pd.concat([df_dummy, df])
    # Obtain new_counts
    df.sort_values(["fips", "timestamp"], inplace=True)
    df["new_counts"] = df["cumulative_counts"].diff()  # 1st discrete difference
    # Handle edge cases where we diffed across fips
    mask = df["fips"] != df["fips"].shift(1)
    df.loc[mask, "new_counts"] = np.nan
    df.reset_index(inplace=True, drop=True)

    # Final sanity checks
    days_by_fips = df.groupby("fips").count()["cumulative_counts"].unique()
    unique_days = df["timestamp"].unique()
    # each FIPS has same number of rows
    if (len(days_by_fips) > 1) or (days_by_fips[0] != len(unique_days)):
        raise ValueError("Differing number of days by fips")
    min_timestamp = min(unique_days)
    max_timestamp = max(unique_days)
    n_days = (max_timestamp - min_timestamp) / np.timedelta64(1, "D") + 1
    if n_days != len(unique_days):
        raise ValueError(
            f"Not every day between {min_timestamp} and "
            "{max_timestamp} is represented."
        )
    return df.loc[
        df["timestamp"] >= min_ts,
        [  # Reorder
            "fips",
            "timestamp",
            "population",
            "new_counts",
            "cumulative_counts",
        ],
    ]
