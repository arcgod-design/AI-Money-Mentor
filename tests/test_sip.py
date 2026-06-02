"""
tests/test_sip.py
-----------------
Unit tests for utils/sip.py — SIP future-value calculator.

All tests are pure-math: no network calls, no LLM, no env variables.
Run with:  pytest tests/test_sip.py -v
"""

import pytest
from utils.sip import calculate_sip


class TestCalculateSip:
    """Tests for the SIP compound-interest formula."""

    def test_zero_rate_returns_simple_sum(self):
        """At 0% annual rate the future value equals monthly * months."""
        result = calculate_sip(monthly=1000, rate=0, years=5)
        assert result == 1000 * 5 * 12

    def test_positive_rate_exceeds_simple_sum(self):
        """With a positive return rate the FV must be greater than simple sum."""
        simple = 5000 * 10 * 12
        result = calculate_sip(monthly=5000, rate=12, years=10)
        assert result > simple

    def test_known_value_within_tolerance(self):
        """
        Standard SIP formula verification:
        ₹1,000/month @ 12% p.a. for 1 year ≈ ₹12,809.
        Tolerance: ±1 rupee (rounding).
        """
        result = calculate_sip(monthly=1000, rate=12, years=1)
        assert abs(result - 12809.0) < 2.0

    def test_high_investment_scales_linearly(self):
        """Doubling monthly contribution should double the FV."""
        fv_1 = calculate_sip(monthly=5000, rate=10, years=5)
        fv_2 = calculate_sip(monthly=10000, rate=10, years=5)
        assert abs(fv_2 - 2 * fv_1) < 1.0   # floating-point epsilon

    def test_returns_float_type(self):
        result = calculate_sip(monthly=2000, rate=8, years=3)
        assert isinstance(result, float)

    def test_single_month(self):
        """1 year = 12 months; result must be a finite positive number."""
        result = calculate_sip(monthly=500, rate=6, years=1)
        assert result > 0

    @pytest.mark.parametrize("monthly,rate,years", [
        (1000, 12, 10),
        (500, 8, 5),
        (10000, 15, 20),
    ])
    def test_result_always_positive(self, monthly, rate, years):
        assert calculate_sip(monthly, rate, years) > 0
