# MIT License
#
# Copyright (c) 2017 Christian Lyder Jacobsen
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import ast
import collections
import itertools
import sys

import astunparse

# From: https://code.activestate.com/recipes/576694/
class OrderedSet(collections.MutableSet):

    def __init__(self, iterable=None):
        self.end = end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        self.map = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map

    def add(self, key):
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def discard(self, key):
        if key in self.map:
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev

    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, last=True):
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)


class Name(object):
    def __init__(self, name, node):
        self.name = name
        self.nodes = set([node])
    def __eq__(self, other):
        if isinstance(other, ast.AST):
            return other in self.nodes
        return self.name == other.name
    def __or__(self, other):
        assert self.name == other.name
        self.nodes |= other.nodes
    def __str__(self):
        return self.name
    def __repr__(self):
        return '<{}({!r}, {!r})>'.format(self.__class__.__name__, self.name,
                                         self.nodes)


def probably_truthy(node):
    def test(node):
        if node.__class__.__name__ == 'BoolOp':
            return probably_truthy(node)
        return node.__class__.__name__ not in ['Str', 'Num', 'List', 'Set',
                                               'Dict']
    if not node.__class__.__name__ == 'BoolOp':
        return False
    return all(map(test, node.values))


def collect_bool_ops(node):
    nodes = []
    if node.__class__.__name__ == 'BoolOp' and probably_truthy(node):
        nodes.append(node)
    for field, value in ast.iter_fields(node):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, ast.AST):
                    nodes.extend(collect_bool_ops(item))
        elif isinstance(value, ast.AST):
            nodes.extend(collect_bool_ops(value))
    return nodes


def collect_names(node):
    names = OrderedSet()
    if node.__class__.__name__ == 'BoolOp':
        for value in node.values:
            if value.__class__.__name__ in ['BoolOp', 'UnaryOp']:
                names = names | collect_names(value)
            else:
                names = names | OrderedSet(
                    [Name(astunparse.unparse(value).strip(), value)])
    elif node.__class__.__name__ == 'UnaryOp':
        names = names | collect_names(node.operand)
    else:
        names = names | OrderedSet(
            [Name(astunparse.unparse(node).strip(), node)])
    return names


def evaluate(node, names, conditions):
    assert len(names) == len(conditions)
    if node.__class__.__name__ == 'BoolOp':
        result = []
        for value in node.values:
            try:
                idx = list(names).index(value)
                result.append(conditions[idx])
            except ValueError:
                result.append(evaluate(value, names, conditions))
        if node.op.__class__.__name__ == 'And':
            return all(result)
        elif node.op.__class__.__name__ == 'Or':
            return any(result)
        else:
            raise NotImplementedError(
                "Nool op {} not implemented".format(
                    node.op.__class__.__name__))
    elif node.__class__.__name__ == 'UnaryOp':
        if node.op.__class__.__name__ == 'Not':
            return not evaluate(node.operand, names, conditions)
        else:
            raise NotImplementedError(
                "Nool op {} not implemented".format(
                    node.op.__class__.__name__))
    else:
        idx = list(names).index(node)
        return conditions[idx]

def truth_table(node):
    names = collect_names(node)
    conditions = list(itertools.product([False, True], repeat=len(names)))
    rows = [tuple(map(str, names) + [astunparse.unparse(node).strip()])]
    for condition in conditions:
        rows.append(condition + tuple([evaluate(node, names, condition)]))
    return rows


def simple_table(lol, sep=4):
    lol = list(lol)
    column_sizes = [0] * len(lol[0])
    for row in lol:
        for i, column in enumerate(row):
            value = str(column)
            length = len(value)
            if column_sizes[i] < length:
                column_sizes[i] = length
    column_sizes = [s + sep for s in column_sizes]
    result = []
    for i, row in enumerate(lol):
        result.append(('{:^{}}' * len(column_sizes)).format(
            *(n for m in zip((str(c) for c in row), column_sizes)
              for n in m)))
        if i == 0:
            result.append(('{:^{}}' * len(column_sizes)).format(
                *(n for m in zip(('-' * (s - sep)
                  for s in column_sizes), column_sizes) for n in m)))
    return '\n'.join(result)


if False:
    a and b
    a and b or c
    a and (b or c)
    fn(a.something['moo']) and all([n for n in p]) and not a + b
    a and not a + b
    not a + b
    not a


if __name__ == '__main__':
    files = sys.argv[1:] or [__file__]
    for file in files:
        bool_ops = collect_bool_ops(compile(open(file, 'rb').read(),
                                            file, 'exec' ,
                                            ast.PyCF_ONLY_AST, 1))
        result = []
        for op in bool_ops:
            result.append('Expression: {}\n    in {} line: {}\n\n{}\n'.format(
                astunparse.unparse(op).strip(), file, op.lineno,
                simple_table(truth_table(op))))

        print('\n\n'.join(result))
