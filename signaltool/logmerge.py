"""Slår sammen append-logger når en annen kjøring har pushet i mellomtiden (unngår rebase-konflikt i fremoverloggen).
Bruk: python -m signaltool.logmerge <vår_kopi> <origin_kopi> <ut> . CSV med date,ticker først: nøkkel (kol 1, kol 2), vår rad vinner
(nyeste kjøring). Annet (jsonl): union av linjer, origin-rekkefølge først. Ingen rader fjernes eller fylles inn."""
import sys


def merge(ours: str, theirs: str, path_hint: str) -> str:
    a, b = ours.splitlines(), theirs.splitlines()
    if path_hint.endswith(".csv") and a and b and a[0] != b[0] and "run_id" in a[0].split(","):
        return ours if ours.endswith("\n") else ours + "\n"   # første gang med nye kolonner: vår migrerte fil er et overmengde
    if path_hint.endswith(".csv") and a and b and a[0] != b[0] and a[0].startswith(b[0] + ","):
        # ny kolonne lagt til på slutten (f.eks. rangert 27.10): origin-radene får tomme felt, verdiene endres ikke
        extra = "," * (a[0].count(",") - b[0].count(","))
        b = [a[0]] + [l + extra if l else l for l in b[1:]]
    if path_hint.endswith(".csv") and a and b and a[0] == b[0]:
        head = a[0]
        if "run_id" in head.split(","):   # append-logger per kjøring: alle rader beholdes (union)
            have = set(b)
            return "\n".join(b + [l for l in a if l and l not in have and not have.add(l)]) + "\n"
        key = lambda l: tuple(l.split(",")[:2])
        mine = {key(l): l for l in a[1:] if l}
        out, seen = [head], set()
        for l in b[1:]:
            if not l:
                continue
            k = key(l)
            out.append(mine.get(k, l)); seen.add(k)
        out += [l for l in a[1:] if l and key(l) not in seen and not seen.add(key(l))]
        return "\n".join(out) + "\n"
    have = set(b)
    return "\n".join(b + [l for l in a if l not in have and not have.add(l)]) + "\n"


if __name__ == "__main__":
    o, t, out = sys.argv[1:4]
    open(out, "w").write(merge(open(o).read(), open(t).read(), out))
