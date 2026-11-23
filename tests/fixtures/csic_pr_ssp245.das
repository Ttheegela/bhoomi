Attributes {
    lat {
        String standard_name "latitude";
        String units "degrees_north";
        String axis "Y";
        String long_name "latitude";
        String bounds "lat_bnds";
        UInt32 _ChunkSizes 180;
    }
    lat_bnds {
        UInt32 _ChunkSizes 180, 2;
    }
    lon {
        String standard_name "longitude";
        String units "degrees_east";
        String axis "X";
        String long_name "longitude";
        String bounds "lon_bnds";
        UInt32 _ChunkSizes 360;
    }
    lon_bnds {
        UInt32 _ChunkSizes 360, 2;
    }
    time {
        String standard_name "time";
        String calendar "standard";
        String units "days since 1850-01-01 00:00:00";
        String axis "T";
        String long_name "time";
        String bounds "time_bnds";
        UInt32 _ChunkSizes 1032;
    }
    time_bnds {
        UInt32 _ChunkSizes 1032, 2;
    }
    member_id {
        String comment "Values uniquely identify each member of the ensemble (<gcm_institution>_<gcm_model>_<gcm_variant>)";
        String standard_name "realization";
        String long_name "Member ID";
        UInt32 _ChunkSizes 32;
    }
    gcm_institution {
        String standard_name "realization";
        String long_name "GCM model institution";
        String comment "Value consists on an identifier for the institution of the GCM";
        UInt32 _ChunkSizes 32;
    }
    gcm_model {
        String standard_name "realization";
        String long_name "GCM model ID";
        String comment "Value consists on an identifier for the GCM model";
        UInt32 _ChunkSizes 32;
    }
    gcm_variant {
        String standard_name "realization";
        String long_name "GCM model variant/member ID";
        String comment "Value consists on an identifier for the GCM member";
        UInt32 _ChunkSizes 32;
    }
    pr {
        Float32 _FillValue -1.7014118E38;
        Int32 least_significant_digit 3;
        String standard_name "lwe_thickness_of_precipitation_amount";
        String units "mm";
        String cell_methods "time: sum within days time: mean over days area: mean";
        String coordinates "member_id time lat lon gcm_institution gcm_model gcm_variant";
        String long_name "Monthly mean of daily accumulated precipitation";
        String comment "Monthly mean of daily accumulated precipitation of liquid water equivalent from all phases";
        Float32 missing_value 1.0384594E34;
        String grid_mapping "crs";
        UInt32 _ChunkSizes 4, 148, 26, 52;
    }
    crs {
        String grid_mapping_name "latitude_longitude";
        Float64 longitude_of_prime_meridian 0.0;
        Float64 semi_major_axis 6378137.0;
        Float64 inverse_flattening 298.257223563;
    }
    NC_GLOBAL {
        String Conventions "CF-1.9 ACDD-1.3";
        String title "IPCC-WGI AR6 Interactive Atlas Dataset";
        String summary "IPCC-WGI AR6 Interactive Atlas dataset: Monthly gridded data from the global (CMIP5, CMIP6) and regional (CORDEX) model projections for the impact-relevant variables and indices included in the IPCC Interactive Atlas (https://interactive-atlas.ipcc.ch).";
        String keywords "CMIP5, CMIP6, CORDEX, IPCC, Interactive Atlas";
        String institution "Instituto de Fisica de Cantabria (IFCA, CSIC-UC, Spain)";
        String contact "ipcc-ddc@ifca.unican.es";
        String license "CC-BY 4.0, https://creativecommons.org/licenses/by/4.0/";
        String project "IPCC-WGI AR6 Atlas";
        String product "ipcc-ar6-interactive-atlas-dataset";
        String product_version "v2.0-final";
        String references "https://doi.org/10.1017/9781009157896.021 https://doi.org/10.1038/s41597-022-01739-y https://doi.org/10.5281/zenodo.5171760 https://doi.org/10.1017/9781009157896.020";
        String standard_name_vocabulary "CF Standard Name Table (Version 79, 2022-03-19)";
        String experiment_id "ssp245";
        String source "CMIP6";
        String frequency "mon";
        String variable_id "pr";
        String time_min "201501";
        String time_max "210012";
        String geospatial_lat_min "-90.0";
        String geospatial_lat_max "90.0";
        String geospatial_lat_resolution "1.0";
        String geospatial_lat_units "degrees_north";
        String geospatial_lon_min "-180.0";
        String geospatial_lon_max "180.0";
        String geospatial_lon_resolution "1.0";
        String geospatial_lon_units "degrees_east";
        String date_created "2022-10-26T00:00:00+00:00";
        String tracking_id "7dff649e-bb71-4995-bcc4-3c8134cb01a7";
    }
}
