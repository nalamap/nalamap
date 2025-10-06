from typing import Any, Dict, List, Optional, Tuple
import math
import re
from collections import Counter

Feature = Dict[str, Any]
FC = Dict[str, Any]


def _to_fc(obj: Dict[str, Any]) -> FC:
    if obj.get("type") == "FeatureCollection":
        return obj
    if obj.get("type") == "Feature":
        return {"type": "FeatureCollection", "features": [obj]}
    raise ValueError("Unsupported GeoJSON type")


def _features(fc: FC) -> List[Feature]:
    return fc.get("features", [])


def list_fields(fc: FC, sample: int = 1000) -> Dict[str, Any]:
    feats = _features(fc)[:sample]
    type_guess = {}
    null_counts = {}
    examples = {}
    for f in feats:
        props = f.get("properties", {}) or {}
        for k, v in props.items():
            null_counts[k] = null_counts.get(k, 0) + (1 if v is None else 0)
            t = "null" if v is None else type(v).__name__
            # keep the most informative type seen
            prev = type_guess.get(k)
            if prev is None or prev == "null":
                type_guess[k] = t
            # store example
            if k not in examples and v is not None:
                examples[k] = v
    fields = []
    for k in sorted(type_guess.keys()):
        fields.append(
            {
                "name": k,
                "type": type_guess[k],
                "null_count": null_counts.get(k, 0),
                "example": examples.get(k),
            }
        )
    return {"fields": fields, "sample_size": len(feats)}


def summarize(fc: FC, fields: List[str]) -> Dict[str, Any]:
    feats = _features(fc)
    out = {}
    for fld in fields:
        vals = []
        for f in feats:
            v = (f.get("properties") or {}).get(fld)
            if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v)):
                vals.append(float(v))
        if vals:
            vals_sorted = sorted(vals)
            n = len(vals)

            def pct(p):
                i = int(max(0, min(n - 1, round(p * (n - 1)))))
                return vals_sorted[i]

            out[fld] = {
                "count": n,
                "mean": sum(vals) / n,
                "min": vals_sorted[0],
                "max": vals_sorted[-1],
                "p25": pct(0.25),
                "p50": pct(0.5),
                "p75": pct(0.75),
            }
        else:
            out[fld] = {"count": 0}
    return out


_token = re.compile(
    r"""
    \s*(?:
        (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
      | "(?P<identq>[^"]+)"
      | '(?P<string>[^']*)'
      | (?P<num>-?\d+(?:\.\d+)?)
      | (?P<op>>=|<=|!=|=|>|<)
      | (?P<kw>AND|OR|NOT|IN|IS|NULL)
      | (?P<lpar>\()
      | (?P<rpar>\))
      | (?P<comma>,)
    )
""",
    re.X,
)


def _tokenize(s: str):
    pos = 0
    while pos < len(s):
        m = _token.match(s, pos)
        if not m:
            raise ValueError(f"Bad token near: {s[pos:pos+20]}")
        pos = m.end()
        yield m


# A very small recursive-descent parser -> AST for predicates.
# To keep it short here, we evaluate in a simple way during filtering.


def _cmp(a, op, b):
    if a is None or b is None:
        return False
    try:
        if op == "=":
            return a == b
        if op == "!=":
            return a != b
        if op == ">":
            return a > b
        if op == "<":
            return a < b
        if op == ">=":
            return a >= b
        if op == "<=":
            return a <= b
    except Exception:
        return False
    return False


def _parse_literal(tok):
    if tok.group("string") is not None:
        return tok.group("string")
    if tok.group("num") is not None:
        s = tok.group("num")
        return float(s) if "." in s else int(s)
    return None


def _read(tokens):
    return next(tokens, None)


def _peek(state):
    return state["cur"]


def _advance(state, tokens):
    state["cur"] = _read(tokens)
    return state["cur"]


def _expect_kw(state, kw):
    cur = _peek(state)
    if not (cur and (cur.group("kw") == kw)):
        raise ValueError(f"Expected {kw}")
    _advance(state, state["tokens"])


def _expect_op(state, ops):
    cur = _peek(state)
    if not (cur and cur.group("op") in ops):
        raise ValueError(f"Expected op in {ops}")
    op = cur.group("op")
    _advance(state, state["tokens"])
    return op


def _field_name(tok) -> str:
    if tok.group("ident"):
        return tok.group("ident")
    if tok.group("identq"):
        return tok.group("identq")
    raise ValueError("Expected field name")


def _parse_primary(state):
    cur = _peek(state)
    if cur and cur.group("lpar"):
        _advance(state, state["tokens"])
        node = _parse_expr(state)
        if not (_peek(state) and _peek(state).group("rpar")):
            raise ValueError("Missing )")
        _advance(state, state["tokens"])
        return node

    # field [IS (NOT)? NULL] | field IN (...) | field op literal
    if cur and (cur.group("ident") or cur.group("identq")):
        field = _field_name(cur)
        _advance(state, state["tokens"])

        cur = _peek(state)
        if cur and cur.group("kw") == "IS":
            _advance(state, state["tokens"])
            cur = _peek(state)
            is_not = False
            if cur and cur.group("kw") == "NOT":
                is_not = True
                _advance(state, state["tokens"])
            _expect_kw(state, "NULL")
            return ("isnull", field, is_not)

        if cur and cur.group("kw") == "IN":
            _advance(state, state["tokens"])
            if not (_peek(state) and _peek(state).group("lpar")):
                raise ValueError("Expected ( after IN")
            _advance(state, state["tokens"])
            values = []
            while True:
                cur = _peek(state)
                if not cur:
                    raise ValueError("Unterminated IN list")
                if cur.group("rpar"):
                    _advance(state, state["tokens"])
                    break
                if cur.group("comma"):
                    _advance(state, state["tokens"])
                    continue
                v = _parse_literal(cur)
                if v is None:
                    raise ValueError("Expected literal in IN list")
                values.append(v)
                _advance(state, state["tokens"])
            return ("in", field, values)

        # comparison
        op = _expect_op(state, {">=", "<=", "!=", "=", ">", "<"})
        cur = _peek(state)
        if not cur:
            raise ValueError("Expected literal after op")
        lit = _parse_literal(cur)
        if lit is None:
            raise ValueError("Expected literal after op")
        _advance(state, state["tokens"])
        return ("cmp", field, op, lit)

    # literal (bool context) not supported
    raise ValueError("Expected expression")


def _parse_not(state):
    cur = _peek(state)
    if cur and cur.group("kw") == "NOT":
        _advance(state, state["tokens"])
        node = _parse_not(state)
        return ("not", node)
    return _parse_primary(state)


def _parse_and(state):
    node = _parse_not(state)
    while _peek(state) and _peek(state).group("kw") == "AND":
        _advance(state, state["tokens"])
        rhs = _parse_not(state)
        node = ("and", node, rhs)
    return node


def _parse_expr(state):
    node = _parse_and(state)
    while _peek(state) and _peek(state).group("kw") == "OR":
        _advance(state, state["tokens"])
        rhs = _parse_and(state)
        node = ("or", node, rhs)
    return node


def _compile_predicate(where: str):
    tokens = iter(_tokenize(where))
    state = {"tokens": tokens, "cur": None}
    _advance(state, tokens)
    _parse_expr(state)  # Parse to validate syntax
    if _peek(state):
        raise ValueError("Unexpected trailing tokens")

    def eval_node(node, props):
        kind = node[0]
        if kind == "cmp":
            _, fld, op, lit = node
            return _cmp(props.get(fld), op, lit)
        if kind == "in":
            _, fld, values = node
            return props.get(fld) in set(values)
        if kind == "isnull":
            _, fld, is_not = node
            is_null = props.get(fld) is None
            return (not is_null) if is_not else is_null
        if kind == "and":
            return eval_node(node[1], props) and eval_node(node[2], props)
        if kind == "or":
            return eval_node(node[1], props) or eval_node(node[2], props)
        if kind == "not":
            return not eval_node(node[1], props)
        raise ValueError(f"Unknown node {kind}")

    return eval_node


def filter_where(fc: FC, where: str) -> FC:
    pred = _compile_predicate(where)
    feats = [
        f
        for f in _features(fc)
        if pred(
            (f.get("properties") or {}),
        )
    ]
    return {"type": "FeatureCollection", "features": feats}


def select_fields(
    fc: FC,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    keep_geometry: bool = True,
) -> FC:
    feats_out = []
    for f in _features(fc):
        props = (f.get("properties") or {}).copy()
        if include:
            props = {k: props.get(k) for k in include}
        if exclude:
            for k in exclude:
                props.pop(k, None)
        newf = {"type": "Feature", "properties": props}
        if keep_geometry:
            newf["geometry"] = f.get("geometry")
        feats_out.append(newf)
    return {"type": "FeatureCollection", "features": feats_out}


def sort_by(fc: FC, fields: List[Tuple[str, str]]) -> FC:
    feats = list(_features(fc))

    def keyfun(feat):
        props = feat.get("properties") or {}
        key = []
        for fld, direction in fields:
            v = props.get(fld)
            key.append((v is None, v))  # Nones last
        return tuple(key)

    reverse = any(d.lower() == "desc" for _, d in fields)
    feats.sort(key=keyfun, reverse=reverse)
    return {"type": "FeatureCollection", "features": feats}


def unique_values(fc: FC, field: str, top_k: Optional[int] = None) -> Dict[str, Any]:
    vals = []
    for f in _features(fc):
        v = (f.get("properties") or {}).get(field)
        if v is not None:
            vals.append(v)
    cnt = Counter(vals)
    pairs = cnt.most_common(top_k) if top_k else list(cnt.items())
    return {"field": field, "values": [{"value": v, "count": c} for v, c in pairs]}
