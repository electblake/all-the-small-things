import calendar
import heapq
import operator
import re
from bisect import bisect_left, insort_right
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import groupby
from threading import Event

import pcre2
from PySide6.QtCore import QLocale

from .catalog import Catalog, Row

EPOCH = 116444736000000000


@dataclass(frozen=True)
class Options:
    case: bool = False
    words: bool = False
    path: bool = False
    auto_path: bool = True
    regex: bool = False
    kind: str = "all"
    sort: str = "name"
    descending: bool = False
    folders_first: bool = True


def tokenize(query):
    tokens, part = [], []
    characters = iter(query)
    for char in characters:
        if char == '"':
            part.append(char)
            char = next(characters)
            while char != '"':
                part.append(char)
                char = next(characters)
            part.append(char)
        elif char.isspace():
            if part:
                tokens.append("".join(part))
                part = []
        elif char in "<>" and part and part[-1] == ":":
            part.append(char)
        elif char in "<>|" or (char == "!" and not part):
            if part:
                tokens.append("".join(part))
                part = []
            tokens.append(char)
        else:
            part.append(char)
    if part:
        tokens.append("".join(part))
    return tokens


def size_value(value):
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([kmgtpe]?)(?:i?b)?", value, re.IGNORECASE)
    number, unit = match.groups()
    scale = 1024 ** (" kmgtpe".index(unit.lower()) if unit else 0)
    return int(Decimal(number) * scale), scale


def date_value(value, now):
    value = value.lower()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if value in ("today", "yesterday", "tomorrow"):
        start = today + timedelta(days={"today": 0, "yesterday": -1, "tomorrow": 1}[value])
        end = start + timedelta(days=1)
    elif value in ("thisweek", "lastweek"):
        start = today - timedelta(days=today.weekday() + (7 if value == "lastweek" else 0))
        end = start + timedelta(days=7)
    elif value in ("thismonth", "lastmonth", "thisyear", "lastyear", "mtd", "ytd"):
        month = today.month if "month" in value or value == "mtd" else 1
        year = today.year
        if value == "lastmonth":
            month -= 1
            if month == 0:
                month, year = 12, year - 1
        if value == "lastyear":
            year -= 1
        start = today.replace(year=year, month=month, day=1)
        end = (start.replace(year=year + 1) if "year" in value or value == "ytd"
               else start + timedelta(days=calendar.monthrange(year, month)[1]))
        if value in ("mtd", "ytd"):
            end = now
    elif re.fullmatch(r"\d+(?:seconds?|minutes?|hours?|days?|weeks?)", value):
        count, unit = re.fullmatch(r"(\d+)(.*)", value).groups()
        seconds = {"second": 1, "minute": 60, "hour": 3600, "day": 86400, "week": 604800}
        start, end = now - timedelta(seconds=int(count) * seconds[unit.rstrip("s")]), now
    else:
        normalized = value.replace("/", "-")
        if "/" in value:
            components = value.split("/")
            if len(components) == 2 and len(components[1]) == 4:
                normalized = f"{components[1]}-{components[0]}"
            elif len(components) == 3 and len(components[0]) != 4:
                pattern = QLocale().dateFormat(QLocale.FormatType.ShortFormat)
                month, day = components[:2] if pattern.index("M") < pattern.index("d") else components[1::-1]
                normalized = f"{components[2]}-{int(month):02d}-{int(day):02d}"
        if re.fullmatch(r"\d{8}", normalized):
            normalized = f"{normalized[:4]}-{normalized[4:6]}-{normalized[6:]}"
        parts = normalized.split("-")
        if len(parts) == 1 and len(value) <= 4:
            start = today.replace(year=int(value), month=1, day=1)
            end = start.replace(year=start.year + 1)
        elif len(parts) == 2:
            start = datetime(int(parts[0]), int(parts[1]), 1, tzinfo=now.tzinfo)
            end = start + timedelta(days=calendar.monthrange(start.year, start.month)[1])
        else:
            start = datetime.fromisoformat(normalized).replace(tzinfo=now.tzinfo)
            precision = timedelta(days=1)
            if "t" in value:
                precision = timedelta(seconds=1) if value.count(":") == 2 else timedelta(minutes=1)
            end = start + precision
    return int(start.timestamp() * 10_000_000) + EPOCH, int(end.timestamp() * 10_000_000) + EPOCH


def comparison(value, convert, date=False):
    if value == "unknown":
        return lambda number: number is None
    if not value:
        return lambda number: number is not None and number != 0
    match = re.fullmatch(r"(<=|>=|==|!=|=|<|>|!)?(.*)", value)
    op, text = match.groups()
    if ".." in text:
        first, last = text.split("..", 1)
        low = convert(first)[0]
        last_value = convert(last)
        high = last_value[1] - 1 if date else last_value[0]
        return lambda number: number is not None and low <= number <= high
    if not date and "-" in text:
        first, last = text.split("-", 1)
        low, high = convert(first)[0], convert(last)[0]
        return lambda number: number is not None and low <= number <= high
    start, step = convert(text)
    end = step if date else start + step
    if op is None or op == "!":
        return lambda number: number is not None and ((start <= number < end) != (op == "!"))
    function = {"<": operator.lt, ">": operator.gt, "<=": operator.le,
                ">=": operator.ge, "=": operator.eq, "==": operator.eq, "!=": operator.ne}[op]
    return lambda number: number is not None and function(number, start)


def text_match(term, options):
    value = term.replace('"', "")
    path = options.path or (options.auto_path and not options.regex and ("\\" in value or "/" in value))
    if not options.regex:
        value = value.replace("/", "\\")
    wildcard = not options.regex and any(char in value for char in "*?")
    if options.regex:
        pattern = value
    elif wildcard:
        pattern = ""
        position = 0
        while position < len(value):
            char = value[position]
            if value[position:position + 2] == "**":
                pattern += ".*"
                position += 2
                continue
            pattern += {"*": r"[^\\]*", "?": r"[^\\]"}.get(char, re.escape(char))
            position += 1
        pattern = r"\A" + pattern + r"\z"
    else:
        pattern = re.escape(value)
    if options.words:
        pattern = r"(?<!\w)(?:" + pattern + r")(?!\w)"
    if not options.regex and not wildcard and not options.words:
        needle = value if options.case else value.casefold()
        if path:
            return lambda row: needle in (row.path if options.case else row.path.casefold())
        return lambda row: needle in (row.entry.name if options.case else row.entry.key)
    expression = pcre2.compile(pattern, flags=0 if options.case else pcre2.IGNORECASE)
    return lambda row: expression.search(row.path if path else row.entry.name) is not None


def term_predicate(term, options, now):
    modifiers = {"case": ("case", True), "nocase": ("case", False),
                 "wholewords": ("words", True), "nowholewords": ("words", False),
                 "path": ("path", True), "nopath": ("path", False), "regex": ("regex", True)}
    while ":" in term:
        prefix, rest = term.split(":", 1)
        key = prefix.lower().replace("-", "")
        if key not in modifiers:
            break
        name, enabled = modifiers[key]
        options = replace(options, **{name: enabled})
        if name == "path":
            options = replace(options, auto_path=enabled)
        term = rest
    if ":" not in term or options.regex:
        return text_match(term, options)
    prefix, value = term.split(":", 1)
    key = prefix.lower().replace("-", "")
    value = value.replace('"', "")
    if key in ("file", "folder"):
        match = text_match(value, options)
        return lambda row: row.metadata.folder == (key == "folder") and match(row)
    if key in ("ext", "extension"):
        values = value.split(";")
        extensions = set(values if options.case else [item.casefold() for item in values])
        return lambda row: not row.metadata.folder and (
            row.entry.extension if options.case else row.entry.extension.casefold()) in extensions
    if key == "size":
        predicate = comparison(value.lower(), size_value)
        return lambda row: predicate(row.metadata.size)
    dates = {"dm": "modified", "datemodified": "modified", "dc": "created",
             "datecreated": "created", "da": "accessed", "dateaccessed": "accessed"}
    if key in dates:
        predicate = comparison(value, lambda text: date_value(text, now), date=True)
        return lambda row: predicate(getattr(row.metadata, dates[key]))
    if key in ("attrib", "attribute", "attributes"):
        names = {"a": "archive", "c": "compressed", "d": "directory", "e": "encrypted",
                 "h": "hidden", "i": "not_content_indexed", "l": "reparse", "n": "normal",
                 "o": "offline", "r": "readonly", "s": "system", "t": "temporary",
                 "p": "pinned", "u": "unpinned", "v": "integrity", "x": "no_scrub", "m": "recall"}
        if value.isdecimal() or value.lower().startswith("0x"):
            mask = int(value, 16 if value.lower().startswith("0x") else 10)
            bits = {1: "readonly", 2: "hidden", 4: "system", 16: "directory", 32: "archive",
                    128: "normal", 256: "temporary", 512: "sparse", 1024: "reparse", 2048: "compressed",
                    4096: "offline", 8192: "not_content_indexed", 16384: "encrypted", 32768: "integrity",
                    131072: "no_scrub", 524288: "pinned", 1048576: "unpinned", 4194304: "recall"}
            required = frozenset(name for bit, name in bits.items() if mask & bit)
        else:
            required = frozenset(names[char] for char in value.lower())
        return lambda row: required <= row.metadata.attributes
    return text_match(term, options)


class Parser:
    def __init__(self, text, options, now):
        self.tokens = tokenize(text) + [None]
        self.position = 0
        self.options = options
        self.now = now

    def atom(self):
        token = self.tokens[self.position]
        self.position += 1
        if token == "!":
            operand = self.atom()
            return lambda row: not operand(row)
        if token == "<":
            expression = self.conjunction()
            {">": True}[self.tokens[self.position]]
            self.position += 1
            return expression
        return term_predicate(token, self.options, self.now)

    def disjunction(self):
        terms = [self.atom()]
        while self.tokens[self.position] == "|":
            self.position += 1
            terms.append(self.atom())
        return lambda row: any(term(row) for term in terms)

    def conjunction(self):
        terms = []
        while self.tokens[self.position] not in (None, ">"):
            terms.append(self.disjunction())
        return lambda row: all(term(row) for term in terms)

    def compile(self):
        expression = self.conjunction()
        {None: True}[self.tokens[self.position]]
        return expression


def compile_query(text, options, now=None):
    clock = datetime.now().astimezone() if now is None else now
    if options.regex:
        pattern = r"(?<!\w)(?:" + text + r")(?!\w)" if options.words else text
        expression = pcre2.compile(pattern, flags=0 if options.case else pcre2.IGNORECASE)
        return lambda row: expression.search(row.path if options.path else row.entry.name) is not None
    return Parser(text, options, clock).compile()


@dataclass
class Results:
    catalog: Catalog
    rows: list
    query: str = ""
    options: Options | None = None

    @property
    def total(self):
        return len(self.rows)

    def window(self, offset, limit):
        return self.rows[offset:offset + limit]

    def index_of(self, selected):
        source = next(source for source in self.catalog.sources if source.identity == selected.source.identity)
        if selected.entry not in source.links.get(selected.entry.object_id, ()):
            return -1
        target = Row(source, selected.entry)
        key = lambda row: order_key(row, self.options)
        index = bisect_left(self.rows, key(target), key=key)
        if index < self.total and self.rows[index].entry == selected.entry and self.rows[index].source.identity == source.identity:
            return index
        return -1


class IndexedRows(Sequence):
    def __init__(self, catalog, references):
        self.sources = {source.identity: source for source in catalog.sources}
        self.references = references

    def __len__(self):
        return len(self.references)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [Row(self.sources[identity], entry) for identity, entry in self.references[index]]
        identity, entry = self.references[index]
        return Row(self.sources[identity], entry)


@dataclass(frozen=True)
class Descending:
    value: object

    def __lt__(self, other):
        return self.value > other.value


def order_key(row, options):
    if options.sort == "name":
        value = row.entry.key
    elif options.sort == "path":
        value = row.path.casefold()
    elif options.sort == "extension":
        value = row.entry.extension.casefold()
    else:
        value = getattr(row.metadata, options.sort)
    missing = value is None
    primary = 0 if missing else value
    if options.descending:
        primary = Descending(primary)
    return (not row.metadata.folder if options.folders_first else False, missing, primary,
            row.path.casefold(), row.source.identity, row.entry.identity)


def update_order(catalog, previous, options, cancelled):
    before = {source.identity: source for source in previous.catalog.sources}
    after = {source.identity: source for source in catalog.sources}
    removals, additions = [], []
    for identity, source in after.items():
        old = before[identity]
        changed = {key for key, version in source.revisions.items() if version > old.version}
        moved = {key for key in changed if key in old.objects and old.objects[key].folder
                 and old.links.get(key, ()) != source.links.get(key, ())}
        affected = set(changed)
        if moved:
            for index, entry in enumerate(old.entries):
                if index % 256 == 0 and cancelled.is_set():
                    return None
                parent = entry.parent_id
                while parent != old.root_id:
                    if parent in moved:
                        affected.add(entry.object_id)
                        break
                    parent = old.links[parent][0].parent_id
        for key in affected:
            old_entries, new_entries = old.links.get(key, ()), source.links.get(key, ())
            if old_entries == new_entries and all(
                order_key(Row(old, entry), options) == order_key(Row(source, entry), options)
                for entry in old_entries
            ):
                continue
            removals.extend((identity, entry) for entry in old_entries)
            additions.extend((identity, entry) for entry in new_entries)
    references = previous.rows.references.copy() if removals or additions else previous.rows.references
    old_key = lambda ref: order_key(Row(before[ref[0]], ref[1]), options)
    new_key = lambda ref: order_key(Row(after[ref[0]], ref[1]), options)
    for reference in removals:
        if cancelled.is_set():
            return None
        position = bisect_left(references, old_key(reference), key=old_key)
        del references[position]
    for reference in additions:
        if cancelled.is_set():
            return None
        insort_right(references, reference, key=new_key)
    return Results(catalog, IndexedRows(catalog, references), "", options)


def ordered_rows(rows, key, descending, cancelled):
    chunks = []
    for start in range(0, len(rows), 4096):
        if cancelled.is_set():
            return
        chunks.append(sorted(rows[start:start + 4096], key=key, reverse=descending))
    for index, row in enumerate(heapq.merge(*chunks, key=key, reverse=descending)):
        if index % 256 == 0 and cancelled.is_set():
            return
        yield row


def search(catalog, text, options, cancelled: Event, previous=None):
    predicate = compile_query(text, options)
    cache_key = options.sort, options.descending, options.folders_first
    cached = catalog.orders.get(cache_key)
    if not text and options.kind == "all" and cached is not None:
        return Results(catalog, cached, "", options)
    if (not text and options.kind == "all" and previous is not None and previous.query == ""
            and previous.options == options and isinstance(previous.rows, IndexedRows)
            and {s.identity for s in previous.catalog.sources} == {s.identity for s in catalog.sources}):
        result = update_order(catalog, previous, options, cancelled)
        if result is not None:
            catalog.orders[cache_key] = result.rows
        return result
    candidates = catalog.rows()
    if text and not options.regex and not options.path and not any(char in text for char in "|<>!*?\\/"):
        literals = [term.replace('"', "") for term in tokenize(text) if ":" not in term]
        if literals:
            needle = max(literals, key=len).casefold()
            candidates = (Row(source, entry) for source in catalog.sources
                          for entry in source.matching_names(needle, cancelled))
    rows = []
    for index, row in enumerate(candidates):
        if index % 256 == 0 and cancelled.is_set():
            return None
        if options.kind == "file" and row.metadata.folder:
            continue
        if options.kind == "folder" and not row.metadata.folder:
            continue
        if not text or predicate(row):
            rows.append(row)
    if cancelled.is_set():
        return None
    getters = {"name": lambda row: row.entry.key, "path": lambda row: row.path.casefold(),
               "extension": lambda row: row.entry.extension.casefold(),
               "size": lambda row: row.metadata.size, "modified": lambda row: row.metadata.modified,
               "created": lambda row: row.metadata.created, "accessed": lambda row: row.metadata.accessed}
    get = getters[options.sort]
    present = [row for row in rows if get(row) is not None]
    absent = [row for row in rows if get(row) is None]
    rows = []
    ordered = ordered_rows(present, get, options.descending, cancelled)
    for _, group in groupby(ordered, key=get):
        if cancelled.is_set():
            return None
        equal = list(group)
        if len(equal) > 1:
            equal.sort(key=lambda row: (row.path.casefold(), row.source.identity, row.entry.identity))
        rows.extend(equal)
    rows.extend(ordered_rows(absent, lambda row: (row.path.casefold(), row.source.identity, row.entry.identity),
                             False, cancelled))
    if options.folders_first:
        rows.sort(key=lambda row: not row.metadata.folder)
    if cancelled.is_set():
        return None
    if not text and options.kind == "all":
        rows = IndexedRows(catalog, [(row.source.identity, row.entry) for row in rows])
        catalog.orders[cache_key] = rows
    return Results(catalog, rows, text, options)
