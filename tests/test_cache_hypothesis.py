# tests/test_cache_hypothesis.py
from hypothesis import assume, given
from hypothesis import strategies as st

from seriesoftubes.cache.keys import hash_dict


@given(
    data=st.dictionaries(
        keys=st.text(min_size=1),
        values=st.one_of(
            st.integers(),
            st.floats(allow_nan=False),
            st.text(),
            st.booleans(),
            st.none(),
        ),
    )
)
def test_hash_dict_deterministic(data):
    """Same dict should always produce same hash"""
    hash1 = hash_dict(data)
    hash2 = hash_dict(data)
    assert hash1 == hash2


@given(
    dict1=st.dictionaries(st.text(), st.integers()),
    dict2=st.dictionaries(st.text(), st.integers()),
)
def test_hash_dict_collision_resistance(dict1, dict2):
    """Different dicts should produce different hashes (with high probability)"""
    assume(dict1 != dict2)  # Only test different dicts

    hash1 = hash_dict(dict1)
    hash2 = hash_dict(dict2)

    # This might fail with extremely low probability (hash collision)
    # but it's astronomically unlikely with a good hash function
    assert hash1 != hash2


@given(
    keys=st.lists(st.text(min_size=1), min_size=1, max_size=5),
    values=st.lists(st.integers(), min_size=1, max_size=5),
)
def test_dict_order_independence(keys, values):
    """Dict hash should be independent of insertion order"""
    assume(len(keys) == len(values))
    assume(len(set(keys)) == len(keys))  # Unique keys

    # Create dict in different orders
    items = list(zip(keys, values, strict=False))
    dict1 = dict(items)
    dict2 = dict(reversed(items))

    assert hash_dict(dict1) == hash_dict(dict2)
