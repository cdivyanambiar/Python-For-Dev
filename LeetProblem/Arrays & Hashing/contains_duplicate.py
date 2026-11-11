"""
LeetCode 217 - Contains Duplicate (Easy)

Given an integer array `nums`, return True if any value appears at least twice,
and False if every element is distinct.

Examples:
    [1, 2, 3, 1]                  -> True
    [1, 2, 3, 4]                  -> False
    [1, 1, 1, 3, 3, 4, 3, 2, 4, 2] -> True

Constraints:
    1 <= len(nums) <= 10^5
    -10^9 <= nums[i] <= 10^9

Approach: set size comparison (or early-exit set scan).
    Time: O(n)    Space: O(n)
"""
from typing import Iterable, List


class Solution:
    def containsDuplicate(self, nums: List[int]) -> bool:
        # C-speed one-liner; builds the whole set even if the duplicate is at index 1
        return len(set(nums)) != len(nums)

    def containsDuplicateEarlyExit(self, nums: List[int]) -> bool:
        seen = set()
        for x in nums:
            if x in seen:
                return True  # stop at the first repeat
            seen.add(x)
        return False

    def containsDuplicateSort(self, nums: List[int]) -> bool:
        # O(1) extra space variant (sorts a copy only to stay non-destructive)
        s = sorted(nums)
        return any(a == b for a, b in zip(s, s[1:]))


def has_duplicate_stream(stream: Iterable[int]) -> bool:
    """Works on any iterable/generator; stops consuming at the first repeat."""
    seen = set()
    for x in stream:
        if x in seen:
            return True
        seen.add(x)
    return False


if __name__ == "__main__":
    s = Solution()
    cases = [
        ([1, 2, 3, 1], True),
        ([1, 2, 3, 4], False),
        ([1, 1, 1, 3, 3, 4, 3, 2, 4, 2], True),
        ([1], False),
    ]
    for nums, expected in cases:
        assert s.containsDuplicate(nums) is expected
        assert s.containsDuplicateEarlyExit(nums) is expected
        assert s.containsDuplicateSort(nums) is expected
        assert has_duplicate_stream(iter(nums)) is expected
    print("All tests passed")
