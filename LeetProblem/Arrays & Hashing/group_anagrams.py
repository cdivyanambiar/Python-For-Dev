"""
LeetCode 49 - Group Anagrams (Medium)

Given an array of strings `strs`, group the anagrams together.
You can return the answer in any order.

Examples:
    ["eat","tea","tan","ate","nat","bat"] -> [["bat"],["nat","tan"],["ate","eat","tea"]]
    [""]                                   -> [[""]]
    ["a"]                                  -> [["a"]]

Constraints:
    1 <= len(strs) <= 10^4
    0 <= len(strs[i]) <= 100
    strs[i] consists of lowercase English letters.
"""
from typing import List
from collections import defaultdict

class Solution:
    def groupAnagrams(self, strs: List[str]) -> List[List[str]]:
        freq = defaultdict(list)
        print(freq)
        for s in strs:
            key = tuple(sorted(s))
            freq[key].append(s)
        return list(freq.values())


def _normalize(groups: List[List[str]]) -> List[List[str]]:
    # Output order is arbitrary, so sort inside and across groups before comparing
    return sorted(sorted(g) for g in groups)


if __name__ == "__main__":
    sol = Solution()
    assert _normalize(sol.groupAnagrams(["eat", "tea", "tan", "ate", "nat", "bat"])) == [
        ["ate", "eat", "tea"],
        ["bat"],
        ["nat", "tan"],
    ]
    assert _normalize(sol.groupAnagrams([""])) == [[""]]
    assert _normalize(sol.groupAnagrams(["a"])) == [["a"]]
    print("All tests passed")
