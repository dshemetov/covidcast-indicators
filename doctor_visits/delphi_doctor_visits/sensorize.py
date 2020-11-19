"""
Sensorizer class to convert an indicator into a sensor.
Uses univariate linear regression from indicator to target.

Author: Aaron Rumack
Created: 2020-11-11

"""

import logging

# third party
import numpy as np
import pandas as pd
from sklearn import linear_model
from datetime import timedelta

# first party
from .config import Config

class Sensorizer:
    """Sensorizer class to convert indicator into a sensor.
    """

    @staticmethod
    def linear_regression_coefs(
            grouped_df,
            signal_col="signal",
            target_col="target"):
        """
        Calculate linear regression coefficients for a grouped df.
        For each group, calculate slope as cov(x,y)/var(x) and
        intercept as mean(y) - slope*mean(x).

        Args:
            grouped_df: Grouped DataFrame, calculation to be done
                        for each group
            signal_col: column name of covariate
            target_col: column name of response

        Returns:
            DataFrame with columns for groups, and
            "b1": slope of regression, and
            "b0": intercept of regression
        """

        signal_mean = signal_col + "_mean"
        target_mean = target_col + "_mean"
        signal_var = signal_col + "_var"

        # ddof=1 to divide by N-1, see note below
        cov_df = grouped_df.apply(
                    lambda x: x[signal_col].cov(x[target_col],ddof=1))
        cov_df = cov_df.reset_index().rename(columns={0: "cov"})

        # Bug in pandas makes it impossible to calculate var divided by N,
        # always divides by N-1 even though np.var divides by N
        var_df = grouped_df.apply(np.var).reset_index()
        var_df = var_df.rename(
            columns={signal_col:signal_var}).drop(target_col,axis=1)
        means_df = grouped_df.agg(np.mean).reset_index()
        means_df = means_df.rename(
            columns={signal_col: signal_mean, target_col:target_mean})

        fit_df = cov_df.merge(var_df).merge(means_df)
        fit_df["b1"] = fit_df["cov"] / fit_df[signal_var]
        fit_df["b0"] = \
            fit_df[target_mean]-fit_df["b1"]*fit_df[signal_mean]
        fit_df = fit_df.drop(
            ["cov",signal_mean,target_mean,signal_var],axis=1)
        return fit_df


    @staticmethod
    def sensorize(
            signal,
            target,
            signal_geo_col,
            signal_time_col,
            signal_val_col,
            target_geo_col,
            target_time_col,
            target_val_col,
            window_start=Config.SENSOR_WINDOW_START,
            window_end=Config.SENSOR_WINDOW_END,
            global_weights=None):
        """
        Sensorize a signal to correct for spatial heterogeneity. For each
         date, use linear regression to fit target to signal globally (f) and
         fit signal to target locally (g_i). Output sensorized signal as
         f(g_i(signal)).

        Args:
            signal: DataFrame with signal values to be sensorized
            target: DataFrame with target observations for sensor fit
            {signal,target}_geo_col: name of location column in DataFrame
            {signal,target}_time_col: name of time column in DataFrame
            {signal,target}_val_col: name of value column in DataFrame
            window_start: Number of days before fit date at which to begin
                          training, inclusive
                          Positive integer
            window_end: Number of days before fit date at which to end
                        training, exclusive
                        Positive integer, greater than window_start
            global_weights: DataFrame with weights to create global signal
                            and global target, with columns signal_geo_col
                            and "weight"

        Returns:
            DataFrame with signal_geo_col, signal_time_col, and signal_val_col
            Values in signal_val_col are sensorized

        """

        logging.info("Sensorizing")
        target = target.rename(columns={
                                target_time_col:signal_time_col,
                                target_geo_col:signal_geo_col,
                                target_val_col:"target"})
        signal = signal.rename(columns={signal_val_col:"signal"})
        merged = pd.merge(signal,target,on=[signal_time_col,signal_geo_col],how="left")
        merged.sort_values([signal_time_col, signal_geo_col]).reset_index()

        unique_times = pd.to_datetime(merged[signal_time_col].unique())
        sliding_window_df = 0
        flag = False
        sensor_time_col = "sensor" + signal_time_col
        for i in range(len(unique_times)):
            if not flag:
                sliding_window_df = pd.DataFrame(data={
                    signal_time_col:pd.date_range(unique_times[i]-timedelta(days=window_end)+1,
                            unique_times[i]-timedelta(days=window_start)),
                    sensor_time_col:unique_times[i]})
                flag = True
            else:
                tmp_df = pd.DataFrame(data={
                    signal_time_col:pd.date_range(unique_times[i]-timedelta(days=window_end)+1,
                            unique_times[i]-timedelta(days=window_start)),
                    sensor_time_col:unique_times[i]})
                sliding_window_df = sliding_window_df.append(tmp_df)

        sliding_window_df = pd.merge(merged,sliding_window_df)
        # Local fits from signal (covariate) to target (response)
        grouped = sliding_window_df[[signal_geo_col,sensor_time_col,"signal","target"]]
        grouped = grouped.groupby([signal_geo_col,sensor_time_col])

        local_fit_df = Sensorizer.linear_regression_coefs(grouped, "signal", "target")
        local_fit_df = local_fit_df.reset_index()
        local_fit_df = local_fit_df.rename(
            columns={"b1":"local_b1","b0":"local_b0",sensor_time_col:signal_time_col})

        # Global fits from target (covariate) to signal (response)
        grouped = sliding_window_df[[signal_geo_col,signal_time_col,sensor_time_col,"signal","target"]]
        if global_weights is None:
            global_weights = pd.DataFrame(data={signal_geo_col:grouped[signal_geo_col].unique(),"weight":1})
            global_weights.weight = global_weights.weight/global_weights.weight.sum()
            grouped = grouped.merge(global_weights)
            grouped["signal_wt"] = grouped.weight * grouped.signal
            grouped["target_wt"] = grouped.weight * grouped.target
            grouped = grouped.groupby([signal_time_col,sensor_time_col]).agg(np.sum).reset_index()
            grouped = grouped[[signal_time_col,sensor_time_col,"signal_wt","target_wt"]]
            grouped = grouped.rename(columns={"signal_wt":"signal","target_wt":"target"})
            
        grouped = grouped.groupby(sensor_time_col)

        global_fit_df = Sensorizer.linear_regression_coefs(grouped, "target", "signal")
        global_fit_df = global_fit_df.reset_index()
        global_fit_df = global_fit_df.rename(
            columns={"b1":"global_b1","b0":"global_b0",sensor_time_col:signal_time_col})

        combined_df = pd.merge(merged,global_fit_df,on=[signal_time_col],how="left")
        combined_df = pd.merge(combined_df,local_fit_df,on=[signal_time_col,signal_geo_col],how="left")
        
        # First, calculate estimate in target space
        combined_df["sensor"] = combined_df["signal"]*combined_df["local_b1"] + combined_df["local_b0"]
        # Second, scale back into signal space
        combined_df["sensor"] = combined_df["sensor"]*combined_df["global_b1"] + combined_df["global_b0"]
        # Where we could not fit regression coefficients, use original signal
        combined_df.sensor = combined_df["sensor"].fillna(combined_df["signal"])
        bad_fit = (combined_df.sensor < 0) | (combined_df.sensor > 1)
        combined_df.loc[bad_fit,"sensor"] = combined_df.loc[bad_fit,"signal"]

        combined_df.to_csv("combined_df.csv",index=False)

        result = combined_df[[signal_geo_col,signal_time_col,"sensor"]]
        result = result.rename(columns={"sensor":signal_val_col})
        return result
