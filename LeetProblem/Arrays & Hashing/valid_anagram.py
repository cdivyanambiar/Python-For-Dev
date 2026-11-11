"""
LeetCode 242 - Valid Anagram (Easy)

Given two strings `s` and `t`, return True if `t` is an anagram of `s`,
and False otherwise.

Examples:
    s = "anagram", t = "nagaram" -> True
    s = "rat",     t = "car"     -> False

Constraints:
    1 <= len(s), len(t) <= 5 * 10^4
    s and t consist of lowercase English letters.

Follow up:
    What if the inputs contain Unicode characters? How would you adapt your solution?
"""
from collections import Counter

class Solution:
    def isAnagram(self, s: str, t: str) -> bool:
        return sorted(s) == sorted(t[::-1])
    def isAnagram2(self, s: str, t: str) -> bool:
        return Counter(s) == Counter(t)

if __name__ == "__main__":
    sol = Solution()
    assert sol.isAnagram("anagram", "nagaram") is True
    assert sol.isAnagram("rat", "car") is False
    assert sol.isAnagram("a", "ab") is False
    print("All tests passed")
