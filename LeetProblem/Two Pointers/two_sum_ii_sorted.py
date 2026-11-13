"""
LeetCode 167 - Two Sum II - Input Array Is Sorted (Medium)

Given a 1-indexed array `numbers` sorted in non-decreasing order, find two numbers
that add up to `target`. Return their 1-indexed positions [index1, index2], index1 < index2.

Exactly one solution exists, the same element cannot be used twice,
and the solution must use only constant extra space.

Examples:
    numbers = [2, 7, 11, 15], target = 9 -> [1, 2]
    numbers = [2, 3, 4],      target = 6 -> [1, 3]
    numbers = [-1, 0],        target = -1 -> [1, 2]

Constraints:
    2 <= len(numbers) <= 3 * 10^4
    -1000 <= numbers[i] <= 1000, sorted in non-decreasing order
    -1000 <= target <= 1000

Approach: two pointers from both ends.
    Sum too small -> move left up (need a bigger number).
    Sum too big   -> move right down (need a smaller number).
    Time: O(n)    Space: O(1)
"""
from typing import List


class Solution:
    def twoSum(self, numbers: List[int], target: int) -> List[int]:
        l, r = 0, len(numbers) - 1
        while l < r:
            s = numbers[l] + numbers[r]
            if s == target:
                return [l + 1, r + 1]  # problem is 1-indexed
            if s < target:
                l += 1
            else:
                r -= 1
        return []  # unreachable: a solution is guaranteed


if __name__ == "__main__":
    sol = Solution()
    assert sol.twoSum([2, 7, 11, 15], 9) == [1, 2]
    assert sol.twoSum([2, 3, 4], 6) == [1, 3]
    assert sol.twoSum([-1, 0], -1) == [1, 2]
    assert sol.twoSum([1, 2, 3, 4, 4, 9, 56, 90], 8) == [4, 5]
    print("All tests passed")
