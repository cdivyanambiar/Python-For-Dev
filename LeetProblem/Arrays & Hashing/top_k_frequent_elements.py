"""
LeetCode 347 - Top K Frequent Elements (Medium)

Given an integer array `nums` and an integer `k`, return the k most frequent
elements. You may return the answer in any order.

Examples:
    nums = [1,1,1,2,2,3], k = 2             -> [1, 2]
    nums = [1], k = 1                        -> [1]
    nums = [1,2,1,2,1,2,3,1,3,2], k = 2      -> [1, 2]

Constraints:
    1 <= len(nums) <= 10^5
    -10^4 <= nums[i] <= 10^4
    k is in the range [1, number of unique elements in the array].
    The answer is guaranteed to be unique.

Follow up:
    Your algorithm's time complexity must be better than O(n log n), where n is the array's size.
"""
from typing import List
from collections import defaultdict

class Solution:
    def topKFrequent(self, nums: List[int], k: int) -> List[int]:
        groups = defaultdict(list)
        for i in nums:
            groups[i].append(i)          # {1: [1,1,1], 2: [2,2], 3: [3]}

        ordered = sorted(groups, key=lambda x: len(groups[x]), reverse=True)
        return ordered[:k]

if __name__ == "__main__":
    sol = Solution()
    assert sorted(sol.topKFrequent([1, 1, 1, 2, 2, 3], 2)) == [1, 2]
    assert sorted(sol.topKFrequent([1], 1)) == [1]
    assert sorted(sol.topKFrequent([1, 2, 1, 2, 1, 2, 3, 1, 3, 2], 2)) == [1, 2]
    print("All tests passed")

