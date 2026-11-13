"""
LeetCode 143 - Reorder List (Medium)

Given the head of a singly linked list L0 -> L1 -> ... -> Ln-1 -> Ln, reorder it to:
    L0 -> Ln -> L1 -> Ln-1 -> L2 -> Ln-2 -> ...

You may not modify the values in the nodes. Only the nodes themselves may be changed.
Modify the list in place; return nothing.

Examples:
    1 -> 2 -> 3 -> 4        => 1 -> 4 -> 2 -> 3
    1 -> 2 -> 3 -> 4 -> 5   => 1 -> 5 -> 2 -> 4 -> 3

Constraints:
    1 <= number of nodes <= 5 * 10^4
    1 <= Node.val <= 1000

Approach (three classic linked-list steps):
    1. Find the middle with slow/fast pointers.
    2. Reverse the second half in place.
    3. Merge the two halves by alternating nodes.
    Time: O(n)    Space: O(1)
"""
from typing import List, Optional


class ListNode:
    def __init__(self, val: int = 0, next: Optional["ListNode"] = None):
        self.val = val
        self.next = next


class Solution:
    def reorderList(self, head: Optional[ListNode]) -> None:
        if not head or not head.next:
            return

        # 1. Middle: slow ends at the last node of the first half
        slow, fast = head, head.next
        while fast and fast.next:
            slow = slow.next
            fast = fast.next.next

        # 2. Reverse the second half and cut the list in two
        prev, curr = None, slow.next
        slow.next = None
        while curr:
            curr.next, prev, curr = prev, curr, curr.next

        # 3. Interleave: first half gets nodes from the reversed second half
        first, second = head, prev
        while second:
            first.next, first = second, first.next
            second.next, second = first, second.next


def build(values: List[int]) -> Optional[ListNode]:
    dummy = tail = ListNode()
    for v in values:
        tail.next = ListNode(v)
        tail = tail.next
    return dummy.next


def to_list(head: Optional[ListNode]) -> List[int]:
    out = []
    while head:
        out.append(head.val)
        head = head.next
    return out


if __name__ == "__main__":
    sol = Solution()
    for values, expected in [
        ([1, 2, 3, 4], [1, 4, 2, 3]),
        ([1, 2, 3, 4, 5], [1, 5, 2, 4, 3]),
        ([1], [1]),
        ([1, 2], [1, 2]),
        ([1, 2, 3], [1, 3, 2]),
    ]:
        head = build(values)
        sol.reorderList(head)
        assert to_list(head) == expected, (values, to_list(head), expected)
    print("All tests passed")
