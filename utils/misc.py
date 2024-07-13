from typing import (
    Any,
    Dict,
    TypeVar,
)
KeyType = TypeVar('KeyType')

# https://github.com/pydantic/pydantic/blob/fd2991fe6a73819b48c906e3c3274e8e47d0f761/pydantic/utils.py#L200
def dict_deep_update(mapping: Dict[KeyType, Any], *updating_mappings: Dict[KeyType, Any]) -> Dict[KeyType, Any]:
    updated_mapping = mapping.copy()
    for updating_mapping in updating_mappings:
        for k, v in updating_mapping.items():
            if k in updated_mapping and isinstance(updated_mapping[k], dict) and isinstance(v, dict):
                updated_mapping[k] = dict_deep_update(updated_mapping[k], v)
            else:
                updated_mapping[k] = v
    return updated_mapping

def get_idx_from_bool_series(s):
    return s.index[s]

def get_mmss(ts):
    mm, ss = divmod(ts, 60)
    out = f'{mm:0.0f}:{ss:06.3f}'
    return out

def wrap_trtd(s1,s2):
    return f'<tr><td>{s1}:</td><td style="text-align: left">{s2}</td></tr>'

# Modded with grouping from:
# https://stackoverflow.com/questions/57882621/efficient-merge-overlapping-intervals-in-same-pandas-dataframe-with-start-and-fi/65282946
def merge_overlapping_intervals(df, cols_grp, col_start, col_end, col_tmp_override="merge_overlapping_intervals_tmp_col"):
    df = df[cols_grp + [col_start, col_end]].copy()
    df.sort_values(col_start, inplace=True)
    df[col_tmp_override] = df.groupby(cols_grp)[col_end].shift() + 0.002 # 0.002 is to fix a "bug" where debuff refreshes with 0.001s downtime + floating point rounding error
    df[col_tmp_override] = df.groupby(cols_grp)[col_start].shift(0) > df.groupby(cols_grp)[col_tmp_override].cummax()
    df[col_tmp_override] = df.groupby(cols_grp)[col_tmp_override].cumsum()
    return df.groupby(cols_grp+[col_tmp_override]).agg({col_start:"min", col_end: "max"}).reset_index()[cols_grp+[col_start,col_end]]