# algorithms/tests.py
"""
Unit tests for LifeLink Nepal algorithm functions.

Run with: python manage.py test algorithms

Covers:
- haversine_distance (haversine.py)
- is_compatible, get_compatible_donors, get_compatible_recipients (blood_compatibility.py)
- rank_donors_mcdm (mcdm.py)
- is_donor_eligible (eligibility.py)
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from django.test import TestCase

from algorithms.haversine import haversine_distance, find_nearby_donors, get_donor_distances
from algorithms.blood_compatibility import (
    is_compatible,
    get_compatible_donors,
    get_compatible_recipients,
)
from algorithms.mcdm import rank_donors_mcdm, normalize_matrix
import numpy as np


# ---------------------------------------------------------------------------
# Helpers — lightweight mock objects so tests don't need a real DB
# ---------------------------------------------------------------------------

def make_donor(id, blood_type, donation_count=5,
               last_donation_date=None, latitude=27.71,
               longitude=85.31, is_available=True):
    """Return a simple mock DonorProfile-like object."""
    d = MagicMock()
    d.id = id
    d.blood_type = blood_type
    d.donation_count = donation_count
    d.last_donation_date = last_donation_date or (date.today() - timedelta(days=100))
    d.latitude = latitude
    d.longitude = longitude
    d.is_available = is_available
    return d


def make_request(blood_type, hospital_lat=27.7, hospital_lon=85.3):
    """Return a simple mock BloodRequest-like object."""
    hospital = MagicMock()
    hospital.id = 99
    hospital.latitude = hospital_lat
    hospital.longitude = hospital_lon

    req = MagicMock()
    req.blood_type = blood_type
    req.hospital = hospital
    return req


# ===========================================================================
# 1. HAVERSINE DISTANCE TESTS
# ===========================================================================

class HaversineDistanceTests(TestCase):

    def test_same_point_is_zero(self):
        """Distance from a point to itself must be 0."""
        distance = haversine_distance(27.7, 85.3, 27.7, 85.3)
        print(f"\n[test_same_point_is_zero] result: {distance}")
        self.assertAlmostEqual(distance, 0.0, places=5)

    def test_known_distance_kathmandu_to_pokhara(self):
        """
        Kathmandu (27.7172, 85.3240) to Pokhara (28.2096, 83.9856).
        Known approximate road distance ~200km; straight-line ~140-160km.
        Test that the result is within a reasonable range.
        """
        distance = haversine_distance(27.7172, 85.3240, 28.2096, 83.9856)
        print(f"\n[test_known_distance_kathmandu_to_pokhara] result: {distance} km")
        self.assertGreater(distance, 130)
        self.assertLess(distance, 175)

    def test_short_distance_within_kathmandu(self):
        """Two points within Kathmandu valley should be < 25km."""
        distance = haversine_distance(27.7172, 85.3240, 27.6788, 85.2795)
        print(f"\n[test_short_distance_within_kathmandu] result: {distance} km")
        self.assertGreater(distance, 0)
        self.assertLess(distance, 15)

    def test_returns_float(self):
        """Result should always be a float."""
        result = haversine_distance(27.7, 85.3, 27.8, 85.4)
        print(f"\n[test_returns_float] result: {result} (type: {type(result).__name__})")
        self.assertIsInstance(result, float)

    def test_symmetry(self):
        """Distance A→B must equal distance B→A."""
        d1 = haversine_distance(27.7, 85.3, 28.0, 85.0)
        d2 = haversine_distance(28.0, 85.0, 27.7, 85.3)
        print(f"\n[test_symmetry] A→B: {d1} km, B→A: {d2} km")
        self.assertAlmostEqual(d1, d2, places=8)

    def test_zero_coordinates_are_valid(self):
        """
        Latitude or longitude of 0.0 is a valid coordinate (equator /
        prime meridian). Must NOT be treated as missing and must return
        a real distance rather than raising an error.
        """
        distance = haversine_distance(0.0, 0.0, 0.001, 0.001)
        print(f"\n[test_zero_coordinates_are_valid] result: {distance} km")
        self.assertGreater(distance, 0)
        self.assertLess(distance, 1)


class FindNearbyDonorsTests(TestCase):

    def test_filters_donors_by_max_distance(self):
        """Donors beyond max_distance should not appear in results."""
        close_donor = make_donor(1, 'O+', latitude=27.71, longitude=85.31)
        far_donor = make_donor(2, 'A+', latitude=28.5, longitude=86.5)

        nearby = find_nearby_donors(27.7, 85.3, [close_donor, far_donor], max_distance=25)
        ids = [d.id for d, dist in nearby]
        print(f"\n[test_filters_donors_by_max_distance] nearby donor ids: {ids}")
        print(f"  full results (id, dist): {[(d.id, round(dist,2)) for d, dist in nearby]}")

        self.assertIn(1, ids)
        self.assertNotIn(2, ids)

    def test_sorted_by_distance_closest_first(self):
        """Results must be sorted closest first."""
        d1 = make_donor(1, 'O+', latitude=27.71, longitude=85.31)
        d2 = make_donor(2, 'A+', latitude=27.75, longitude=85.35)

        nearby = find_nearby_donors(27.7, 85.3, [d1, d2], max_distance=50)
        print(f"\n[test_sorted_by_distance_closest_first] order: {[(d.id, round(dist,2)) for d, dist in nearby]}")
        self.assertEqual(nearby[0][0].id, 1)

    def test_empty_donor_list_returns_empty(self):
        """No donors in → empty list out."""
        result = find_nearby_donors(27.7, 85.3, [], max_distance=25)
        print(f"\n[test_empty_donor_list_returns_empty] result: {result}")
        self.assertEqual(result, [])

    def test_donors_without_coordinates_are_skipped(self):
        """Donors with None lat/lon should be skipped silently."""
        no_coords = make_donor(1, 'O+', latitude=None, longitude=None)
        result = find_nearby_donors(27.7, 85.3, [no_coords], max_distance=25)
        print(f"\n[test_donors_without_coordinates_are_skipped] result: {result}")
        self.assertEqual(result, [])


# ===========================================================================
# 2. BLOOD COMPATIBILITY TESTS
# ===========================================================================

class BloodCompatibilityTests(TestCase):

    def test_o_negative_is_universal_donor(self):
        """O- should be compatible with every blood type."""
        all_types = ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']
        results = {r: is_compatible('O-', r) for r in all_types}
        print(f"\n[test_o_negative_is_universal_donor] results: {results}")
        for recipient in all_types:
            with self.subTest(recipient=recipient):
                self.assertTrue(results[recipient], f"O- should be compatible with {recipient}")

    def test_ab_positive_only_donates_to_ab_positive(self):
        """AB+ can only donate to AB+."""
        all_types = ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']
        results = {r: is_compatible('AB+', r) for r in all_types}
        print(f"\n[test_ab_positive_only_donates_to_ab_positive] results: {results}")
        self.assertTrue(results['AB+'])
        for recipient in ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-']:
            with self.subTest(recipient=recipient):
                self.assertFalse(results[recipient])

    def test_o_positive_compatible_recipients(self):
        """O+ can donate to O+, A+, B+, AB+ but NOT to negatives."""
        compatible = ['O+', 'A+', 'B+', 'AB+']
        incompatible = ['O-', 'A-', 'B-', 'AB-']
        results = {r: is_compatible('O+', r) for r in compatible + incompatible}
        print(f"\n[test_o_positive_compatible_recipients] results: {results}")
        for r in compatible:
            self.assertTrue(results[r], f"O+ should be compatible with {r}")
        for r in incompatible:
            self.assertFalse(results[r], f"O+ should NOT be compatible with {r}")

    def test_a_negative_compatible_recipients(self):
        """A- can donate to A-, A+, AB-, AB+."""
        compatible = ['A-', 'A+', 'AB-', 'AB+']
        incompatible = ['O-', 'O+', 'B-', 'B+']
        results = {r: is_compatible('A-', r) for r in compatible + incompatible}
        print(f"\n[test_a_negative_compatible_recipients] results: {results}")
        for r in compatible:
            self.assertTrue(results[r])
        for r in incompatible:
            self.assertFalse(results[r])

    def test_invalid_blood_type_returns_false(self):
        """Unknown/invalid blood types should return False, not raise."""
        r1 = is_compatible('X+', 'A+')
        r2 = is_compatible('O+', 'Z-')
        r3 = is_compatible('', 'A+')
        print(f"\n[test_invalid_blood_type_returns_false] 'X+' vs 'A+': {r1}, 'O+' vs 'Z-': {r2}, '' vs 'A+': {r3}")
        self.assertFalse(r1)
        self.assertFalse(r2)
        self.assertFalse(r3)

    def test_exact_match_always_compatible(self):
        """Every blood type should be compatible with itself."""
        all_types = ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']
        results = {bt: is_compatible(bt, bt) for bt in all_types}
        print(f"\n[test_exact_match_always_compatible] results: {results}")
        for bt in all_types:
            with self.subTest(blood_type=bt):
                self.assertTrue(results[bt])

    def test_ab_positive_recipient_accepts_all_donors(self):
        """AB+ recipient can receive from all 8 blood types."""
        donors = get_compatible_donors('AB+')
        print(f"\n[test_ab_positive_recipient_accepts_all_donors] compatible donors: {donors}")
        self.assertEqual(len(donors), 8)

    def test_o_negative_recipient_only_accepts_o_negative(self):
        """O- recipient can only receive from O-."""
        donors = get_compatible_donors('O-')
        print(f"\n[test_o_negative_recipient_only_accepts_o_negative] compatible donors: {donors}")
        self.assertEqual(donors, ['O-'])

    def test_o_negative_donor_can_give_to_all(self):
        """O- donor can give to all 8 blood types."""
        recipients = get_compatible_recipients('O-')
        print(f"\n[test_o_negative_donor_can_give_to_all] compatible recipients: {recipients}")
        self.assertEqual(len(recipients), 8)

    def test_ab_positive_donor_can_only_give_to_ab_positive(self):
        """AB+ donor can only give to AB+."""
        recipients = get_compatible_recipients('AB+')
        print(f"\n[test_ab_positive_donor_can_only_give_to_ab_positive] compatible recipients: {recipients}")
        self.assertEqual(recipients, ['AB+'])


# ===========================================================================
# 3. MCDM / TOPSIS TESTS
# ===========================================================================

class MCDMRankDonorsTests(TestCase):

    def test_empty_donor_list_returns_empty(self):
        result = rank_donors_mcdm([], 27.7, 85.3, {}, 'A+')
        print(f"\n[test_empty_donor_list_returns_empty] result: {result}")
        self.assertEqual(result, [])

    def test_none_donor_list_returns_empty(self):
        result = rank_donors_mcdm(None, 27.7, 85.3, {}, 'A+')
        print(f"\n[test_none_donor_list_returns_empty] result: {result}")
        self.assertEqual(result, [])

    def test_single_compatible_donor_returns_score_one(self):
        """A single compatible donor should get a score of 1.0."""
        donor = make_donor(1, 'A+')
        result = rank_donors_mcdm([donor], 27.7, 85.3, {1: 5.0}, 'A+')
        print(f"\n[test_single_compatible_donor_returns_score_one] result: {[(d.id, score) for d, score in result]}")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], 1.0)

    def test_incompatible_donors_completely_excluded(self):
        """
        CRITICAL SAFETY TEST:
        An incompatible donor (AB- for an A+ request) must never appear
        in rankings, regardless of how good their other scores are.
        """
        incompatible = make_donor(1, 'AB-', donation_count=100)
        compatible = make_donor(2, 'O-', donation_count=1)
        distances = {1: 1.0, 2: 20.0}

        result = rank_donors_mcdm([incompatible, compatible], 27.7, 85.3, distances, 'A+')
        result_ids = [d.id for d, score in result]
        print(f"\n[test_incompatible_donors_completely_excluded] result ids: {result_ids}")
        print(f"  full result: {[(d.id, d.blood_type, round(score,4)) for d, score in result]}")

        self.assertNotIn(1, result_ids, "Incompatible AB- donor must never appear in results")
        self.assertIn(2, result_ids)

    def test_all_incompatible_returns_empty(self):
        """If no donor is compatible, result must be empty."""
        donors = [make_donor(1, 'AB+'), make_donor(2, 'AB-')]
        result = rank_donors_mcdm(donors, 27.7, 85.3, {1: 5.0, 2: 5.0}, 'O-')
        print(f"\n[test_all_incompatible_returns_empty] result: {result}")
        self.assertEqual(result, [])

    def test_closer_donor_ranked_higher_when_other_factors_equal(self):
        """When donation count and recency are equal, closer donor ranks higher."""
        close = make_donor(1, 'A+', donation_count=5,
                           last_donation_date=date.today() - timedelta(days=90))
        far = make_donor(2, 'A+', donation_count=5,
                         last_donation_date=date.today() - timedelta(days=90))
        distances = {1: 3.0, 2: 20.0}

        result = rank_donors_mcdm([close, far], 27.7, 85.3, distances, 'A+')
        print(f"\n[test_closer_donor_ranked_higher_when_other_factors_equal]")
        print(f"  result: {[(d.id, round(score,4)) for d, score in result]}")
        self.assertEqual(result[0][0].id, 1, "Closer donor should rank first")

    def test_scores_are_between_zero_and_one(self):
        """All TOPSIS scores must be in [0, 1]."""
        donors = [
            make_donor(1, 'A+', donation_count=10),
            make_donor(2, 'O-', donation_count=2),
            make_donor(3, 'A-', donation_count=5),
        ]
        distances = {1: 5.0, 2: 15.0, 3: 8.0}

        result = rank_donors_mcdm(donors, 27.7, 85.3, distances, 'A+')
        print(f"\n[test_scores_are_between_zero_and_one]")
        print(f"  result: {[(d.id, round(score,4)) for d, score in result]}")
        for donor, score in result:
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    def test_result_sorted_descending_by_score(self):
        """Results must always be in descending score order."""
        donors = [
            make_donor(1, 'A+', donation_count=10),
            make_donor(2, 'O-', donation_count=3),
            make_donor(3, 'A-', donation_count=7),
        ]
        distances = {1: 5.0, 2: 20.0, 3: 10.0}

        result = rank_donors_mcdm(donors, 27.7, 85.3, distances, 'A+')
        scores = [score for _, score in result]
        print(f"\n[test_result_sorted_descending_by_score]")
        print(f"  result: {[(d.id, round(score,4)) for d, score in result]}")
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_donor_never_donated_treated_as_fully_recovered(self):
        """
        A donor who has never donated (last_donation_date=None) should
        get the maximum recency score (90 days), not an error.
        """
        never_donated = make_donor(1, 'A+', last_donation_date=None)
        recent_donor = make_donor(2, 'A+', last_donation_date=date.today() - timedelta(days=5))
        distances = {1: 10.0, 2: 10.0}

        result = rank_donors_mcdm([never_donated, recent_donor], 27.7, 85.3, distances, 'A+')
        print(f"\n[test_donor_never_donated_treated_as_fully_recovered]")
        print(f"  result: {[(d.id, round(score,4)) for d, score in result]}")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0].id, 1)


class NormalizeMatrixTests(TestCase):

    def test_normalized_column_magnitude_is_one(self):
        """After vector normalization, each column's L2 norm must equal 1."""
        matrix = np.array([
            [3.0, 10.0, 90.0],
            [15.0, 2.0, 45.0],
            [7.0, 5.0, 60.0],
        ])
        normalized = normalize_matrix(matrix)
        col_norms = [round(np.sqrt(np.sum(normalized[:, j] ** 2)), 6) for j in range(matrix.shape[1])]
        print(f"\n[test_normalized_column_magnitude_is_one]")
        print(f"  normalized matrix:\n{normalized}")
        print(f"  column L2 norms: {col_norms}")
        for j, norm in enumerate(col_norms):
            self.assertAlmostEqual(norm, 1.0, places=6)

    def test_empty_matrix_returns_empty(self):
        """Empty matrix input must return empty, not raise."""
        empty = np.array([]).reshape(0, 3)
        result = normalize_matrix(empty)
        print(f"\n[test_empty_matrix_returns_empty] result size: {result.size}, shape: {result.shape}")
        self.assertEqual(result.size, 0)

    def test_zero_column_handled_without_error(self):
        """A column of all zeros must not cause division by zero."""
        matrix = np.array([[0.0, 5.0], [0.0, 3.0]])
        result = normalize_matrix(matrix)
        print(f"\n[test_zero_column_handled_without_error]")
        print(f"  input:\n{matrix}")
        print(f"  result:\n{result}")
        self.assertTrue(np.all(result[:, 0] == 0.0))


# ===========================================================================
# 4. ELIGIBILITY TESTS
# ===========================================================================

class DonorEligibilityTests(TestCase):

    def _make_eligible_setup(self, blood_type='A+', hospital_lat=27.7,
                              hospital_lon=85.3, donor_lat=27.71,
                              donor_lon=85.31):
        donor = make_donor(
            id=1,
            blood_type=blood_type,
            latitude=donor_lat,
            longitude=donor_lon,
            is_available=True,
            last_donation_date=date.today() - timedelta(days=100),
        )
        request = make_request(blood_type, hospital_lat, hospital_lon)
        return donor, request

    @patch('algorithms.eligibility.DonorResponse')
    def test_fully_eligible_donor_returns_true(self, mock_dr):
        from algorithms.eligibility import is_donor_eligible
        mock_dr.objects.filter.return_value.exists.return_value = False

        donor, request = self._make_eligible_setup()
        result = is_donor_eligible(donor, request)
        print(f"\n[test_fully_eligible_donor_returns_true] result: {result}")
        self.assertTrue(result)

    @patch('algorithms.eligibility.DonorResponse')
    def test_unavailable_donor_excluded(self, mock_dr):
        from algorithms.eligibility import is_donor_eligible
        mock_dr.objects.filter.return_value.exists.return_value = False

        donor, request = self._make_eligible_setup()
        donor.is_available = False
        result = is_donor_eligible(donor, request)
        print(f"\n[test_unavailable_donor_excluded] is_available=False → result: {result}")
        self.assertFalse(result)

    @patch('algorithms.eligibility.DonorResponse')
    def test_donor_donated_too_recently_excluded(self, mock_dr):
        """Donor who donated 30 days ago (< 90 day cooldown) must be excluded."""
        from algorithms.eligibility import is_donor_eligible
        mock_dr.objects.filter.return_value.exists.return_value = False

        donor, request = self._make_eligible_setup()
        donor.last_donation_date = date.today() - timedelta(days=30)
        result = is_donor_eligible(donor, request)
        print(f"\n[test_donor_donated_too_recently_excluded] donated 30 days ago → result: {result}")
        self.assertFalse(result)

    @patch('algorithms.eligibility.DonorResponse')
    def test_incompatible_blood_type_excluded(self, mock_dr):
        """Donor with incompatible blood type must be excluded."""
        from algorithms.eligibility import is_donor_eligible
        mock_dr.objects.filter.return_value.exists.return_value = False

        donor, request = self._make_eligible_setup()
        donor.blood_type = 'AB+'
        request.blood_type = 'O-'
        result = is_donor_eligible(donor, request)
        print(f"\n[test_incompatible_blood_type_excluded] donor=AB+, request=O- → result: {result}")
        self.assertFalse(result)

    @patch('algorithms.eligibility.DonorResponse')
    def test_previously_declined_donor_excluded(self, mock_dr):
        """Donor who previously declined this request must be excluded."""
        from algorithms.eligibility import is_donor_eligible
        mock_dr.objects.filter.return_value.exists.return_value = True

        donor, request = self._make_eligible_setup()
        result = is_donor_eligible(donor, request)
        print(f"\n[test_previously_declined_donor_excluded] previously declined → result: {result}")
        self.assertFalse(result)

    @patch('algorithms.eligibility.DonorResponse')
    def test_donor_too_far_excluded(self, mock_dr):
        """Donor beyond max_distance must be excluded."""
        from algorithms.eligibility import is_donor_eligible
        mock_dr.objects.filter.return_value.exists.return_value = False

        donor, request = self._make_eligible_setup(donor_lat=28.5, donor_lon=86.5)
        result = is_donor_eligible(donor, request)
        print(f"\n[test_donor_too_far_excluded] donor at (28.5, 86.5) → result: {result}")
        self.assertFalse(result)

    @patch('algorithms.eligibility.DonorResponse')
    def test_missing_donor_coordinates_excluded(self, mock_dr):
        """
        CRITICAL: Donor with missing coordinates must be EXCLUDED,
        not treated as eligible by default (fail-closed, not fail-open).
        """
        from algorithms.eligibility import is_donor_eligible
        mock_dr.objects.filter.return_value.exists.return_value = False

        donor, request = self._make_eligible_setup()
        donor.latitude = None
        donor.longitude = None
        result = is_donor_eligible(donor, request)
        print(f"\n[test_missing_donor_coordinates_excluded] lat=None, lon=None → result: {result}")
        self.assertFalse(result)

    @patch('algorithms.eligibility.DonorResponse')
    def test_missing_hospital_coordinates_excluded(self, mock_dr):
        """Hospital with missing coordinates must also cause exclusion."""
        from algorithms.eligibility import is_donor_eligible
        mock_dr.objects.filter.return_value.exists.return_value = False

        donor, request = self._make_eligible_setup()
        request.hospital.latitude = None
        request.hospital.longitude = None
        result = is_donor_eligible(donor, request)
        print(f"\n[test_missing_hospital_coordinates_excluded] hospital lat=None, lon=None → result: {result}")
        self.assertFalse(result)

    @patch('algorithms.eligibility.DonorResponse')
    def test_zero_coordinates_are_not_treated_as_missing(self, mock_dr):
        """
        CRITICAL: lat/lon of 0.0 is a valid coordinate, not a missing one.
        A donor near (0,0) and a hospital at (0,0) should pass the
        coordinate check and be evaluated on actual distance, not excluded
        because Python treats 0.0 as falsy.
        """
        from algorithms.eligibility import is_donor_eligible
        mock_dr.objects.filter.return_value.exists.return_value = False

        donor, request = self._make_eligible_setup(
            hospital_lat=0.0, hospital_lon=0.0,
            donor_lat=0.001, donor_lon=0.001
        )
        result = is_donor_eligible(donor, request)
        print(f"\n[test_zero_coordinates_are_not_treated_as_missing] hospital=(0,0), donor=(0.001,0.001) → result: {result}")
        self.assertTrue(result)

    @patch('algorithms.eligibility.DonorResponse')
    def test_distance_attached_to_donor_on_success(self, mock_dr):
        """
        When a donor passes eligibility, their distance should be
        attached as donor.distance for use in downstream MCDM ranking.
        """
        from algorithms.eligibility import is_donor_eligible
        mock_dr.objects.filter.return_value.exists.return_value = False

        donor, request = self._make_eligible_setup()
        is_donor_eligible(donor, request)
        print(f"\n[test_distance_attached_to_donor_on_success] donor.distance: {donor.distance}")

        self.assertTrue(hasattr(donor, 'distance'))
        self.assertIsNotNone(donor.distance)
        self.assertGreater(donor.distance, 0)