"""
LeetCode 1 - Two Sum (Easy)

Given an array of integers `nums` and an integer `target`, return the indices
of the two numbers such that they add up to `target`.

Exactly one solution exists, and the same element may not be used twice.

Examples:
    nums = [2, 7, 11, 15], target = 9  -> [0, 1]
    nums = [3, 2, 4],      target = 6  -> [1, 2]
    nums = [3, 3],         target = 6  -> [0, 1]

Constraints:
    2 <= len(nums) <= 10^4
    -10^9 <= nums[i], target <= 10^9
    Exactly one valid answer exists.

Approach: one-pass hash map (complement lookup).
    Time: O(n)    Space: O(n)
"""
from typing import Iterator, List, Tuple


class Solution:
    def twoSum(self, nums: List[int], target: int) -> List[int]:
        seen = {}  # value -> index
        for i, x in enumerate(nums):
            if (need := target - x) in seen:
                return [seen[need], i]
            seen[x] = i  # insert AFTER the check so an element is never reused
        return []  # unreachable: a solution is guaranteed


def two_sum_stream(nums: List[int], target: int) -> Iterator[Tuple[int, int]]:
    """Generator variant: lazily yields pairs as they are found (streaming / all-pairs follow-up)."""
    seen = {}
    for i, x in enumerate(nums):
        if (need := target - x) in seen:
            yield seen[need], i
        seen[x] = i  # for duplicate values this keeps only the latest index


if __name__ == "__main__":
    s = Solution()
    assert s.twoSum([2, 7, 11, 15], 9) == [0, 1]
    assert s.twoSum([3, 2, 4], 6) == [1, 2]
    assert s.twoSum([3, 3], 6) == [0, 1]
    assert list(two_sum_stream([2, 7, 11, 15], 9)) == [(0, 1)]
    print("All tests passed")
