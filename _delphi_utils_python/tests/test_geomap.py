import pytest
import os
import pandas as pd
import numpy as np
from delphi_utils.geomap import GeoMapper


class TestGeoMapper:
    unique_zips = 33099
    fips_data = pd.DataFrame({
        "fips":[1123,2340,98633,18181],
        "num": [2,0,20,10021],
        "den": [4,0,400,100001]
    })
    fips_data_2 = pd.DataFrame({
        "fips":[1123,2340,2002,18633,18181],
        "date":[pd.Timestamp('2018-01-01')]*5,
        "num": [2,1,20,np.nan,10021],
        "den": [4,1,400,np.nan,100001]
    })
    fips_data_3 = pd.DataFrame({
        "fips":[48059, 48253, 48441, 72003, 72005],
        "date": [pd.Timestamp('2018-01-01')]*3 + [pd.Timestamp('2018-01-03')]*2,
        "num": [1,2,3,4,8],
        "den": [2,4,7,11,100]
    })
    zip_data = pd.DataFrame({
        "zip":[45140,95616,95618]*2,
        "date": [pd.Timestamp('2018-01-01')]*3 + [pd.Timestamp('2018-01-03')]*3,
        "count": [99,345,456,100,344,442]
    })
    zip_data["total"] = zip_data["count"] * 2
    jan_month = pd.bdate_range('2018-01-01','2018-02-01')
    mega_data = pd.concat((
        pd.DataFrame({
        'fips': [1001]*len(jan_month),
        'date': jan_month,
        'count': np.arange(len(jan_month)),
        'visits': np.arange(len(jan_month)),
        }),
        pd.DataFrame({
            'fips': [1002]*len(jan_month),
            'date': jan_month,
            'count': np.arange(len(jan_month)),
            'visits': 2*np.arange(len(jan_month)),
        })))

    def test_load_zip_fips_cross(self):
        gmpr = GeoMapper()
        gmpr.load_zip_fips_cross()
        fips_data = gmpr.zip_fips_cross
        assert tuple(fips_data.columns) == ('zip', 'fips', 'weight')
        assert len(pd.unique(fips_data['zip'])) == self.unique_zips
        assert tuple(fips_data.dtypes) == (('object','object','float64'))

    def test_load_state_cross(self):
        gmpr = GeoMapper()
        gmpr.load_state_cross()
        state_data = gmpr.stcode_cross
        assert tuple(state_data.columns) == ('st_code', 'state_id', 'state_name')
        assert state_data.shape[0] == 52

    def test_load_fips_msa_cross(self):
        gmpr = GeoMapper()
        gmpr.load_fips_msa_cross()
        msa_data = gmpr.fips_msa_cross
        assert tuple(msa_data.columns) == ('fips','msa')

    def test_convert_intfips_to_str(self):
        gmpr = GeoMapper()
        new_data = gmpr.convert_intfips_to_str(self.fips_data)
        assert new_data['fips'].dtype=='O'
        assert new_data.shape == self.fips_data.shape

    def test_convert_fips_to_stcode(self):
        gmpr = GeoMapper()
        new_data = gmpr.convert_fips_to_stcode(self.fips_data)
        assert new_data['st_code'].dtype=='O'
        assert new_data.loc[1,"st_code"] == new_data.loc[1,"fips"][:2]

    def test_convert_stcode_to_state_id(self):
        gmpr = GeoMapper()
        new_data = gmpr.convert_fips_to_stcode(self.fips_data)
        new_data = gmpr.convert_stcode_to_state_id(new_data)
        assert new_data['state_id'].isnull()[2] == True
        assert new_data['state_id'][3] == 'IN'
        new_data = gmpr.convert_fips_to_stcode(self.fips_data)
        new_data = gmpr.convert_stcode_to_state_id(new_data,full=True)
        assert len(pd.unique(new_data['state_id'])) == 53

    def test_convert_fips_to_state_id(self):
        gmpr = GeoMapper()
        new_data = gmpr.convert_fips_to_state_id(self.fips_data)
        assert new_data['state_id'].isnull()[2] == True
        assert new_data['state_id'][3] == 'IN'

    def test_county_to_state(self):
        gmpr = GeoMapper()
        new_data = gmpr.county_to_state(self.fips_data_2)
        assert new_data.shape[0] == 3

    def test_convert_fips_to_msa(self):
        gmpr = GeoMapper()
        new_data = gmpr.convert_fips_to_msa(self.fips_data_3)
        assert new_data['msa'][2] == "10180"

    def test_county_to_msa(self):
        gmpr = GeoMapper()
        new_data = gmpr.county_to_msa(self.fips_data_3)
        assert new_data.shape[0] == 2
        assert new_data[['num']].sum()[0] == self.fips_data_3['num'].sum()

    def test_convert_zip_to_fips(self):
        gmpr = GeoMapper()
        new_data = gmpr.convert_zip_to_fips(self.zip_data)
        assert new_data.shape[0] == 12
        assert (new_data.groupby('zip').sum()['weight'] == 2).sum() == 3

    def test_zip_to_county(self):
        gmpr = GeoMapper()
        new_data = gmpr.zip_to_county(self.zip_data)
        assert new_data.shape[0] == 10
        assert (new_data[['count','total']].sum()-self.zip_data[['count','total']].sum()).sum() < 1e-3

    def test_megacounty_creation(self):
        gmpr = GeoMapper()
        new_data = gmpr.county_to_megacounty(self.mega_data,6,50)
        assert (new_data[['count','visits']].sum()-self.mega_data[['count','visits']].sum()).sum() < 1e-3
