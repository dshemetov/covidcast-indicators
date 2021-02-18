# -*- coding: utf-8 -*-
"""Functions to call when running the function.

This module should contain a function called `run_module`, that is executed
when the module is run with `python -m MODULE_NAME`.
"""
import time as t
from datetime import datetime, date, time, timedelta
from itertools import product
from typing import Dict, Any

import pandas as pd
import numpy as np
from delphi_utils import (
    create_export_csv,
    get_structured_logger,
    S3ArchiveDiffer,
    Smoother,
    Nans
)

from .geo import geo_map
from .pull import pull_usafacts_data

# global constants
METRICS = [
    "confirmed",
    "deaths",
]
SENSORS = [
    "new_counts",
    "cumulative_counts",
    "incidence",  # new_counts per 100k people
    "cumulative_prop",
]
SMOOTHERS = [
    "unsmoothed",
    "seven_day_average",
]
SENSOR_NAME_MAP = {
    "new_counts":           ("incidence_num", False),
    "cumulative_counts":    ("cumulative_num", False),
    "incidence":            ("incidence_prop", False),
    "cumulative_prop":      ("cumulative_prop", False),
}
# Temporarily added for wip_ signals
# WIP_SENSOR_NAME_MAP = {
#     "new_counts":           ("incid_num", False),
#     "cumulative_counts":    ("cumul_num", False),
#     "incidence":            ("incid_prop", False),
#     "cumulative_prop":      ("cumul_prop", False),
# }

SMOOTHERS_MAP = {
    "unsmoothed": (Smoother("identity"), "", False, lambda d: d - timedelta(days=7)),
    "seven_day_average": (Smoother("moving_average", window_length=7), "7dav_", True, lambda d: d),
}
GEO_RESOLUTIONS = [
    "county",
    "state",
    "msa",
    "hrr",
    "hhs",
    "nation"
]


def add_nancodes(df, smoother):
    """Add nancodes to the dataframe."""
    idx = pd.IndexSlice

    # Default nancodes
    df["missing_val"] = Nans.NOT_MISSING
    df["missing_se"] = Nans.NOT_APPLICABLE
    df["missing_sample_size"] = Nans.NOT_APPLICABLE

    # Mark early smoothing entries as data insufficient
    if smoother == "seven_day_average":
        df.sort_index(inplace=True)
        min_time_value = df.index.min()[0] + 6 * pd.Timedelta(days=1)
        df.loc[idx[:min_time_value, :], "missing_val"] = Nans.PRIVACY

    # Mark any remaining nans with unknown
    remaining_nans_mask = df["val"].isnull() & (df["missing_val"] == Nans.NOT_MISSING)
    df.loc[remaining_nans_mask, "missing_val"] = Nans.UNKNOWN
    return df


def run_module(params: Dict[str, Dict[str, Any]]):
    """Run the usafacts indicator.

    The `params` argument is expected to have the following structure:
    - "common":
        - "export_dir": str, directory to write output
        - "log_exceptions" (optional): bool, whether to log exceptions to file
        - "log_filename" (optional): str, name of file to write logs
    - "indicator":
        - "base_url": str, URL from which to read upstream data
        - "export_start_date": str, date from which to export data in YYYY-MM-DD format
    - "archive" (optional): if provided, output will be archived with S3
        - "aws_credentials": Dict[str, str], AWS login credentials (see S3 documentation)
        - "bucket_name: str, name of S3 bucket to read/write
        - "cache_dir": str, directory of locally cached data
    """
    start_time = t.time()
    csv_export_count = 0
    oldest_final_export_date = None
    logger = get_structured_logger(
        __name__, filename=params["common"].get("log_filename"),
        log_exceptions=params["common"].get("log_exceptions", True))
    export_start_date = params["indicator"]["export_start_date"]
    if export_start_date == "latest":
        export_start_date = datetime.combine(date.today(), time(0, 0)) - timedelta(days=1)
    else:
        export_start_date = datetime.strptime(export_start_date, "%Y-%m-%d")
    export_dir = params["common"]["export_dir"]
    base_url = params["indicator"]["base_url"]

    if "archive" in params:
        arch_diff = S3ArchiveDiffer(
            params["archive"]["cache_dir"], export_dir,
            params["archive"]["bucket_name"], "usafacts",
            params["archive"]["aws_credentials"])
        arch_diff.update_cache()

    dfs = {metric: pull_usafacts_data(base_url, metric) for metric in METRICS}
    for metric, geo_res, sensor, smoother in product(
            METRICS, GEO_RESOLUTIONS, SENSORS, SMOOTHERS):
        logger.info("generating signal and exporting to CSV",
            geo_res = geo_res,
            metric = metric,
            sensor = sensor,
            smoother = smoother)
        df = dfs[metric]
        # Aggregate to appropriate geographic resolution
        df = geo_map(df, geo_res, sensor)
        df.set_index(["timestamp", "geo_id"], inplace=True)

        # Smooth
        smooth_obj, smoother_prefix, _, smoother_lag = SMOOTHERS_MAP[smoother]
        df["val"] = df[sensor].groupby(level=1).transform(smooth_obj.smooth)

        # USAFacts is not a survey indicator
        df["se"] = np.nan
        df["sample_size"] = np.nan

        df = add_nancodes(df, smoother)

        df.reset_index(inplace=True)
        sensor_name = SENSOR_NAME_MAP[sensor][0]
        # if (SENSOR_NAME_MAP[sensor][1] or is_smooth_wip):
        #     metric = f"wip_{metric}"
        #     sensor_name = WIP_SENSOR_NAME_MAP[sensor][0]
        sensor_name = smoother_prefix + sensor_name
        exported_csv_dates = create_export_csv(
            df,
            export_dir=export_dir,
            start_date=smoother_lag(export_start_date),
            metric=metric,
            geo_res=geo_res,
            sensor=sensor_name,
        )
        if not exported_csv_dates.empty:
            logger.info("Exported CSV",
                csv_export_count = exported_csv_dates.size,
                min_csv_export_date = min(exported_csv_dates).strftime("%Y-%m-%d"),
                max_csv_export_date = max(exported_csv_dates).strftime("%Y-%m-%d"))
            csv_export_count += exported_csv_dates.size
            if not oldest_final_export_date:
                oldest_final_export_date = max(exported_csv_dates)
            oldest_final_export_date = min(
                oldest_final_export_date, max(exported_csv_dates))

    if "archive" in params:
        # Diff exports, and make incremental versions
        _, common_diffs, new_files = arch_diff.diff_exports()

        # Archive changed and new files only
        to_archive = [f for f, diff in common_diffs.items() if diff is not None]
        to_archive += new_files
        _, fails = arch_diff.archive_exports(to_archive)

        # Filter existing exports to exclude those that failed to archive
        succ_common_diffs = {f: diff for f, diff in common_diffs.items() if f not in fails}
        arch_diff.filter_exports(succ_common_diffs)

        # Report failures: someone should probably look at them
        for exported_file in fails:
            print(f"Failed to archive '{exported_file}'")

    elapsed_time_in_seconds = round(t.time() - start_time, 2)
    max_lag_in_days = None
    formatted_oldest_final_export_date = None
    if oldest_final_export_date:
        max_lag_in_days = (datetime.now() - oldest_final_export_date).days
        formatted_oldest_final_export_date = oldest_final_export_date.strftime("%Y-%m-%d")
    logger.info("Completed indicator run",
        elapsed_time_in_seconds = elapsed_time_in_seconds,
        csv_export_count = csv_export_count,
        max_lag_in_days = max_lag_in_days,
        oldest_final_export_date = formatted_oldest_final_export_date)
