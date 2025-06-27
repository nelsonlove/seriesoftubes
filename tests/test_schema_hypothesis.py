# tests/test_schema_hypothesis.py
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from seriesoftubes.schemas import FilterNodeInput, TransformNodeOutput


# Generate various input types to test schema validation
@given(
    items=st.one_of(
        st.lists(st.integers()),
        st.lists(st.text()),
        st.lists(st.dictionaries(st.text(), st.integers())),
        st.none(),
        st.integers(),  # Invalid type
        st.text(),  # Invalid type
    ),
    filter_context=st.dictionaries(st.text(), st.integers()),
)
def test_filter_input_validation(items, filter_context):
    """Test that FilterNodeInput properly validates various inputs"""
    if isinstance(items, list):
        # Should succeed with list input
        inp = FilterNodeInput(items=items, filter_context=filter_context)
        assert inp.items == items
    else:
        # Should fail with non-list input
        with pytest.raises(ValidationError):
            FilterNodeInput(items=items, filter_context=filter_context)
